from flask import Blueprint, render_template, redirect, url_for, jsonify, send_from_directory, request, flash, current_app, abort, make_response
from flask_login import login_required, current_user
from app.decorators import student_required, student_enrolled, admin_required, teacher_required
from app import db
from app.models import Course, Enrollment, Section, EnrollmentSection, Assignment, AssignmentSubmission, Quiz, QuizQuestion, QuizAttempt, QuizAnswer, Rating, Announcement, Notification, VideoWatchProgress, VideoInteractiveQuestion, VideoQuestionResponse
from app.forms import ProfileForm, SubmissionForm
from app.utils.file_helpers import allowed_file, allowed_file_size
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from uuid import uuid4
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Learner dashboard: enrolled courses, progress, and upcoming items."""
    # Enrolled approved courses
    enrolled_courses = Course.query.join(Enrollment) \
        .filter(Enrollment.student_id == current_user.id) \
        .filter(Course.status == 'approved') \
        .all()

    # Simple course progress per course
    progress_by_course = {}
    continue_learning = []  # recently accessed sections
    upcoming = []  # assignments due soon
    estimated_time = {}  # estimated completion time per course

    try:
        # Preload enrollments
        enrollments = {e.course_id: e for e in Enrollment.query.filter_by(student_id=current_user.id).all()}

        for course in enrolled_courses:
            sections = Section.query.filter_by(course_id=course.id).order_by(Section.order).all()
            total_sections = len(sections)
            enrollment = enrollments.get(course.id)

            completed_sections = 0
            last_accessed = None
            
            # Calculate estimated time (sum of section durations)
            total_duration = sum(s.duration or 0 for s in sections)  # duration in minutes
            estimated_time[course.id] = total_duration
            
            if enrollment:
                # Map enrollment sections
                es_list = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
                completed_sections = sum(1 for es in es_list if es.completed)
                es_by_sec = {es.section_id: es for es in es_list}
                
                # Determine smart next / continue section for this course:
                cont_section = None
                
                # 1. Did the user access an incomplete section most recently?
                incomplete_accessed = [es for es in es_list if not es.completed and es.last_accessed]
                if incomplete_accessed:
                    best_es = max(incomplete_accessed, key=lambda es: es.last_accessed)
                    cont_section = Section.query.get(best_es.section_id)
                
                # 2. If not, find the FIRST incomplete section in sequential order
                if not cont_section:
                    for sec in sections:
                        es = es_by_sec.get(sec.id)
                        if not (es and es.completed):
                            cont_section = sec
                            break
                
                # 3. If all sections completed, fallback to first section
                if not cont_section and sections:
                    cont_section = sections[0]

                if cont_section:
                    recent_time = datetime.min
                    for es in es_list:
                        if es.last_accessed and es.last_accessed > recent_time:
                            recent_time = es.last_accessed
                    if recent_time == datetime.min:
                        recent_time = enrollment.created_at or datetime.utcnow()
                    continue_learning.append({'course': course, 'section': cont_section, 'last_accessed': recent_time})

            completion = (completed_sections / total_sections * 100) if total_sections > 0 else 0
            progress_by_course[course.id] = round(completion, 1)

        # Upcoming assignments within 7 days across all enrolled courses
        upcoming = Assignment.query.join(Section).join(Course) \
            .filter(Course.id.in_([c.id for c in enrolled_courses])) \
            .filter(Assignment.due_date.isnot(None)) \
            .order_by(Assignment.due_date.asc()) \
            .limit(10).all()
    except Exception as e:
        logger.warning(f"Dashboard aggregation fallback: {e}")

    # Calculate quick stats
    total_enrolled = len(enrolled_courses)
    completed_courses = Enrollment.query.filter_by(
        student_id=current_user.id,
        completed=True
    ).count()
    total_certificates = Enrollment.query.filter_by(
        student_id=current_user.id,
        completed=True
    ).filter(Enrollment.certificate_path.isnot(None)).count()
    in_progress = total_enrolled - completed_courses

    blocked_course_ids = {
        e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id, is_blocked=True).all()
    }

    return render_template(
        'student/dashboard.html',
        courses=enrolled_courses,
        blocked_course_ids=blocked_course_ids,
        progress_by_course=progress_by_course,
        continue_learning=sorted(continue_learning, key=lambda x: x['last_accessed'], reverse=True)[:6],
        upcoming=upcoming,
        estimated_time=estimated_time,
        stats={
            'enrolled': total_enrolled,
            'completed': completed_courses,
            'certificates': total_certificates,
            'in_progress': in_progress
        }
    )

@student_bp.route('/course-progress')
@login_required
@student_required
def course_progress():
    enrolled_courses = Course.query.join(Enrollment)\
        .filter(Enrollment.student_id == current_user.id)\
        .filter(Course.status == 'approved')\
        .all()
    course_progress = []
    for course in enrolled_courses:
        sections = Section.query.filter_by(course_id=course.id).order_by(Section.order).all()
        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        enrollment_sections = {es.section_id: es for es in enrollment.sections} if enrollment else {}
        total_sections = len(sections)
        completed_sections = sum(1 for es in enrollment_sections.values() if es.completed)
        completion_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0
        course_progress.append({
            'id': course.id,
            'title': course.title,
            'completion': completion_percentage
        })
    return render_template('student/course_progress.html', courses=enrolled_courses, course_progress=course_progress)

@student_bp.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Check authorization based on role
    if current_user.role == 'student':
        if course.status != 'approved':
            flash('This course has not been published or approved yet.', 'danger')
            return redirect(url_for('student.dashboard'))
        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
        if not enrollment:
            flash('You are not enrolled in this course.', 'danger')
            return redirect(url_for('student.dashboard'))
        if getattr(enrollment, 'is_blocked', False):
            flash(f'Access to "{course.title}" has been restricted by an administrator. Please contact support.', 'warning')
            return redirect(url_for('student.dashboard'))
        enrollment_sections = {es.section_id: es for es in enrollment.sections}
        total_sections = len(course.sections)
        completed_sections = sum(1 for es in enrollment_sections.values() if es.completed)
        completion_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0
    elif current_user.role == 'admin' or (current_user.role == 'teacher' and course.teacher_id == current_user.id):
        # Admin or course teacher is allowed to preview
        enrollment = None
        enrollment_sections = {}
        completion_percentage = 0
    else:
        abort(403)

    from app.models import Module
    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    
    # Gather all ordered sections across modules
    ordered_sections = []
    for m in modules:
        m_secs = Section.query.filter_by(module_id=m.id).order_by(Section.order).all()
        ordered_sections.extend(m_secs)
    
    unassigned = Section.query.filter_by(course_id=course_id, module_id=None).order_by(Section.order).all()
    ordered_sections.extend(unassigned)

    sections = ordered_sections
    locked_sections = set()

    if current_user.role == 'student' and enrollment:
        # Sequential progression: First section is unlocked.
        # Section N is locked if Section N-1 is not completed.
        unlocked_so_far = True
        for i, sec in enumerate(ordered_sections):
            if i == 0:
                continue
            prev_sec = ordered_sections[i - 1]
            prev_es = enrollment_sections.get(prev_sec.id)
            if not (prev_es and prev_es.completed):
                unlocked_so_far = False
            
            if not unlocked_so_far:
                locked_sections.add(sec.id)

    first_section = None
    target_section_id = request.args.get('section_id', type=int)

    # 1. Explicit target section requested in URL query string
    if target_section_id:
        for sec in ordered_sections:
            if sec.id == target_section_id and sec.id not in locked_sections:
                first_section = sec
                break

    # 2. Smart Resumption for Enrolled Student
    if not first_section and enrollment:
        es_list = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
        es_by_sec = {es.section_id: es for es in es_list}

        # Priority A: Check if the student was actively on an incomplete, unlocked section
        incomplete_accessed = [
            es for es in es_list 
            if not es.completed and es.last_accessed and es.section_id not in locked_sections
        ]
        if incomplete_accessed:
            best_es = max(incomplete_accessed, key=lambda es: es.last_accessed)
            first_section = next((s for s in ordered_sections if s.id == best_es.section_id), None)

        # Priority B: Find the NEXT incomplete section in sequential order that is unlocked
        if not first_section:
            for sec in ordered_sections:
                es = es_by_sec.get(sec.id)
                if sec.id not in locked_sections and not (es and es.completed):
                    first_section = sec
                    break

    # 3. Fallback: First unlocked section
    if not first_section:
        for sec in ordered_sections:
            if sec.id not in locked_sections:
                first_section = sec
                break

    # 4. Ultimate Fallback: First section in course
    if not first_section and ordered_sections:
        first_section = ordered_sections[0]

    return render_template('student/course_detail.html', 
                          course=course, 
                          sections=sections,
                          modules=modules,
                          enrollment_sections=enrollment_sections,
                          locked_sections=locked_sections,
                          completion_percentage=completion_percentage,
                          enrollment=enrollment,
                          first_section=first_section)

@student_bp.route('/section/<int:section_id>/content', methods=['GET', 'POST'])
@login_required
def get_section_content(section_id):
    section = Section.query.get_or_404(section_id)
    course = Course.query.get_or_404(section.course_id)
    
    # Check authorization based on role
    if current_user.role == 'student':
        if course.status != 'approved':
            return '<div class="p-4 text-red-700 bg-red-50 rounded-xl border border-red-150">⚠️ This course has not been approved or published yet.</div>', 403
        # Student must be enrolled
        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first_or_404()
        enrollment_sections = {es.section_id: es for es in enrollment.sections}

        # Check sequential progression lock
        from app.models import Module
        modules = Module.query.filter_by(course_id=course.id).order_by(Module.order).all()
        ordered_sections = []
        for m in modules:
            ordered_sections.extend(Section.query.filter_by(module_id=m.id).order_by(Section.order).all())
        ordered_sections.extend(Section.query.filter_by(course_id=course.id, module_id=None).order_by(Section.order).all())
        
        is_locked = False
        unlocked_so_far = True
        for i, sec in enumerate(ordered_sections):
            if i > 0:
                prev_sec = ordered_sections[i - 1]
                prev_es = enrollment_sections.get(prev_sec.id)
                if not (prev_es and prev_es.completed):
                    unlocked_so_far = False
            if not unlocked_so_far and sec.id == section_id:
                is_locked = True
                break

        if is_locked:
            return '''
            <div class="p-8 text-center bg-white rounded-3xl border border-gray-100 shadow-sm max-w-lg mx-auto my-12">
                <div class="w-16 h-16 bg-amber-50 border border-amber-100 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">🔒</div>
                <h3 class="text-xl font-black text-gray-900 mb-2">Lesson Locked</h3>
                <p class="text-sm text-gray-600 leading-relaxed mb-6">You must complete the previous lesson and mark it as complete before unlocking this section.</p>
                <div class="bg-amber-50/60 p-3 rounded-xl border border-amber-100/60 text-xs font-semibold text-amber-800">
                    💡 Tip: Go back to your last active section and click "Mark as Completed".
                </div>
            </div>
            ''', 403
        # Fetch or create EnrollmentSection for tracking
        enrollment_section = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
        if not enrollment_section:
            enrollment_section = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
            db.session.add(enrollment_section)

        # Update tracking
        enrollment_section.view_count = (enrollment_section.view_count or 0) + 1
        enrollment_section.last_accessed = datetime.utcnow()
        db.session.commit()

        # Handle marking as complete with instant auto-progression to next section
        if request.method == 'POST' and ('mark_completed' in request.form or (request.json and request.json.get('mark_completed'))):
            enrollment_section.completed = True
            enrollment_section.completed_at = datetime.utcnow()
            db.session.commit()

            # Find next section ID for auto-progression
            next_section_id = None
            for idx, sec in enumerate(ordered_sections):
                if sec.id == section_id and idx + 1 < len(ordered_sections):
                    next_section_id = ordered_sections[idx + 1].id
                    break

            # Check if the entire course is completed
            all_sections = Section.query.filter_by(course_id=course.id).all()
            all_enrollment_sections = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
            is_course_completed = all(es.completed for es in all_enrollment_sections) and len(all_enrollment_sections) == len(all_sections)
            if is_course_completed:
                enrollment.completed = True
                enrollment.completed_at = datetime.utcnow()
                db.session.commit()
                flash('🎉 Congratulations! You completed the course! Check your certificates.', 'success')

            # Render target section: Next Section if available, else current section
            target_section = Section.query.get(next_section_id) if next_section_id else section
            target_es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=target_section.id).first()
            if not target_es:
                target_es = EnrollmentSection(enrollment_id=enrollment.id, section_id=target_section.id)
                db.session.add(target_es)
                db.session.commit()

            interactive_questions = []
            subtitles = []
            if target_section.section_type == 'video' or target_section.video_url or (target_section.media_file and target_section.media_file.endswith(('.mp4', '.webm', '.ogg'))):
                interactive_questions = VideoInteractiveQuestion.query.filter_by(section_id=target_section.id).order_by(VideoInteractiveQuestion.timestamp).all()
                subtitles = target_section.subtitles if hasattr(target_section, 'subtitles') else []
            
            resp = make_response(render_template('student/_section_content.html', 
                                 section=target_section, 
                                 course=course, 
                                 enrollment_section=target_es,
                                 interactive_questions=interactive_questions,
                                 subtitles=subtitles))
            
            import json
            trigger_payload = {
                'sectionCompleted': {
                    'section_id': section_id,
                    'sectionId': section_id,
                    'next_section_id': next_section_id,
                    'nextSectionId': next_section_id,
                    'is_course_completed': is_course_completed,
                    'isCourseCompleted': is_course_completed
                }
            }
            if is_course_completed:
                trigger_payload['course-completed'] = True

            resp.headers['HX-Trigger'] = json.dumps(trigger_payload)
            if next_section_id:
                resp.headers['HX-Push-Url'] = url_for('student.course_detail', course_id=course.id, section_id=next_section_id)
            return resp
    elif current_user.role == 'admin' or (current_user.role == 'teacher' and course.teacher_id == current_user.id):
        # Admin or Course Teacher is allowed
        enrollment_section = None
    else:
        # Unauthorized role or other teacher
        abort(403)

    # Get interactive questions and subtitles for video sections
    interactive_questions = []
    subtitles = []
    if section.section_type == 'video' or section.video_url or (section.media_file and section.media_file.endswith(('.mp4', '.webm', '.ogg'))):
        interactive_questions = VideoInteractiveQuestion.query.filter_by(section_id=section_id).order_by(VideoInteractiveQuestion.timestamp).all()
        subtitles = section.subtitles if hasattr(section, 'subtitles') else []
    
    return render_template('student/_section_content.html', 
                         section=section, 
                         course=course, 
                         enrollment_section=enrollment_section,
                         interactive_questions=interactive_questions,
                         subtitles=subtitles)

@student_bp.route('/section/<int:section_id>/assignment/<int:assignment_id>/submit', methods=['GET', 'POST'])
@login_required
def submit_assignment(section_id, assignment_id):
    # Teachers and admins can preview — redirect them back to the course reader
    if current_user.role in ('teacher', 'admin'):
        section = Section.query.get_or_404(section_id)
        flash('You are previewing as a teacher. Log in as a student to submit assignments.', 'info')
        return redirect(url_for('student.course_detail', course_id=section.course_id))

    if current_user.role != 'student':
        abort(403)

    section = Section.query.get_or_404(section_id)
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.section_id != section_id or not student_enrolled(section.course_id):
        abort(403)
    
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        abort(403)
    
    # Fetch all submissions for assignment (supports up to 3 tries with full audit history)
    all_submissions = AssignmentSubmission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).order_by(AssignmentSubmission.submitted_at.desc()).all()
    
    max_attempts = getattr(assignment, 'max_attempts', None) or 3
    attempt_count = len(all_submissions)
    existing_submission = all_submissions[0] if all_submissions else None
    
    # Calculate best grade across all submissions
    graded_scores = [s.grade for s in all_submissions if s.grade is not None]
    best_grade = max(graded_scores) if graded_scores else None
    
    form = SubmissionForm()

    if request.method == 'POST':
        if attempt_count >= max_attempts:
            flash(f'You have reached the maximum limit of {max_attempts} attempts for this assignment.', 'warning')
            return redirect(url_for('student.course_detail', course_id=section.course_id))

        try:
            file_path = None
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                if file and allowed_file(file.filename):
                    # 1. Save file locally first
                    filename = secure_filename(f"{uuid4().hex}{os.path.splitext(file.filename)[1]}")
                    local_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(local_path)
                    file_path = filename

                    # 2. Upload to Cloudinary if configured
                    try:
                        with open(local_path, 'rb') as f:
                            from app.utils.cloudinary_helper import upload_file_to_cloudinary
                            cloudinary_url = upload_file_to_cloudinary(f, filename=file.filename, folder="pace_assignments")
                            if cloudinary_url:
                                file_path = cloudinary_url
                    except Exception as cloud_err:
                        logger.warning(f"Cloudinary upload fallback to local storage: {cloud_err}")
                else:
                    flash('Invalid file format. Allowed formats: .zip, .pdf, .docx, .png, .jpg, .txt, .py, .js, .html, etc.', 'danger')
                    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission, submissions=all_submissions, attempt_count=attempt_count, max_attempts=max_attempts, best_grade=best_grade)

            new_attempt_number = attempt_count + 1

            # Code assignment logic
            if assignment.is_coding_assignment:
                code = request.form.get('code_submission', '').strip()
                if not code and not file_path:
                    flash('Please write code or upload a code file before submitting.', 'danger')
                    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission, submissions=all_submissions, attempt_count=attempt_count, max_attempts=max_attempts, best_grade=best_grade)

                submission = AssignmentSubmission(
                    assignment_id=assignment_id,
                    student_id=current_user.id,
                    attempt_number=new_attempt_number,
                    submission_text=code if not file_path else 'Code File Upload',
                    file_path=file_path,
                    submission_type='code',
                    code_submission=code if code else None,
                    programming_language=assignment.programming_language
                )
                db.session.add(submission)
            else:
                # Regular assignment logic
                sub_text = (request.form.get('submission_text') or '').strip()
                if not sub_text and not file_path:
                    flash('Please provide submission text or attach a file.', 'warning')
                    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission, submissions=all_submissions, attempt_count=attempt_count, max_attempts=max_attempts, best_grade=best_grade)

                submission = AssignmentSubmission(
                    assignment_id=assignment_id,
                    student_id=current_user.id,
                    attempt_number=new_attempt_number,
                    submission_text=sub_text if sub_text else (file_path.split('/')[-1] if file_path else 'File Submission'),
                    file_path=file_path,
                    submission_type='file' if file_path else 'text'
                )
                db.session.add(submission)

            # Auto-mark section as completed upon assignment submission
            es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
            if not es:
                es = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
                db.session.add(es)
            es.completed = True
            es.completed_at = datetime.utcnow()

            db.session.commit()
            flash(f'Assignment Attempt {new_attempt_number} of {max_attempts} submitted successfully!', 'success')
            return redirect(url_for('student.course_detail', course_id=section.course_id))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error submitting assignment: {e}", exc_info=True)
            flash(f'An unexpected error occurred during submission: {str(e)}', 'danger')
            return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission, submissions=all_submissions, attempt_count=attempt_count, max_attempts=max_attempts, best_grade=best_grade)

    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission, submissions=all_submissions, attempt_count=attempt_count, max_attempts=max_attempts, best_grade=best_grade)

@student_bp.route('/section/<int:section_id>/quiz/<int:quiz_id>/take', methods=['GET', 'POST'])
@login_required
@student_required
def take_quiz(section_id, quiz_id):
    section = Section.query.get_or_404(section_id)
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.section_id != section_id or not student_enrolled(section.course_id):
        abort(403)
    
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        abort(403)
    
    questions = QuizQuestion.query.filter_by(quiz_id=quiz_id).all()
    if not questions:
        flash('No questions available in this quiz.', 'danger')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    
    all_attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id, student_id=current_user.id).order_by(QuizAttempt.attempted_at.desc()).all()
    attempt_count = len(all_attempts)
    max_attempts = quiz.max_attempts if quiz.max_attempts else 3
    best_score = max([a.score for a in all_attempts]) if all_attempts else None
    
    if attempt_count >= max_attempts:
        flash(f'You have reached the maximum of {max_attempts} attempts for this quiz.', 'warning')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    
    if request.method == 'POST':
        score = 0
        total = len(questions)
        for q in questions:
            user_answer = request.form.get(f'q{q.id}')
            if user_answer and user_answer == q.correct_answer:
                score += 1
        
        attempt_percentage = (score / total) * 100
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=current_user.id,
            score=attempt_percentage
        )
        db.session.add(attempt)

        # Auto-mark section as completed upon quiz submission
        es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
        if not es:
            es = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
            db.session.add(es)
        es.completed = True
        es.completed_at = datetime.utcnow()

        db.session.commit()
        
        # Calculate updated best score including this attempt
        updated_attempts = QuizAttempt.query.filter_by(quiz_id=quiz_id, student_id=current_user.id).all()
        updated_best_score = max([a.score for a in updated_attempts]) if updated_attempts else attempt_percentage
        
        return render_template('student/quiz_results.html', 
                               quiz=quiz, 
                               section=section, 
                               score=score, 
                               total=total, 
                               percentage=attempt_percentage,
                               attempt_number=len(updated_attempts),
                               max_attempts=max_attempts,
                               attempts=updated_attempts,
                               best_score=updated_best_score)
    return render_template('student/take_quiz.html', quiz=quiz, questions=questions, section=section, attempts=all_attempts, attempt_count=attempt_count, max_attempts=max_attempts, best_score=best_score)

@student_bp.route('/section/<int:section_id>/mark-completed', methods=['POST'])
@login_required
def mark_section_completed(section_id):
    if current_user.role != 'student':
        return "Unauthorized", 403
    
    section = Section.query.get_or_404(section_id)
    if not student_enrolled(section.course_id):
        return "Not enrolled or course not approved", 403
    
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        return "Not enrolled", 403
    
    es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not es:
        es = EnrollmentSection(
            enrollment_id=enrollment.id,
            section_id=section_id,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(es)
    else:
        es.completed = True
        es.completed_at = datetime.utcnow()
    
    # Check if all sections are completed to mark course as complete
    all_sections = Section.query.filter_by(course_id=section.course_id).all()
    all_enrollment_sections = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
    if all(es_item.completed for es_item in all_enrollment_sections) and len(all_enrollment_sections) == len(all_sections):
        enrollment.completed = True
        enrollment.completed_at = datetime.utcnow()
    
    db.session.commit()
    return "Section marked as completed", 200

@student_bp.route('/view-pdf/<int:section_id>')
@login_required
def view_pdf(section_id):
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    
    section = Section.query.get_or_404(section_id)
    if not student_enrolled(section.course_id):
        abort(403)
    
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        abort(403)
    
    es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not es:
        es = EnrollmentSection(
            enrollment_id=enrollment.id,
            section_id=section_id,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(es)
    else:
        es.completed = True
        es.completed_at = datetime.utcnow()
    
    db.session.commit()
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], section.content)

@student_bp.route('/course/<int:course_id>/rate', methods=['POST'])
@login_required
@student_required
def rate_course(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first_or_404()
    if all(es.completed for es in enrollment.sections):
        rating = request.form.get('rating')
        comment = request.form.get('comment', '')
        if rating and 0 <= float(rating) <= 5:
            new_rating = Rating(
                course_id=course_id,
                user_id=current_user.id,
                rating=float(rating),
                comment=comment,
                rated_at=datetime.utcnow()
            )
            db.session.add(new_rating)
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Thank you for your feedback!'})
        return jsonify({'status': 'error', 'message': 'Please provide a valid rating between 0 and 5.'}), 400
    return jsonify({'status': 'error', 'message': 'Course not completed.'}), 403

@student_bp.route('/course/<int:course_id>/ratings')
@login_required
@admin_required
def view_ratings(course_id):
    course = Course.query.get_or_404(course_id)
    ratings = Rating.query.filter_by(course_id=course_id).all()
    return render_template('admin/course_ratings.html', course=course, ratings=ratings)

def generate_certificate_pdf(output_dest, course, student_name, completion_date=None, certificate_id=None, instructor_name=None):
    """
    Generates an executive, co-branded landscape certificate PDF for a course.
    output_dest: file path or BytesIO stream
    course: Course instance
    student_name: str
    completion_date: str or None
    certificate_id: str or None
    instructor_name: str or None
    """
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    import io, requests

    if not completion_date:
        completion_date = datetime.utcnow().strftime('%B %d, %Y')
    if not certificate_id:
        certificate_id = f"CERT-{course.id}-{int(datetime.utcnow().timestamp())}"

    # Setup page geometry (Landscape Letter: 792 x 612)
    width, height = landscape(letter)
    c = canvas.Canvas(output_dest, pagesize=landscape(letter))

    # Theme Palettes
    theme = getattr(course, 'certificate_theme', 'gold') or 'gold'
    themes = {
        'gold': {
            'primary': HexColor('#B8860B'),       # Rich Dark Gold
            'secondary': HexColor('#D4AF37'),     # Warm Gold
            'accent': HexColor('#1E3A8A'),        # Royal Blue
            'border_outer': HexColor('#D4AF37'),
            'border_inner': HexColor('#B8860B'),
            'title_color': HexColor('#B8860B'),
            'name_box_bg': HexColor('#FDFCFA'),
            'name_box_border': HexColor('#E5D5A5'),
            'name_text': HexColor('#1E3A8A'),
            'seal_bg': HexColor('#FFD700'),
            'seal_border': HexColor('#B8860B'),
            'subtext': HexColor('#4B5563')
        },
        'navy': {
            'primary': HexColor('#1E3A8A'),       # Deep Navy
            'secondary': HexColor('#2563EB'),     # Electric Blue
            'accent': HexColor('#3B82F6'),
            'border_outer': HexColor('#1E3A8A'),
            'border_inner': HexColor('#3B82F6'),
            'title_color': HexColor('#1E3A8A'),
            'name_box_bg': HexColor('#F8FAFC'),
            'name_box_border': HexColor('#93C5FD'),
            'name_text': HexColor('#1E3A8A'),
            'seal_bg': HexColor('#3B82F6'),
            'seal_border': HexColor('#1E3A8A'),
            'subtext': HexColor('#475569')
        },
        'emerald': {
            'primary': HexColor('#065F46'),       # Deep Emerald
            'secondary': HexColor('#059669'),     # Green
            'accent': HexColor('#D4AF37'),        # Gold accent
            'border_outer': HexColor('#059669'),
            'border_inner': HexColor('#D4AF37'),
            'title_color': HexColor('#065F46'),
            'name_box_bg': HexColor('#F0FDF4'),
            'name_box_border': HexColor('#86EFAC'),
            'name_text': HexColor('#065F46'),
            'seal_bg': HexColor('#10B981'),
            'seal_border': HexColor('#065F46'),
            'subtext': HexColor('#374151')
        },
        'dark': {
            'primary': HexColor('#111827'),       # Charcoal Black
            'secondary': HexColor('#4F46E5'),     # Indigo
            'accent': HexColor('#6366F1'),
            'border_outer': HexColor('#1F2937'),
            'border_inner': HexColor('#4F46E5'),
            'title_color': HexColor('#111827'),
            'name_box_bg': HexColor('#F9FAFB'),
            'name_box_border': HexColor('#CBD5E1'),
            'name_text': HexColor('#111827'),
            'seal_bg': HexColor('#4F46E5'),
            'seal_border': HexColor('#1F2937'),
            'subtext': HexColor('#4B5563')
        },
        'burgundy': {
            'primary': HexColor('#831843'),       # Deep Burgundy
            'secondary': HexColor('#BE185D'),     # Crimson Rose
            'accent': HexColor('#D4AF37'),        # Gold
            'border_outer': HexColor('#831843'),
            'border_inner': HexColor('#D4AF37'),
            'title_color': HexColor('#831843'),
            'name_box_bg': HexColor('#FFF1F2'),
            'name_box_border': HexColor('#FECDD3'),
            'name_text': HexColor('#831843'),
            'seal_bg': HexColor('#BE185D'),
            'seal_border': HexColor('#831843'),
            'subtext': HexColor('#4B5563')
        }
    }
    palette = themes.get(theme, themes['gold'])

    # Helper to load and draw images with true centered aspect ratio scaling
    def draw_image_safe(src, x, y, max_w, max_h):
        if not src:
            return False
        try:
            from PIL import Image as PILImage
            reader = None
            orig_w, orig_h = None, None
            
            if src.startswith('data:image'):
                import base64
                header, encoded = src.split(',', 1)
                img_data = base64.b64decode(encoded)
                pil_img = PILImage.open(io.BytesIO(img_data))
                orig_w, orig_h = pil_img.size
                stream = io.BytesIO(img_data)
                reader = ImageReader(stream)
            elif src.startswith(('http://', 'https://')):
                res = requests.get(src, timeout=3)
                if res.status_code == 200:
                    pil_img = PILImage.open(io.BytesIO(res.content))
                    orig_w, orig_h = pil_img.size
                    stream = io.BytesIO(res.content)
                    reader = ImageReader(stream)
            else:
                local_f = os.path.join(current_app.config['UPLOAD_FOLDER'], src)
                if not os.path.exists(local_f):
                    local_f = os.path.join(current_app.root_path, 'static', src)
                if os.path.exists(local_f):
                    pil_img = PILImage.open(local_f)
                    orig_w, orig_h = pil_img.size
                    reader = ImageReader(local_f)

            if reader and orig_w and orig_h:
                aspect = orig_w / orig_h
                box_aspect = max_w / max_h
                if box_aspect > aspect:
                    render_h = max_h
                    render_w = max_h * aspect
                else:
                    render_w = max_w
                    render_h = max_w / aspect
                
                # Perfect horizontal and vertical centering inside bounding box
                render_x = x + (max_w - render_w) / 2
                render_y = y + (max_h - render_h) / 2
                c.drawImage(reader, render_x, render_y, width=render_w, height=render_h, mask='auto')
                return True
        except Exception as e:
            logger.warning(f"Failed to draw image on certificate: {e}")
        return False

    # Helper to render a perfectly aligned signature block
    def draw_signature_block(center_x, baseline_y, label, signatory_name, signatory_title, sig_src=None):
        # 1. Top Section Label
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(HexColor('#6B7280'))
        c.drawCentredString(center_x, baseline_y + 40, label.upper())

        # 2. Signature Drawing (Image or Cursive Fallback)
        if sig_src:
            sig_box_w = 130
            sig_box_h = 36
            draw_image_safe(sig_src, center_x - (sig_box_w / 2), baseline_y + 2, sig_box_w, sig_box_h)
        else:
            c.setFont("Helvetica-Oblique", 11)
            c.setFillColor(HexColor('#1E3A8A'))
            c.drawCentredString(center_x, baseline_y + 8, signatory_name)

        # 3. Horizontal Line
        c.setStrokeColor(HexColor('#4B5563'))
        c.setLineWidth(0.8)
        c.line(center_x - 80, baseline_y, center_x + 80, baseline_y)

        # 4. Printed Signatory Name
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(HexColor('#111827'))
        c.drawCentredString(center_x, baseline_y - 14, signatory_name)

        # 5. Designation / Title
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor('#6B7280'))
        c.drawCentredString(center_x, baseline_y - 25, signatory_title)

    # 1. Background Fill (Soft tint)
    c.setFillColor(HexColor('#FFFFFF'))
    c.rect(0, 0, width, height, stroke=0, fill=1)

    # 2. Ornate Double Borders & Corner Highlights
    c.setStrokeColor(palette['border_outer'])
    c.setLineWidth(5)
    c.rect(22, 22, width - 44, height - 44, stroke=1, fill=0)

    c.setStrokeColor(palette['border_inner'])
    c.setLineWidth(1.5)
    c.rect(30, 30, width - 60, height - 60, stroke=1, fill=0)

    # Decorative Corner Ornaments
    c.setStrokeColor(palette['secondary'])
    c.setLineWidth(2.5)
    corner_len = 35
    # Top-Left
    c.line(30, height - 30, 30 + corner_len, height - 30)
    c.line(30, height - 30, 30, height - 30 - corner_len)
    # Top-Right
    c.line(width - 30 - corner_len, height - 30, width - 30, height - 30)
    c.line(width - 30, height - 30, width - 30, height - 30 - corner_len)
    # Bottom-Left
    c.line(30, 30, 30 + corner_len, 30)
    c.line(30, 30, 30, 30 + corner_len)
    # Bottom-Right
    c.line(width - 30 - corner_len, 30, width - 30, 30)
    c.line(width - 30, 30, width - 30, 30 + corner_len)

    # 3. Header & Dual Branding
    has_partner = bool(course.partner_name or course.partner_logo)
    
    # Try drawing partner logo on top-right if available
    if course.partner_logo:
        draw_image_safe(course.partner_logo, width - 150, height - 85, 100, 45)

    # Institution Names
    c.setFillColor(palette['primary'])
    c.setFont("Helvetica-Bold", 18)
    if has_partner and course.partner_name:
        c.drawCentredString(width / 2, height - 65, "PACE ACADEMY")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(palette['subtext'])
        c.drawCentredString(width / 2, height - 82, f"IN JOINT COLLABORATION WITH {course.partner_name.upper()}")
    else:
        c.drawCentredString(width / 2, height - 65, "PACE ACADEMY")
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(palette['subtext'])
        c.drawCentredString(width / 2, height - 82, "SKILLS & VOCATIONAL EDUCATION PLATFORM")

    # Accreditation / Qualification Ribbon (if present)
    accred_text = course.partner_accreditation_number or course.accreditation_name
    if accred_text:
        c.setFillColor(HexColor('#F3F4F6'))
        c.setStrokeColor(palette['border_inner'])
        c.setLineWidth(0.8)
        ribbon_w = min(500, max(260, len(accred_text) * 7 + 30))
        c.roundRect((width - ribbon_w) / 2, height - 110, ribbon_w, 20, 5, stroke=1, fill=1)
        c.setFillColor(palette['primary'])
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(width / 2, height - 103, f"★ ACCREDITATION / PROVIDER: {accred_text.upper()}")

    # 4. Certificate Title
    cert_title = (getattr(course, 'custom_certificate_title', None) or "CERTIFICATE OF COMPLETION").upper()
    c.setFillColor(palette['title_color'])
    c.setFont("Helvetica-Bold", 24)
    title_y = height - 145 if accred_text else height - 130
    c.drawCentredString(width / 2, title_y, cert_title)

    # Divider bar under title
    c.setStrokeColor(palette['secondary'])
    c.setLineWidth(1.5)
    c.line(width / 2 - 140, title_y - 12, width / 2 + 140, title_y - 12)

    # 5. Recipient Section
    c.setFillColor(HexColor('#4B5563'))
    c.setFont("Helvetica-Oblique", 13)
    c.drawCentredString(width / 2, title_y - 35, "This is to certify that")

    # Student Name Plaque
    plaque_w = 500
    plaque_h = 44
    plaque_x = (width - plaque_w) / 2
    plaque_y = title_y - 90
    c.setFillColor(palette['name_box_bg'])
    c.setStrokeColor(palette['name_box_border'])
    c.setLineWidth(1.2)
    c.roundRect(plaque_x, plaque_y, plaque_w, plaque_h, 8, stroke=1, fill=1)

    c.setFillColor(palette['name_text'])
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, plaque_y + 13, student_name)

    # 6. Course Award Description
    c.setFillColor(HexColor('#4B5563'))
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2, plaque_y - 22, "has successfully fulfilled all required coursework, assessments, and competencies in")

    c.setFillColor(palette['primary'])
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, plaque_y - 44, f'"{course.title}"')

    c.setFillColor(HexColor('#6B7280'))
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, plaque_y - 62, "Demonstrating dedication to vocational mastery, practical skills, and academic excellence.")

    # 7. Signatures & Certified Seal (Bottom Section)
    # Left: Official Seal & Date
    seal_x = 100
    seal_y = 110
    c.setStrokeColor(palette['seal_border'])
    c.setFillColor(palette['seal_bg'])
    c.setLineWidth(2)
    c.circle(seal_x, seal_y, 34, stroke=1, fill=1)

    c.setFillColor(HexColor('#FFFFFF'))
    c.circle(seal_x, seal_y, 29, stroke=0, fill=1)

    c.setFillColor(palette['primary'])
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(seal_x, seal_y + 6, "★ PACE ★")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(seal_x, seal_y - 4, "VERIFIED")
    c.setFont("Helvetica", 6)
    c.drawCentredString(seal_x, seal_y - 13, "ACCREDITED")

    # Date
    c.setFillColor(HexColor('#374151'))
    c.setFont("Helvetica", 9)
    c.drawString(60, 52, "Date of Issuance:")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, 40, completion_date)

    # Center: Primary Course Instructor Signatory
    if not instructor_name:
        if course.teacher:
            instructor_name = f"{course.teacher.first_name or ''} {course.teacher.last_name or ''}".strip() or course.teacher.username or course.teacher.email.split('@')[0]
        else:
            instructor_name = "Pace Academic Board"

    instructor_sig = getattr(course, 'instructor_signature', None)
    draw_signature_block(
        center_x=width / 2,
        baseline_y=95,
        label="Course Instructor",
        signatory_name=instructor_name,
        signatory_title="Lead Instructor / Educator",
        sig_src=instructor_sig
    )

    # Right: Partner Executive Signatory (if custom) OR Pace Curriculum Head (Adam Dono)
    right_x = width - 150
    if course.partner_signatory_name:
        sig_name = course.partner_signatory_name
        sig_title = course.partner_signatory_title or "Executive Director"
        sig_org = f"{sig_title} · {course.partner_name}" if course.partner_name else sig_title
        sig_src = getattr(course, 'partner_signatory_signature', None)
    else:
        sig_name = "Adam Dono"
        sig_org = "Head of Curriculum · Pace Academy"
        sig_src = getattr(course, 'partner_signatory_signature', None)

    draw_signature_block(
        center_x=right_x,
        baseline_y=95,
        label="Authorized Signatory",
        signatory_name=sig_name,
        signatory_title=sig_org,
        sig_src=sig_src
    )

    # 8. Bottom Verification Footer
    c.setFillColor(HexColor('#9CA3AF'))
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 34, f"Certificate ID: {certificate_id}  ·  Verify at pace-academy.co.za")

    c.save()
    return True

@student_bp.route('/generate_certificate/<int:enrollment_id>', methods=['POST'])
@login_required
@student_required
def generate_certificate(enrollment_id):
    logger.debug(f"Generating certificate for enrollment_id: {enrollment_id}")
    if enrollment_id == 0:
        enrollment_id = request.form.get('enrollment_id', type=int) or 0
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != current_user.id:
        logger.warning(f"Unauthorized certificate request for enrollment_id: {enrollment_id}")
        return jsonify({'status': 'error', 'message': 'Unauthorized access.'})

    # Ensure rating exists so generation is never blocked
    existing_rating = Rating.query.filter_by(course_id=enrollment.course_id, user_id=current_user.id).first()
    if not existing_rating:
        new_rating = Rating(
            course_id=enrollment.course_id,
            user_id=current_user.id,
            rating=5.0,
            comment="Completed course"
        )
        db.session.add(new_rating)
        db.session.commit()

    user_name = f"{current_user.first_name} {current_user.last_name}" if (current_user.first_name and current_user.last_name) else (current_user.username or current_user.email.split('@')[0])
    certificate_filename = f"certificate_{enrollment.id}_{int(datetime.utcnow().timestamp())}.pdf"
    certificate_path = os.path.join(current_app.config['UPLOAD_FOLDER'], certificate_filename)

    # Generate Landscape Certificate PDF
    generate_certificate_pdf(
        output_dest=certificate_path,
        course=enrollment.course,
        student_name=user_name,
        completion_date=datetime.utcnow().strftime('%B %d, %Y'),
        certificate_id=f"CERT-{enrollment.id}-{int(datetime.utcnow().timestamp())}"
    )

    enrollment.certificate_path = certificate_filename
    db.session.commit()
    logger.info(f"Certificate generated successfully for enrollment_id: {enrollment_id}")
    flash('Certificate generated successfully!', 'success')
    
    # Redirect to download the certificate immediately
    return redirect(url_for('student.serve_certificate', enrollment_id=enrollment_id))

@student_bp.route('/serve_certificate/<int:enrollment_id>')
@login_required
@student_required
def serve_certificate(enrollment_id):
    logger.debug(f"Serving certificate for enrollment_id: {enrollment_id}")
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != current_user.id or not enrollment.certificate_path:
        logger.warning(f"Unauthorized or no certificate for enrollment_id: {enrollment_id}")
        abort(403)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], enrollment.certificate_path, as_attachment=True)

@student_bp.route('/track-time/<int:section_id>', methods=['POST'])
@login_required
def track_time(section_id):
    """Track time spent on a section (AJAX endpoint)"""
    # Teachers/admins previewing — silently succeed without writing a record
    if current_user.role != 'student':
        return jsonify({'success': True, 'total_time': 0})
    try:
        data = request.get_json()
        time_spent = data.get('time_spent', 0)  # in seconds
        
        # Find the enrollment and section
        section = Section.query.get_or_404(section_id)
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.id,
            course_id=section.course_id
        ).first_or_404()
        
        # Find or create enrollment section
        enrollment_section = EnrollmentSection.query.filter_by(
            enrollment_id=enrollment.id,
            section_id=section_id
        ).first()
        
        if not enrollment_section:
            enrollment_section = EnrollmentSection(
                enrollment_id=enrollment.id,
                section_id=section_id
            )
            db.session.add(enrollment_section)
        
        # Update time spent (cumulative)
        enrollment_section.time_spent = (enrollment_section.time_spent or 0) + time_spent
        enrollment_section.last_accessed = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'total_time': enrollment_section.time_spent
        })
    except Exception as e:
        logger.error(f"Error tracking time for section {section_id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/profile', methods=['GET', 'POST'])
@student_required
def profile():
    form = ProfileForm()
    
    if request.method == 'POST':
        curr_pwd = (request.form.get('current_password') or form.current_password.data or '').strip()
        new_pwd = (request.form.get('new_password') or form.new_password.data or '').strip()
        confirm_pwd = (request.form.get('confirm_password') or form.confirm_password.data or '').strip()
        
        # Explicit password change handling
        password_changed = False
        if new_pwd:
            if not curr_pwd:
                flash('Please enter your Current Password to update your password.', 'danger')
                return render_template('student/profile.html', form=form)
            if not current_user.verify_password(curr_pwd):
                flash('Current password is incorrect.', 'danger')
                return render_template('student/profile.html', form=form)
            if len(new_pwd) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return render_template('student/profile.html', form=form)
            if new_pwd != confirm_pwd:
                flash('New password and confirm password do not match.', 'danger')
                return render_template('student/profile.html', form=form)
            
            current_user.password = new_pwd
            password_changed = True
        
        # Update other profile fields
        username_val = (request.form.get('username') or form.username.data or current_user.username).strip()
        email_val = (request.form.get('email') or form.email.data or current_user.email).strip()
        
        if email_val != current_user.email:
            existing_user = User.query.filter_by(email=email_val).first()
            if existing_user:
                flash('Email is already in use by another account.', 'danger')
                return render_template('student/profile.html', form=form)
        
        if username_val != current_user.username:
            existing_user = User.query.filter_by(username=username_val).first()
            if existing_user:
                flash('Username is already in use.', 'danger')
                return render_template('student/profile.html', form=form)
        
        current_user.username = username_val
        current_user.email = email_val
        current_user.bio = request.form.get('bio', current_user.bio or '')
        current_user.contact = request.form.get('contact', current_user.contact or '')
        current_user.first_name = request.form.get('first_name', current_user.first_name or '')
        current_user.last_name = request.form.get('last_name', current_user.last_name or '')
        current_user.specialization = request.form.get('specialization', current_user.specialization or '')
        
        # Handle profile image upload
        file = request.files.get('profile_image')
        if file and file.filename:
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
            if ext in allowed:
                from app.utils.cloudinary_helper import upload_file_to_cloudinary
                cloudinary_url = upload_file_to_cloudinary(file, filename=file.filename, folder="pace_avatars")
                if cloudinary_url:
                    current_user.profile_image = cloudinary_url
                else:
                    new_name = f"avatar_student_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
                    file.save(save_path)
                    current_user.profile_image = new_name
        
        db.session.commit()
        if password_changed:
            flash('Profile and password updated successfully! 🔐', 'success')
        else:
            flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.profile'))
    
    # Pre-populate form with current user data
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
        form.contact.data = current_user.contact
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.specialization.data = current_user.specialization
    
    return render_template('student/profile.html', form=form)

# ===== VIDEO FEATURES =====

@student_bp.route('/video-progress/<int:section_id>', methods=['GET', 'POST'])
@login_required
@student_required
def video_progress(section_id):
    """Save or retrieve video watch progress"""
    section = Section.query.get_or_404(section_id)
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=section.course_id
    ).first_or_404()
    
    enrollment_section = EnrollmentSection.query.filter_by(
        enrollment_id=enrollment.id,
        section_id=section_id
    ).first()
    
    if not enrollment_section:
        enrollment_section = EnrollmentSection(
            enrollment_id=enrollment.id,
            section_id=section_id
        )
        db.session.add(enrollment_section)
        db.session.commit()
    
    if request.method == 'POST':
        # Save video progress
        data = request.get_json()
        
        progress = VideoWatchProgress.query.filter_by(
            enrollment_section_id=enrollment_section.id,
            section_id=section_id,
            student_id=current_user.id
        ).first()
        
        if not progress:
            progress = VideoWatchProgress(
                enrollment_section_id=enrollment_section.id,
                section_id=section_id,
                student_id=current_user.id
            )
            db.session.add(progress)
        
        # Update progress
        curr_time = float(data.get('current_time') or 0)
        dur = float(data.get('duration') or 0)
        pct = float(data.get('watch_percentage') or 0)
        
        progress.video_current_time = curr_time
        if dur > 0:
            progress.duration = dur
        progress.watch_percentage = max(progress.watch_percentage or 0, round(pct, 1))
        
        # Calculate/accumulate real total watch time in seconds
        watch_time_input = float(data.get('total_watch_time') or 0)
        if watch_time_input > 0:
            progress.total_watch_time = max(progress.total_watch_time or 0, watch_time_input)
        elif curr_time > 0:
            progress.total_watch_time = max(progress.total_watch_time or 0, curr_time)
            
        progress.playback_speed = float(data.get('playback_speed') or 1.0)
        progress.play_count = max(progress.play_count or 1, int(data.get('play_count') or 1))
        progress.last_watched = datetime.utcnow()
        
        # Mark as completed if watched >= 85%
        if progress.watch_percentage >= 85:
            progress.completed = True
            if not enrollment_section.completed:
                enrollment_section.completed = True
                enrollment_section.completed_at = datetime.utcnow()
                
                # Check if all sections are completed to mark course as complete
                section = Section.query.get(section_id)
                enrollment = Enrollment.query.filter_by(
                    student_id=current_user.id,
                    course_id=section.course_id
                ).first()
                
                if enrollment:
                    all_sections = Section.query.filter_by(course_id=section.course_id).all()
                    all_enrollment_sections = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
                    if all(es.completed for es in all_enrollment_sections) and len(all_enrollment_sections) == len(all_sections):
                        enrollment.completed = True
                        enrollment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'watch_percentage': progress.watch_percentage,
            'completed': progress.completed
        })
    
    else:
        # GET: Retrieve saved progress
        progress = VideoWatchProgress.query.filter_by(
            enrollment_section_id=enrollment_section.id,
            section_id=section_id,
            student_id=current_user.id
        ).first()
        
        if progress:
            return jsonify({
                'current_time': progress.video_current_time,
                'duration': progress.duration,
                'watch_percentage': progress.watch_percentage,
                'total_watch_time': progress.total_watch_time,
                'play_count': progress.play_count,
                'playback_speed': progress.playback_speed
            })
        else:
            return jsonify({
                'current_time': 0,
                'duration': 0,
                'watch_percentage': 0,
                'total_watch_time': 0,
                'play_count': 0,
                'playback_speed': 1.0
            })

@student_bp.route('/video-question/respond', methods=['POST'])
@login_required
@student_required
def respond_video_question():
    """Submit response to interactive video question"""
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        selected_answer = data.get('selected_answer')
        is_correct = data.get('is_correct')
        
        question = VideoInteractiveQuestion.query.get_or_404(question_id)
        
        # Check if already answered
        existing_response = VideoQuestionResponse.query.filter_by(
            question_id=question_id,
            student_id=current_user.id
        ).first()
        
        if existing_response:
            # Update existing response
            existing_response.selected_answer = selected_answer
            existing_response.is_correct = is_correct
            existing_response.answered_at = datetime.utcnow()
        else:
            # Create new response
            response = VideoQuestionResponse(
                question_id=question_id,
                student_id=current_user.id,
                selected_answer=selected_answer,
                is_correct=is_correct
            )
            db.session.add(response)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'is_correct': is_correct
        })
    
    except Exception as e:
        logger.error(f"Error submitting video question response: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== NEW SIDEBAR ROUTES =====

@student_bp.route('/assignments')
@login_required
@student_required
def assignments():
    """View all assignments across enrolled courses"""
    from sqlalchemy import or_
    
    # Get all assignments for enrolled courses
    enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).join(Course).filter(Course.status == 'approved').all()]
    
    assignments = Assignment.query.join(Section).filter(
        Section.course_id.in_(enrolled_course_ids)
    ).order_by(Assignment.due_date.asc()).all()
    
    # Categorize assignments
    pending = []
    submitted = []
    graded = []
    
    for assignment in assignments:
        submission = AssignmentSubmission.query.filter_by(
            assignment_id=assignment.id,
            student_id=current_user.id
        ).first()
        
        if submission:
            if submission.grade is not None:
                graded.append({'assignment': assignment, 'submission': submission})
            else:
                submitted.append({'assignment': assignment, 'submission': submission})
        else:
            pending.append({'assignment': assignment, 'submission': None})
    
    return render_template('student/assignments.html',
                         pending=pending,
                         submitted=submitted,
                         graded=graded)

@student_bp.route('/certificates')
@login_required
@student_required
def certificates():
    """View all earned certificates"""
    # Get all enrollments (completed flag OR 100% section progress)
    all_enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()

    certificates = []
    for enrollment in all_enrollments:
        course = Course.query.get(enrollment.course_id)
        if not course:
            continue

        # Check completion: either flag is True, or all sections are done
        is_completed = enrollment.completed
        if not is_completed:
            all_sections = Section.query.filter_by(course_id=course.id).all()
            if all_sections:
                completed_sections = EnrollmentSection.query.filter_by(
                    enrollment_id=enrollment.id, completed=True
                ).count()
                if completed_sections >= len(all_sections):
                    # Auto-heal the flag so future checks are fast
                    enrollment.completed = True
                    enrollment.completed_at = enrollment.completed_at or datetime.utcnow()
                    db.session.commit()
                    is_completed = True

        if is_completed:
            certificates.append({
                'enrollment': enrollment,
                'course': course,
                'has_certificate': bool(enrollment.certificate_path),
                'completed_at': enrollment.completed_at
            })

    return render_template('student/certificates.html', certificates=certificates)

@student_bp.route('/calendar')
@login_required
@student_required
def calendar():
    """Calendar view of all deadlines"""
    from datetime import datetime, timedelta
    
    enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).all()]
    
    # Get all assignments with due dates
    assignments = Assignment.query.join(Section).filter(
        Section.course_id.in_(enrolled_course_ids),
        Assignment.due_date.isnot(None)
    ).order_by(Assignment.due_date).all()
    
    # Group by date
    calendar_data = {}
    today = datetime.utcnow().date()
    
    for assignment in assignments:
        date_key = assignment.due_date.date()
        if date_key not in calendar_data:
            calendar_data[date_key] = {
                'date': date_key,
                'assignments': [],
                'is_past': date_key < today,
                'is_today': date_key == today
            }
        calendar_data[date_key]['assignments'].append(assignment)
    
    calendar_items = sorted(calendar_data.values(), key=lambda x: x['date'])
    
    return render_template('student/calendar.html', calendar_items=calendar_items)

@student_bp.route('/announcements')
@login_required
@student_required
def announcements():
    """View all course announcements"""
    from app.models import Announcement
    
    enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).all()]
    
    announcements = Announcement.query.filter(
        Announcement.course_id.in_(enrolled_course_ids)
    ).order_by(Announcement.created_at.desc()).all()
    
    return render_template('student/announcements.html', announcements=announcements)

@student_bp.route('/notifications')
@login_required
@student_required
def notifications_list():
    """View all notifications"""
    from app.models import Notification
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    return render_template('student/notifications.html', notifications=notifications)

@student_bp.route('/help')
@login_required
@student_required
def help():
    return render_template('student/help.html')

@student_bp.route('/grades')
@login_required
@student_required
def grades():
    """Student gradebook showing all grades across enrolled courses"""
    # Get all enrolled courses
    enrolled_courses = Course.query.join(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Course.status == 'approved'
    ).all()
    
    grade_data = []
    
    for course in enrolled_courses:
        # Get assignments and quizzes for this course
        assignments = Assignment.query.join(Section).filter(Section.course_id == course.id).all()
        quizzes = Quiz.query.join(Section).filter(Section.course_id == course.id).all()
        
        # Get student's submissions across all attempts (highest grade considered)
        assignment_grades = []
        for assignment in assignments:
            submissions = AssignmentSubmission.query.filter_by(
                assignment_id=assignment.id,
                student_id=current_user.id
            ).order_by(AssignmentSubmission.submitted_at.desc()).all()
            
            graded_scores = [s.grade for s in submissions if s.grade is not None]
            best_grade = max(graded_scores) if graded_scores else None
            latest_sub = submissions[0] if submissions else None
            
            assignment_grades.append({
                'assignment': assignment,
                'submission': latest_sub,
                'submissions': submissions,
                'grade': best_grade,
                'best_grade': best_grade,
                'status': 'graded' if graded_scores else 'submitted' if submissions else 'not_submitted'
            })
        
        # Get quiz attempts
        quiz_grades = []
        for quiz in quizzes:
            attempts = QuizAttempt.query.filter_by(
                quiz_id=quiz.id,
                student_id=current_user.id
            ).order_by(QuizAttempt.attempted_at.desc()).all()
            
            best_score = max([a.score for a in attempts]) if attempts else None
            
            quiz_grades.append({
                'quiz': quiz,
                'attempts': attempts,
                'best_score': best_score,
                'status': 'completed' if attempts else 'not_attempted'
            })
        
        # Calculate course average
        assignment_scores = [g['grade'] for g in assignment_grades if g['grade'] is not None]
        quiz_scores = [g['best_score'] for g in quiz_grades if g['best_score'] is not None]
        
        assignment_avg = sum(assignment_scores) / len(assignment_scores) if assignment_scores else None
        quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else None
        
        # Overall grade (60% assignments, 40% quizzes)
        overall_grade = None
        if assignment_avg is not None or quiz_avg is not None:
            overall_grade = (assignment_avg or 0) * 0.6 + (quiz_avg or 0) * 0.4
        
        grade_data.append({
            'course': course,
            'assignment_grades': assignment_grades,
            'quiz_grades': quiz_grades,
            'assignment_avg': round(assignment_avg, 1) if assignment_avg else None,
            'quiz_avg': round(quiz_avg, 1) if quiz_avg else None,
            'overall_grade': round(overall_grade, 1) if overall_grade else None,
            'total_assignments': len(assignments),
            'graded_assignments': sum(1 for g in assignment_grades if g['status'] == 'graded'),
            'total_quizzes': len(quizzes),
            'attempted_quizzes': sum(1 for g in quiz_grades if g['status'] == 'completed')
        })
    
    # Calculate overall GPA
    all_grades = [g['overall_grade'] for g in grade_data if g['overall_grade'] is not None]
    overall_gpa = sum(all_grades) / len(all_grades) if all_grades else None
    
    return render_template('student/grades.html',
                         grade_data=grade_data,
                         overall_gpa=round(overall_gpa, 1) if overall_gpa else None)


@student_bp.route('/live-classrooms')
@login_required
@student_required
def live_classrooms():
    """Student view of upcoming, active live video classrooms for enrolled courses"""
    from app.models import LiveSession, Enrollment, Course
    from datetime import datetime, timedelta

    # Auto-expire stale live sessions
    now = datetime.utcnow()
    stale_sessions = LiveSession.query.filter_by(status='live').all()
    for s in stale_sessions:
        start_ref = s.started_at or s.scheduled_at
        if start_ref and now > (start_ref + timedelta(minutes=s.duration_minutes or 60)):
            s.status = 'ended'
            s.ended_at = now
    db.session.commit()
    
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    enrolled_course_ids = [e.course_id for e in enrollments]
    
    if not enrolled_course_ids:
        return render_template('student/live_sessions.html', 
                               upcoming_sessions=[], 
                               live_sessions=[], 
                               past_sessions=[])
        
    sessions = LiveSession.query.filter(LiveSession.course_id.in_(enrolled_course_ids)).order_by(LiveSession.scheduled_at.asc()).all()
    
    upcoming_sessions = [s for s in sessions if s.status == 'scheduled']
    live_sessions_list = [s for s in sessions if s.status == 'live']
    past_sessions = [s for s in sessions if s.status in ('ended', 'cancelled')]
    
    return render_template('student/live_sessions.html',
                           upcoming_sessions=upcoming_sessions,
                           live_sessions=live_sessions_list,
                           past_sessions=past_sessions)


@student_bp.route('/live-classroom/<int:session_id>/join')
@login_required
@student_required
def join_live_room(session_id):
    """Enrolled student 1-click video classroom launcher"""
    from app.models import LiveSession, Enrollment, LiveAttendance
    
    session_obj = LiveSession.query.get_or_404(session_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=session_obj.course_id).first()
    
    if not enrollment:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('student.live_classrooms'))
        
    if session_obj.status == 'cancelled':
        flash('This live session was cancelled.', 'warning')
        return redirect(url_for('student.live_classrooms'))
        
    # Log attendance entry
    attendance = LiveAttendance.query.filter_by(session_id=session_id, student_id=current_user.id).first()
    if not attendance:
        attendance = LiveAttendance(session_id=session_id, student_id=current_user.id)
        db.session.add(attendance)
    else:
        attendance.last_ping = datetime.utcnow()
    db.session.commit()
    
    return render_template('live_room.html', session_obj=session_obj, is_host=False)


@student_bp.route('/live-classroom/<int:session_id>/ping-attendance', methods=['POST'])
@login_required
def ping_live_attendance(session_id):
    """Heartbeat endpoint to track student active duration during live meeting"""
    from app.models import LiveAttendance
    attendance = LiveAttendance.query.filter_by(session_id=session_id, student_id=current_user.id).first()
    if attendance:
        attendance.last_ping = datetime.utcnow()
        db.session.commit()
        return jsonify({'status': 'active'}), 200
    return jsonify({'status': 'not_found'}), 404


@student_bp.route('/live-classroom/<int:session_id>/ask-question', methods=['POST'])
@login_required
@student_required
def ask_live_question(session_id):
    """Submit a pre-meeting question for an upcoming or live session"""
    from app.models import LiveSession, LiveQuestion, Enrollment
    session_obj = LiveSession.query.get_or_404(session_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=session_obj.course_id).first()
    
    if not enrollment:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('student.live_classrooms'))
        
    question_text = request.form.get('question_text', '').strip()
    if not question_text:
        flash('Please type a question before submitting.', 'warning')
        return redirect(url_for('student.live_classrooms'))
        
    new_q = LiveQuestion(
        session_id=session_id,
        student_id=current_user.id,
        question_text=question_text
    )
    db.session.add(new_q)
    db.session.commit()
    
    flash('❓ Question submitted to instructor for the live session!', 'success')
    return redirect(url_for('student.live_classrooms'))