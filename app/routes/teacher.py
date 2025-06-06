from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Course, db, Section, User, Enrollment, Assignment, Quiz, QuizQuestion, QuizAttempt, QuizAnswer
from app.forms import CourseForm, AssignmentForm, QuizForm, QuestionForm
from app.decorators import teacher_required
import os
import uuid
from datetime import datetime

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def allowed_file(filename, allowed_extensions=None):
    if allowed_extensions is None:
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('teacher/dashboard.html')

@teacher_bp.route('/create-course', methods=['GET', 'POST'])
@teacher_required
def create_course():
    form = CourseForm()
    if form.validate_on_submit():
        try:
            pdf_filename = None
            banner_image = None
            intro_video = None

            # Handle PDF upload
            if form.pdf_upload.data:
                pdf = form.pdf_upload.data
                if not allowed_file(pdf.filename):
                    flash('Only PDF files are allowed', 'danger')
                    return redirect(url_for('teacher.create_course'))
                
                pdf_filename = f"course_{uuid.uuid4().hex}.pdf"
                save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    pdf_filename
                )
                pdf.save(save_path)

            # Handle banner image upload
            banner_file = request.files.get('banner_image')
            if banner_file and banner_file.filename:
                if not allowed_file(banner_file.filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif'}):
                    flash('Only image files (PNG, JPG, JPEG, GIF) are allowed for banner', 'danger')
                    return redirect(url_for('teacher.create_course'))
                
                banner_filename = f"banner_{uuid.uuid4().hex}{os.path.splitext(banner_file.filename)[1]}"
                banner_save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    banner_filename
                )
                banner_file.save(banner_save_path)
                banner_image = banner_filename

            # Handle intro video URL
            intro_video_url = request.form.get('intro_video')
            if intro_video_url:
                if 'youtube.com' not in intro_video_url and 'youtu.be' not in intro_video_url:
                    flash('Only YouTube URLs are allowed for intro video', 'danger')
                    return redirect(url_for('teacher.create_course'))
                intro_video = intro_video_url

            # Validate YouTube URL for youtube_url field
            youtube_url = None
            if form.youtube_url.data:
                if 'youtube.com' not in form.youtube_url.data and 'youtu.be' not in form.youtube_url.data:
                    flash('Only YouTube URLs are allowed', 'danger')
                    return redirect(url_for('teacher.create_course'))
                youtube_url = form.youtube_url.data

            # Create the course
            course = Course(
                title=form.title.data,
                description=form.description.data,
                youtube_url=youtube_url,
                teacher_id=current_user.id,
                status='pending',
                pdf_filename=pdf_filename,
                banner_image=banner_image,
                intro_video=intro_video
            )
            
            db.session.add(course)
            db.session.commit()
            flash('Course submitted for approval!', 'success')
            return redirect(url_for('teacher.my_courses'))
            
        except Exception as e:
            db.session.rollback()
            # Clean up uploaded files on error
            if pdf_filename and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)):
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename))
            if banner_image and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], banner_image)):
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], banner_image))
            flash(f'Error: {str(e)}', 'danger')

    return render_template('teacher/create_course.html', form=form)

