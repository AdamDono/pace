from flask import Blueprint, render_template, redirect, url_for, jsonify, send_from_directory, request, flash, current_app
from flask_login import login_required, current_user
from app.models import Course, Section, Enrollment, EnrollmentSection, Assignment, Quiz, QuizQuestion, QuizAttempt, AssignmentSubmission, Rating
from app import db
from datetime import datetime
from app.decorators import student_required, student_enrolled
from app.forms import SubmissionForm
import logging
import os
from uuid import uuid4
from werkzeug.utils import secure_filename
from app.routes.teacher import allowed_file

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
    for course in enrolled_courses:
        logger.debug(f"Course ID: {course.id}, Title: {course.title}, intro_text: {course.intro_text}")
    new_enrollments = [c for c in enrolled_courses if not hasattr(current_user, 'last_seen') or c.created_at > getattr(current_user, 'last_seen', None)]
    if new_enrollments:
        flash(f"You’ve been enrolled in {', '.join(c.title for c in new_enrollments)}!", 'success')
    return render_template('student/courses.html', courses=enrolled_courses)

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
            prev_enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
            prev_es = EnrollmentSection.query.filter_by(enrollment_id=prev_enrollment.id, section_id=prev_section.id).first()
            if not prev_es or not prev_es.completed:
                return "Section locked", 403

    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first_or_404()
    enrollment_section = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not enrollment_section and current_user.role == 'student':
        enrollment_section = EnrollmentSection(enrollment_id=enrollment.id, section_id=section_id)
        db.session.add(enrollment_section)
        db.session.commit()

    if request.method == 'POST' and 'mark_completed' in request.form and current_user.role == 'student':
        enrollment_section.completed = True
        enrollment_section.completed_at = datetime.utcnow()
        db.session.commit()
        flash('Section marked as completed.', 'success')

    course = Course.query.get_or_404(section.course_id)
    return render_template('student/_section_content.html', section=section, course=course, enrollment_section=enrollment_section)

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
        file_path = None
        # Handle file upload if present
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file and allowed_file(file.filename, allowed_extensions={'pdf', 'doc', 'docx'}):
                filename = secure_filename(f"{uuid4().hex}{os.path.splitext(file.filename)[1]}")
                file_path = filename
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))

        submission = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=current_user.id,
            submission_text=form.submission_text.data,
            file_path=file_path
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

@student_bp.route('/course/<int:course_id>/review', methods=['POST'])
@login_required
@student_required
def submit_review(course_id):
    if not student_enrolled(course_id):
        return "Unauthorized", 403
    rating = int(request.form['rating'])
    review = request.form['review']
    new_rating = Rating(user_id=current_user.id, course_id=course_id, rating=rating, review=review)
    db.session.add(new_rating)
    db.session.commit()
    flash('Review submitted successfully!', 'success')
    return redirect(url_for('student.course_detail', course_id=course_id))