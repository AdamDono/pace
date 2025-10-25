from flask import Blueprint, render_template, redirect, url_for, jsonify, send_from_directory, request, flash, current_app, abort
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
                # Continue learning: pick most recent section
                if es_list:
                    last_es = max(es_list, key=lambda es: es.last_accessed or datetime.min)
                    if last_es and last_es.last_accessed:
                        last_accessed = last_es
                        # Ensure section exists
                        try:
                            cont_section = Section.query.get(last_es.section_id)
                            if cont_section:
                                continue_learning.append({'course': course, 'section': cont_section, 'last_accessed': last_es.last_accessed})
                        except Exception:
                            pass

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

    return render_template(
        'student/dashboard.html',
        courses=enrolled_courses,
        progress_by_course=progress_by_course,
        continue_learning=sorted(continue_learning, key=lambda x: x['last_accessed'], reverse=True)[:6],
        upcoming=upcoming,
        estimated_time=estimated_time
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
@student_required
def course_detail(course_id):
    if not student_enrolled(course_id):
        return redirect(url_for('auth.login'))

    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if not enrollment:
        return redirect(url_for('student.dashboard'))

    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()
    enrollment_sections = {es.section_id: es for es in enrollment.sections}

    total_sections = len(sections)
    completed_sections = sum(1 for es in enrollment_sections.values() if es.completed)
    completion_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0

    locked_sections = set()
    for i, section in enumerate(sections):
        es = enrollment_sections.get(section.id)
        if i == 0:
            continue
        prev_section = sections[i-1]
        prev_es = enrollment_sections.get(prev_section.id)
        if not prev_es or not prev_es.completed:
            locked_sections.add(section.id)

    return render_template('student/course_detail.html', 
                         course=course, 
                         sections=sections,
                         enrollment_sections=enrollment_sections,
                         locked_sections=locked_sections,
                         completion_percentage=completion_percentage,
                         enrollment=enrollment)

@student_bp.route('/section/<int:section_id>/content', methods=['GET', 'POST'])
@login_required
@student_required
def get_section_content(section_id):
    section = Section.query.get_or_404(section_id)
    course = Course.query.get_or_404(section.course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first_or_404()

    # Section locking logic
    sections = Section.query.filter_by(course_id=course.id).order_by(Section.order).all()
    section_idx = next(i for i, s in enumerate(sections) if s.id == section_id)
    if section_idx > 0:
        prev_section = sections[section_idx - 1]
        prev_es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=prev_section.id).first()
        if not prev_es or not prev_es.completed:
            flash('Please complete the previous section first.', 'error')
            return redirect(url_for('student.course_detail', course_id=course.id))

    # Create EnrollmentSection if it doesn't exist
    enrollment_section = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not enrollment_section:
        enrollment_section = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
        db.session.add(enrollment_section)
    
    # Update tracking: increment view count and update last accessed
    enrollment_section.view_count = (enrollment_section.view_count or 0) + 1
    enrollment_section.last_accessed = datetime.utcnow()
    db.session.commit()

    # Handle marking as complete
    if request.method == 'POST' and 'mark_completed' in request.form:
        enrollment_section.completed = True
        enrollment_section.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Section marked as completed.', 'success')

        # Check if the entire course is completed
        all_sections = Section.query.filter_by(course_id=course.id).all()
        all_enrollment_sections = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
        if all(es.completed for es in all_enrollment_sections) and len(all_enrollment_sections) == len(all_sections):
            # Mark enrollment as completed
            enrollment.completed = True
            enrollment.completed_at = datetime.utcnow()
            db.session.commit()
            flash('🎉 Congratulations! You completed the course! Check your certificates.', 'success')
            return jsonify({'status': 'completed', 'course_id': course.id, 'redirect': None})
        return jsonify({'status': 'updated', 'message': 'Section updated.'})

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
@student_required
def submit_assignment(section_id, assignment_id):
    section = Section.query.get_or_404(section_id)
    assignment = Assignment.query.get_or_404(assignment_id)
    if assignment.section_id != section_id or not student_enrolled(section.course_id):
        abort(403)
    
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        abort(403)
    
    # Check for existing submission
    existing_submission = AssignmentSubmission.query.filter_by(
        assignment_id=assignment_id,
        student_id=current_user.id
    ).first()
    
    form = SubmissionForm()

    # --- Coding assignment submission path ---
    if assignment.is_coding_assignment:
        if request.method == 'POST':
            code = request.form.get('code_submission', '').strip()
            file_path = None

            # Allow code file uploads if enabled
            if assignment.allow_file_upload and 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                # Accept common code extensions
                code_exts = {'py', 'js', 'java', 'cpp', 'c', 'hpp', 'h', 'ts', 'tsx', 'html', 'css', 'sql', 'txt'}
                if file and allowed_file(file.filename, allowed_extensions=code_exts):
                    filename = secure_filename(f"{uuid4().hex}{os.path.splitext(file.filename)[1]}")
                    file_path = filename
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

            if not code and not file_path:
                flash('Please write code or upload a code file before submitting.', 'danger')
                return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission)

            submission = AssignmentSubmission(
                assignment_id=assignment_id,
                student_id=current_user.id,
                submission_text=code if not file_path else '',
                file_path=file_path,
                submission_type='code',
                code_submission=code if code else None,
                programming_language=assignment.programming_language
            )
            db.session.add(submission)
            db.session.commit()
            flash('Coding assignment submitted successfully.', 'success')
            return redirect(url_for('student.course_detail', course_id=section.course_id))

        # GET or invalid post
        return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission)

    # --- Regular (text/file) assignment path ---
    if form.validate_on_submit():
        file_path = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{uuid4().hex}{os.path.splitext(file.filename)[1]}")
                file_path = filename
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            submission_text=form.submission_text.data,
            file_path=file_path,
            submission_type='text'
        )
        db.session.add(submission)
        db.session.commit()
        flash('Assignment submitted successfully.', 'success')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section, existing_submission=existing_submission)

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
    
    attempt_count = QuizAttempt.query.filter_by(quiz_id=quiz_id, student_id=current_user.id).count()
    if attempt_count >= 3:
        flash('You have reached the maximum of 3 attempts for this quiz.', 'warning')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    
    if request.method == 'POST':
        score = 0
        total = len(questions)
        for q in questions:
            user_answer = request.form.get(f'q{q.id}')
            if user_answer and user_answer == q.correct_answer:
                score += 1
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            student_id=current_user.id,
            score=(score / total) * 100
        )
        db.session.add(attempt)
        db.session.commit()
        flash(f'Quiz completed! Score: {score}/{total} ({(score/total)*100:.1f}%)', 'success')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    return render_template('student/take_quiz.html', quiz=quiz, questions=questions, section=section)

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

