from flask import Blueprint, render_template, redirect, url_for, jsonify, send_from_directory, request, flash
from flask_login import login_required, current_user
from app.models import Course, Section, Enrollment, EnrollmentSection, Assignment, Quiz, QuizQuestion, QuizAttempt, AssignmentSubmission
from app import db
from datetime import datetime
from app.decorators import student_required, student_enrolled
from app.forms import SubmissionForm
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    enrolled_courses = Course.query.join(Enrollment)\
        .filter(Enrollment.student_id == current_user.id)\
        .filter(Course.status == 'approved')\
        .all()

    new_enrollments = [c for c in enrolled_courses if not hasattr(current_user, 'last_seen') or c.created_at > getattr(current_user, 'last_seen', None)]
    if new_enrollments:
        flash(f"You’ve been enrolled in {', '.join(c.title for c in new_enrollments)}!", 'success')

    return render_template('student/dashboard.html', courses=enrolled_courses)

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
                         completion_percentage=completion_percentage)

@student_bp.route('/section/<int:section_id>/content', methods=['GET', 'POST'])
@login_required
def get_section_content(section_id):
    if current_user.role not in ['student', 'admin']:
        return "Unauthorized", 403
    
    section = Section.query.get_or_404(section_id)
    logger.debug(f"Fetching content for section {section.id}: title={section.title}, type={section.section_type}, content={section.content}, duration={section.duration}")

    if current_user.role == 'student':
        if not student_enrolled(section.course_id):
            return "Not enrolled or course not approved", 403
        
        sections = Section.query.filter_by(course_id=section.course_id).order_by(Section.order).all()
        section_idx = next(i for i, s in enumerate(sections) if s.id == section_id)
        if section_idx > 0:
            prev_section = sections[section_idx - 1]
            prev_es = EnrollmentSection.query.filter_by(enrollment_id=Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first().id, section_id=prev_section.id).first()
            if not prev_es or not prev_es.completed:
                return "Section locked", 403

    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    enrollment_section = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id if enrollment else None, section_id=section_id).first()
    if not enrollment_section and current_user.role == 'student':
        enrollment_section = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
        db.session.add(enrollment_section)
        db.session.commit()

    if request.method == 'POST' and current_user.role == 'student':
        if 'mark_completed' in request.form:
            enrollment_section.completed = True
            enrollment_section.completed_at = datetime.utcnow()
            db.session.commit()
            content_html = f"<div id='section-content-{section.id}'>"
            content_html += f"<p class='text-gray-600 mb-2'>Duration: {section.duration} minutes</p>"
            content_html += f"<p class='text-gray-600 mb-4'>Type: {section.section_type.capitalize()}</p>"
            if not section.content:
                content_html += "<p class='text-red-500'>No content available for this section.</p>"
            elif section.section_type == 'video':
                try:
                    youtube_id = section.content.split('v=')[1].split('&')[0] if 'v=' in section.content else section.content.split('/')[-1]
                    if not youtube_id or len(youtube_id) != 11:
                        logger.error(f"Invalid YouTube ID for section {section.id}: {section.content}")
                        content_html += "<p class='text-red-500'>Invalid video content. Please check the URL.</p>"
                    else:
                        content_html += f"""
                            <div class="aspect-w-16 aspect-h-9">
                                <iframe id="youtube-player-{section.id}" 
                                        class="w-full h-64 md:h-96" 
                                        src="https://www.youtube.com/embed/{youtube_id}?enablejsapi=1" 
                                        frameborder="0" 
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                        allowfullscreen></iframe>
                            </div>
                        """
                except Exception as e:
                    logger.error(f"Error parsing YouTube URL for section {section.id}: {section.content}, error: {str(e)}")
                    content_html += "<p class='text-red-500'>Error loading video content. Please check the URL.</p>"
            elif section.section_type == 'pdf':
                pdf_url = url_for('admin.serve_pdf', filename=section.content) if current_user.role == 'admin' else url_for('student.view_pdf', section_id=section.id)
                if not section.content:
                    content_html += "<p class='text-red-500'>No PDF file associated.</p>"
                else:
                    content_html += f"""
                        <a href="{pdf_url}" 
                           class="text-blue-600 hover:underline flex items-center" target="_blank">
                            <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                            </svg>
                            View PDF
                        </a>
                    """
            else:
                content_html += f"""
                    <div class="prose max-w-none mt-2" id="text-content-{section.id}">
                        {section.content or 'No text content available.'}
                    </div>
                """
            content_html += "<h4 class='font-medium mt-4'>Assignments</h4>"
            assignments = Assignment.query.filter_by(section_id=section.id).all()
            if assignments:
                for assignment in assignments:
                    content_html += f"""
                        <p><a href="{url_for('student.submit_assignment', section_id=section.id, assignment_id=assignment.id)}" class="text-blue-600 hover:underline">{assignment.title}</a></p>
                        <p>Due: {assignment.due_date.strftime('%Y-%m-%d %H:%M') if assignment.due_date else 'No due date'}</p>
                    """
            else:
                content_html += "<p>No assignments available.</p>"
            
            content_html += "<h4 class='font-medium mt-4'>Video</h4>"
            if section.section_type == 'video' and section.content:
                try:
                    youtube_id = section.content.split('v=')[1].split('&')[0] if 'v=' in section.content else section.content.split('/')[-1]
                    if not youtube_id or len(youtube_id) != 11:
                        content_html += "<p class='text-red-500'>Invalid video content.</p>"
                    else:
                        content_html += f"""
                            <div class="aspect-w-16 aspect-h-9">
                                <iframe id="youtube-player-{section.id}" 
                                        class="w-full h-64 md:h-96" 
                                        src="https://www.youtube.com/embed/{youtube_id}?enablejsapi=1" 
                                        frameborder="0" 
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                        allowfullscreen></iframe>
                            </div>
                        """
                except:
                    content_html += "<p class='text-red-500'>Error loading video.</p>"
            else:
                content_html += "<p>No video available.</p>"
            
            content_html += "<h4 class='font-medium mt-4'>Quizzes</h4>"
            quizzes = Quiz.query.filter_by(section_id=section.id).all()
            if quizzes:
                for quiz in quizzes:
                    content_html += f"""
                        <p><a href="{url_for('student.take_quiz', section_id=section.id, quiz_id=quiz.id)}" class="text-blue-600 hover:underline">{quiz.title}</a></p>
                    """
            else:
                content_html += "<p>No quizzes available.</p>"

            if current_user.role == 'student':
                button_html = f"""
                    <form method="POST" class="mt-4" hx-post="{url_for('student.get_section_content', section_id=section.id)}" hx-target="#section-content-{section.id}" hx-swap="innerHTML">
                        <button type="submit" name="mark_completed" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                                {'disabled' if enrollment_section.completed else ''}>
                            {'Completed' if enrollment_section.completed else 'Mark as Completed'}
                        </button>
                    </form>
                """
                content_html += button_html
            content_html += "</div>"
            return content_html

    content_html = f"<div id='section-content-{section.id}'>"
    content_html += f"<p class='text-gray-600 mb-2'>Duration: {section.duration} minutes</p>"
    content_html += f"<p class='text-gray-600 mb-4'>Type: {section.section_type.capitalize()}</p>"
    if not section.content:
        content_html += "<p class='text-red-500'>No content available for this section.</p>"
    elif section.section_type == 'video':
        try:
            youtube_id = section.content.split('v=')[1].split('&')[0] if 'v=' in section.content else section.content.split('/')[-1]
            if not youtube_id or len(youtube_id) != 11:
                logger.error(f"Invalid YouTube ID for section {section.id}: {section.content}")
                content_html += "<p class='text-red-500'>Invalid video content. Please check the URL.</p>"
            else:
                content_html += f"""
                    <div class="aspect-w-16 aspect-h-9">
                        <iframe id="youtube-player-{section.id}" 
                                class="w-full h-64 md:h-96" 
                                src="https://www.youtube.com/embed/{youtube_id}?enablejsapi=1" 
                                frameborder="0" 
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                allowfullscreen></iframe>
                    </div>
                """
        except Exception as e:
            logger.error(f"Error parsing YouTube URL for section {section.id}: {section.content}, error: {str(e)}")
            content_html += "<p class='text-red-500'>Error loading video content. Please check the URL.</p>"
    elif section.section_type == 'pdf':
        pdf_url = url_for('admin.serve_pdf', filename=section.content) if current_user.role == 'admin' else url_for('student.view_pdf', section_id=section.id)
        if not section.content:
            content_html += "<p class='text-red-500'>No PDF file associated.</p>"
        else:
            content_html += f"""
                <a href="{pdf_url}" 
                   class="text-blue-600 hover:underline flex items-center" target="_blank">
                    <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                    </svg>
                    View PDF
                </a>
            """
    else:
        content_html += f"""
            <div class="prose max-w-none mt-2" id="text-content-{section.id}">
                {section.content or 'No text content available.'}
            </div>
        """
    
    content_html += "<h4 class='font-medium mt-4'>Assignments</h4>"
    assignments = Assignment.query.filter_by(section_id=section.id).all()
    if assignments:
        for assignment in assignments:
            content_html += f"""
                <p><a href="{url_for('student.submit_assignment', section_id=section.id, assignment_id=assignment.id)}" class="text-blue-600 hover:underline">{assignment.title}</a></p>
                <p>Due: {assignment.due_date.strftime('%Y-%m-%d %H:%M') if assignment.due_date else 'No due date'}</p>
            """
    else:
        content_html += "<p>No assignments available.</p>"
    
    content_html += "<h4 class='font-medium mt-4'>Video</h4>"
    if section.section_type == 'video' and section.content:
        try:
            youtube_id = section.content.split('v=')[1].split('&')[0] if 'v=' in section.content else section.content.split('/')[-1]
            if not youtube_id or len(youtube_id) != 11:
                content_html += "<p class='text-red-500'>Invalid video content.</p>"
            else:
                content_html += f"""
                    <div class="aspect-w-16 aspect-h-9">
                        <iframe id="youtube-player-{section.id}" 
                                class="w-full h-64 md:h-96" 
                                src="https://www.youtube.com/embed/{youtube_id}?enablejsapi=1" 
                                frameborder="0" 
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                                allowfullscreen></iframe>
                    </div>
                """
        except:
            content_html += "<p class='text-red-500'>Error loading video.</p>"
    else:
        content_html += "<p>No video available.</p>"
    
    content_html += "<h4 class='font-medium mt-4'>Quizzes</h4>"
    quizzes = Quiz.query.filter_by(section_id=section.id).all()
    if quizzes:
        for quiz in quizzes:
            content_html += f"""
                <p><a href="{url_for('student.take_quiz', section_id=section.id, quiz_id=quiz.id)}" class="text-blue-600 hover:underline">{quiz.title}</a></p>
            """
    else:
        content_html += "<p>No quizzes available.</p>"

    if current_user.role == 'student':
        button_html = f"""
            <form method="POST" class="mt-4" hx-post="{url_for('student.get_section_content', section_id=section.id)}" hx-target="#section-content-{section.id}" hx-swap="innerHTML">
                <button type="submit" name="mark_completed" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                        {'disabled' if enrollment_section.completed else ''}>
                    {'Completed' if enrollment_section.completed else 'Mark as Completed'}
                </button>
            </form>
        """
        content_html += button_html

    content_html += "</div>"
    return content_html

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
    
    form = SubmissionForm()
    if form.validate_on_submit():
        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            submission_text=form.submission_text.data
        )
        db.session.add(submission)
        db.session.commit()
        flash('Assignment submitted successfully.', 'success')
        return redirect(url_for('student.course_detail', course_id=section.course_id))
    return render_template('student/submit_assignment.html', form=form, assignment=assignment, section=section)

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

# Added new get_section_content route with unique endpoint to avoid conflict
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

    return render_template('student/_section_content.html', section=section, course=course, enrollment_section=enrollment_section)