@teacher_bp.route('/edit-course/<int:course_id>', methods=['GET', 'POST'])
@teacher_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id or course.status == 'approved':
        abort(403)
    
    form = CourseForm(obj=course)
    
    if form.validate_on_submit():
        try:
            # Handle PDF upload
            if form.pdf_upload.data:
                if course.pdf_filename:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], course.pdf_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                pdf = form.pdf_upload.data
                if not allowed_file(pdf.filename):
                    flash('Only PDF files are allowed', 'danger')
                    return redirect(url_for('teacher.edit_course', course_id=course_id))
                
                pdf_filename = f"course_{uuid.uuid4().hex}.pdf"
                save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    pdf_filename
                )
                pdf.save(save_path)
                course.pdf_filename = pdf_filename

            # Handle banner image upload
            banner_file = request.files.get('banner_image')
            if banner_file and banner_file.filename:
                if course.banner_image:
                    old_banner_path = os.path.join(current_app.config['UPLOAD_FOLDER'], course.banner_image)
                    if os.path.exists(old_banner_path):
                        os.remove(old_banner_path)
                
                if not allowed_file(banner_file.filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif'}):
                    flash('Only image files (PNG, JPG, JPEG, GIF) are allowed for banner', 'danger')
                    return redirect(url_for('teacher.edit_course', course_id=course_id))
                
                banner_filename = f"banner_{uuid.uuid4().hex}{os.path.splitext(banner_file.filename)[1]}"
                banner_save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    banner_filename
                )
                banner_file.save(banner_save_path)
                course.banner_image = banner_filename

            # Handle intro video URL
            intro_video_url = request.form.get('intro_video')
            if intro_video_url:
                if 'youtube.com' not in intro_video_url and 'youtu.be' not in intro_video_url:
                    flash('Only YouTube URLs are allowed for intro video', 'danger')
                    return redirect(url_for('teacher.edit_course', course_id=course_id))
                course.intro_video = intro_video_url
            else:
                course.intro_video = None

            # Update other fields
            form.populate_obj(course)
            course.status = 'pending'
            db.session.commit()
            flash('Course updated successfully!', 'success')
            return redirect(url_for('teacher.my_courses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('teacher/edit_course.html', form=form, course=course)

@teacher_bp.route('/my-courses')
@teacher_required
def my_courses():
    status_filter = request.args.get('status', 'all')
    query = Course.query.filter_by(teacher_id=current_user.id)\
                        .order_by(Course.created_at.desc())
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    courses = query.all()
    return render_template('teacher/my_courses.html', courses=courses, status_filter=status_filter)

@teacher_bp.route('/course/<int:course_id>/enroll-students', methods=['GET', 'POST'])
@teacher_required
def enroll_students(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        student_email = request.form.get('student_email')
        student = User.query.filter_by(email=student_email, role='student').first()

        if not student:
            flash('Student not found or invalid email.', 'danger')
            return redirect(url_for('teacher.enroll_students', course_id=course_id))

        existing_enrollment = Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first()
        if existing_enrollment:
            flash('Student is already enrolled in this course.', 'warning')
            return redirect(url_for('teacher.enroll_students', course_id=course_id))

        enrollment = Enrollment(student_id=student.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'Student {student.email} enrolled successfully!', 'success')
        return redirect(url_for('teacher.enroll_students', course_id=course_id))

    enrolled_students = User.query.join(Enrollment).filter(Enrollment.course_id == course.id).all()
    return render_template('teacher/enroll_students.html', course=course, enrolled_students=enrolled_students)

@teacher_bp.route('/course/<int:course_id>/add-section', methods=['GET', 'POST'])
@teacher_required
def create_section(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        section_type = request.form['section_type']
        duration = int(request.form.get('duration', 0))

        section = Section(
            title=title,
            content=content,
            course_id=course.id,
            section_type=section_type,
            order=len(course.sections) + 1,
            duration=duration
        )
        db.session.add(section)
        db.session.commit()
        flash('Section added!', 'success')
        return redirect(url_for('teacher.manage_sections', course_id=course.id))

    return render_template('teacher/section_editor.html', course=course)

@teacher_bp.route('/course/<int:course_id>/sections', methods=['GET', 'POST'])
@login_required
@teacher_required
def manage_sections(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('You are not authorized to manage this course.', 'danger')
        return redirect(url_for('teacher.my_courses'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        section_type = request.form.get('section_type', 'text')
        duration = request.form.get('duration', type=int, default=0)
        media_file = request.files.get('media_file')
        video_url = request.form.get('video_url')

        if not title:
            flash('Title is required.', 'danger')
            return redirect(url_for('teacher.manage_sections', course_id=course_id))

        section = Section(
            course_id=course_id,
            title=title,
            content=content,
            section_type=section_type,
            duration=duration,
            is_published=False,
            created_at=datetime.utcnow()
        )

        if media_file and section_type in ['image', 'audio', 'presentation']:
            if not allowed_file(media_file.filename, allowed_extensions={'jpg', 'jpeg', 'png', 'gif', 'mp3', 'pdf'}):
                flash('Only images (JPG, JPEG, PNG, GIF), audio (MP3), or PDFs are allowed', 'danger')
                return redirect(url_for('teacher.manage_sections', course_id=course_id))
            
            filename = secure_filename(media_file.filename)
            media_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            section.media_file = filename

        if video_url and section_type == 'video':
            if 'youtube.com' not in video_url and 'youtu.be' not in video_url:
                flash('Only YouTube URLs are allowed for video sections', 'danger')
                return redirect(url_for('teacher.manage_sections', course_id=course_id))
            section.video_url = video_url

        db.session.add(section)
        db.session.commit()
        flash('Section created successfully!', 'success')
        return redirect(url_for('teacher.manage_sections', course_id=course_id))

    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()
    return render_template('teacher/section_editor.html', course=course, sections=sections)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/add-assignment', methods=['GET', 'POST'])
@teacher_required
def add_assignment(course_id, section_id):
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    form = AssignmentForm()
    if form.validate_on_submit():
        assignment = Assignment(
            title=form.title.data,
            description=form.description.data,
            section_id=section_id,
            due_date=form.due_date.data
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Assignment created successfully.', 'success')
        return redirect(url_for('teacher.manage_sections', course_id=course_id))
    return render_template('teacher/add_assignment.html', form=form, course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/add-quiz', methods=['GET', 'POST'])
@teacher_required
def add_quiz(course_id, section_id):
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    form = QuizForm()
    if form.validate_on_submit():
        quiz = Quiz(title=form.title.data, section_id=section_id)
        db.session.add(quiz)
        db.session.flush()
        for q in form.questions.data:
            question = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q['question'],
                option_a=q['a'], option_b=q['b'], option_c=q['c'], option_d=q['d'],
                correct_answer=q['correct']
            )
            db.session.add(question)
        db.session.commit()
        flash('Quiz created successfully.', 'success')
        return redirect(url_for('teacher.manage_sections', course_id=course_id))
    return render_template('teacher/add_quiz.html', form=form, course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/submissions')
@teacher_required
def view_submissions(course_id, section_id):
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    assignments = Assignment.query.filter_by(section_id=section_id).all()
    submissions = []
    for assignment in assignments:
        submissions.extend(assignment.submissions)  # Directly use submission objects
    return render_template('teacher/view_submissions.html', course=course, section=section, submissions=submissions)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/submission/<int:submission_id>/review', methods=['POST'])
@teacher_required
def review_submission(course_id, section_id, submission_id):
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    submission.feedback = request.form.get('feedback')
    submission.reviewed = True
    db.session.commit()
    flash('Submission reviewed successfully.', 'success')
    return redirect(url_for('teacher.view_submissions', course_id=course_id, section_id=section_id))

@teacher_bp.route('/course/<int:course_id>/reorder-sections', methods=['POST'])
@teacher_required
def reorder_sections(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    try:
        order_data = request.get_json()
        for idx, section_id in enumerate(order_data):
            section = Section.query.get(section_id)
            section.order = idx + 1
        db.session.commit()
        return jsonify({"message": "Sections reordered successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@teacher_bp.route('/section/<int:section_id>/delete', methods=['POST'])
@teacher_required
def delete_section(section_id):
    section = db.session.get(Section, section_id) or abort(404)
    course_id = section.course_id
    
    if section.course.teacher_id != current_user.id:
        abort(403)

    try:
        db.session.delete(section)
        db.session.commit()
        flash('Section deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('teacher.manage_sections', course_id=course_id))

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/quiz-attempts')
@teacher_required
def view_quiz_attempts(course_id, section_id):
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)

    # Get all quizzes in this section
    quizzes = Quiz.query.filter_by(section_id=section_id).all()
    quiz_attempts = []
    for quiz in quizzes:
        # Get all attempts for this quiz
        attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).all()
        for attempt in attempts:
            # Get the student and their answers
            student = User.query.get(attempt.student_id)
            answers = QuizAnswer.query.filter_by(attempt_id=attempt.id).all()
            quiz_attempts.append({
                'quiz_title': quiz.title,
                'student_email': student.email,
                'score': attempt.score,
                'attempted_at': attempt.attempted_at,
                'answers': answers
            })

    return render_template('teacher/view_quiz_attempts.html', course=course, section=section, quiz_attempts=quiz_attempts)