@student_bp.route('/section/<int:section_id>/content_new', methods=['GET', 'POST'])
@student_required
def get_section_content_new(section_id):
    section = Section.query.get_or_404(section_id)
    course = Course.query.get_or_404(section.course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first_or_404()

    # Section locking logic
    sections = Section.query.filter_by(course_id=section.course_id).order_by(Section.order).all()
    section_idx = next(i for i, s in enumerate(sections) if s.id == section_id)
    if section_idx > 0:
        prev_section = sections[section_idx - 1]
        prev_es = EnrollmentSection.query.filter_by(
            enrollment_id=enrollment.id, section_id=prev_section.id
        ).first()
        if not prev_es or not prev_es.completed:
            return "Section locked", 403

    # Create EnrollmentSection if it doesn't exist
    enrollment_section = EnrollmentSection.query.filter_by(
        enrollment_id=enrollment.id, section_id=section_id
    ).first()
    if not enrollment_section:
        enrollment_section = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
        db.session.add(enrollment_section)
        db.session.commit()

    # Handle marking as complete
    if request.method == 'POST' and 'mark_completed' in request.form:
        enrollment_section.completed = True
        enrollment_section.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Section marked as completed.', 'success')

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

@student_bp.route('/generate_certificate/<int:enrollment_id>', methods=['POST'])
@login_required
@student_required
def generate_certificate(enrollment_id):
    logger.debug(f"Generating certificate for enrollment_id: {enrollment_id}")
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != current_user.id:
        logger.warning(f"Unauthorized certificate request for enrollment_id: {enrollment_id}")
        return jsonify({'status': 'error', 'message': 'Unauthorized access.'}), 403
    if not all(es.completed for es in enrollment.sections) or not Rating.query.filter_by(course_id=enrollment.course_id, user_id=current_user.id).first():
        return jsonify({'status': 'error', 'message': 'Course not fully completed or rated.'}), 403

    user_name = current_user.username or current_user.email.split('@')[0]
    certificate_filename = f"certificate_{enrollment.id}_{int(datetime.utcnow().timestamp())}.pdf"
    certificate_path = os.path.join(current_app.config['UPLOAD_FOLDER'], certificate_filename)

    c = canvas.Canvas(certificate_path, pagesize=letter)
    width, height = letter
    
    # ===== ELEGANT BORDER DESIGN =====
    # Outer gold border
    c.setStrokeColor(HexColor('#D4AF37'))  # Gold
    c.setLineWidth(8)
    c.rect(30, 30, width - 60, height - 60, stroke=1, fill=0)
    
    # Inner border with gradient effect (multiple lines)
    c.setStrokeColor(HexColor('#B8860B'))  # Dark gold
    c.setLineWidth(2)
    c.rect(40, 40, width - 80, height - 80, stroke=1, fill=0)
    
    # Decorative corner accents
    c.setStrokeColor(HexColor('#FFD700'))  # Bright gold
    c.setLineWidth(3)
    # Top left corner
    c.line(40, height - 80, 100, height - 80)
    c.line(40, height - 80, 40, height - 140)
    # Top right corner
    c.line(width - 100, height - 80, width - 40, height - 80)
    c.line(width - 40, height - 80, width - 40, height - 140)
    # Bottom left corner
    c.line(40, 80, 100, 80)
    c.line(40, 80, 40, 140)
    # Bottom right corner
    c.line(width - 100, 80, width - 40, 80)
    c.line(width - 40, 80, width - 40, 140)
    
    # ===== HEADER SECTION =====
    # Top decorative line
    c.setStrokeColor(HexColor('#4169E1'))  # Royal blue
    c.setLineWidth(3)
    c.line(100, height - 120, width - 100, height - 120)
    
    # Logo at top (if exists)
    logo_path = os.path.join(current_app.static_folder, 'images', 'xai_logo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, (width - 100) / 2, height - 110, width=100, height=50, mask='auto')
    
    # ===== TITLE SECTION =====
    # "Certificate of" in elegant script
    c.setFillColor(HexColor('#4169E1'))  # Royal blue
    c.setFont("Helvetica-Oblique", 24)
    c.drawCentredString(width / 2, height - 180, "Certificate of")
    
    # "COMPLETION" in bold capitals
    c.setFillColor(HexColor('#1E3A8A'))  # Dark blue
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(width / 2, height - 230, "COMPLETION")
    
    # Decorative line under title
    c.setStrokeColor(HexColor('#D4AF37'))  # Gold
    c.setLineWidth(2)
    c.line(150, height - 250, width - 150, height - 250)
    
    # ===== PRESENTED TO SECTION =====
    c.setFillColor(HexColor('#666666'))  # Gray
    c.setFont("Helvetica-Oblique", 16)
    c.drawCentredString(width / 2, height - 290, "This certificate is proudly presented to")
    
    # ===== STUDENT NAME (HIGHLIGHTED) =====
    # Name background box
    c.setFillColor(HexColor('#F0F8FF'))  # Alice blue background
    c.setStrokeColor(HexColor('#4169E1'))  # Royal blue border
    c.setLineWidth(1)
    c.roundRect(120, height - 360, width - 240, 50, 10, stroke=1, fill=1)
    
    # Student name in elegant font
    c.setFillColor(HexColor('#1E3A8A'))  # Dark blue
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width / 2, height - 345, user_name)
    
    # ===== COURSE DESCRIPTION =====
    c.setFillColor(HexColor('#333333'))  # Dark gray
    c.setFont("Helvetica", 14)
    course_name = enrollment.course.title
    c.drawCentredString(width / 2, height - 400, "For successfully completing the course")
    
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(HexColor('#4169E1'))  # Royal blue
    c.drawCentredString(width / 2, height - 430, f'"{course_name}"')
    
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor('#666666'))  # Gray
    c.drawCentredString(width / 2, height - 460, "with dedication and commitment to learning excellence")
    
    # ===== DATE AND SIGNATURE SECTION =====
    # Completion date
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor('#333333'))
    completion_date = datetime.utcnow().strftime('%B %d, %Y')
    c.drawString(120, 200, "Date of Completion:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(120, 180, completion_date)
    
    # Signature line and text
    c.setFont("Helvetica", 12)
    c.setFillColor(HexColor('#333333'))
    c.drawString(width - 250, 200, "Authorized Signature:")
    # Signature line
    c.setStrokeColor(HexColor('#000000'))
    c.setLineWidth(1)
    c.line(width - 250, 175, width - 80, 175)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(width - 220, 160, "Pace Academy")
    
    # ===== SEAL/BADGE =====
    # Draw a circular seal
    c.setStrokeColor(HexColor('#D4AF37'))  # Gold
    c.setFillColor(HexColor('#FFD700'))  # Bright gold
    c.setLineWidth(3)
    seal_x, seal_y = 100, 120
    c.circle(seal_x, seal_y, 40, stroke=1, fill=1)
    
    # Inner circle
    c.setFillColor(HexColor('#FFFFFF'))  # White
    c.circle(seal_x, seal_y, 35, stroke=0, fill=1)
    
    # Seal text
    c.setFillColor(HexColor('#D4AF37'))  # Gold
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(seal_x, seal_y + 5, "CERTIFIED")
    c.setFont("Helvetica", 8)
    c.drawCentredString(seal_x, seal_y - 10, "COMPLETION")
    
    # ===== FOOTER =====
    c.setFillColor(HexColor('#999999'))
    c.setFont("Helvetica-Oblique", 9)
    certificate_id = f"CERT-{enrollment.id}-{int(datetime.utcnow().timestamp())}"
    c.drawCentredString(width / 2, 60, f"Certificate ID: {certificate_id}")
    c.drawCentredString(width / 2, 45, "This certificate verifies successful course completion")
    
    # Save the PDF
    logger.debug(f"Saving certificate to {certificate_path}")
    c.save()

    enrollment.certificate_path = certificate_filename
    db.session.commit()
    logger.info(f"Certificate generated successfully for enrollment_id: {enrollment_id}")
    flash('Certificate generated successfully!', 'success')
    return jsonify({'status': 'success', 'message': 'Certificate generated', 'certificate_path': certificate_filename})

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
@student_required
def track_time(section_id):
    """Track time spent on a section (AJAX endpoint)"""
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
    
    if form.validate_on_submit():
        # Only require current password when changing password
        if form.new_password.data:
            if not current_user.verify_password(form.current_password.data or ''):
                flash('Current password is incorrect', 'danger')
                return render_template('student/profile.html', form=form)
        
        # Check if email is already taken by another user
        if form.email.data != current_user.email:
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already in use by another account', 'danger')
                return render_template('student/profile.html', form=form)
        
        # Check if username is already taken by another user
        if form.username.data != current_user.username:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash('Username already in use', 'danger')
                return render_template('student/profile.html', form=form)
        
        # Update profile information
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        current_user.contact = form.contact.data
        
        # Handle profile image upload (optional field)
        file = request.files.get('profile_image')
        if file and file.filename:
            # Basic validation
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
            if ext in allowed:
                # Remove old image if exists
                if getattr(current_user, 'profile_image', None):
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_image)
                    try:
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception:
                        pass
                # Save new image
                new_name = f"avatar_student_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
                file.save(save_path)
                current_user.profile_image = new_name
        
        # Update password if provided
        if form.new_password.data:
            current_user.password = form.new_password.data
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.profile'))
    
    # Pre-populate form with current user data
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
        form.contact.data = current_user.contact
    
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
        progress.video_current_time = data.get('current_time', 0)
        progress.duration = data.get('duration', 0)
        progress.watch_percentage = data.get('watch_percentage', 0)
        progress.total_watch_time = data.get('total_watch_time', 0)
        progress.playback_speed = data.get('playback_speed', 1.0)
        progress.play_count = data.get('play_count', 0)
        progress.last_watched = datetime.utcnow()
        
        # Mark as completed if watched >90%
        if progress.watch_percentage >= 90:
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
    enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).all()]
    
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
    enrollments = Enrollment.query.filter_by(
        student_id=current_user.id,
        completed=True
    ).all()
    
    certificates = [e for e in enrollments if e.certificate_path]
    
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
    """Help and support page"""
    return render_template('student/help.html')