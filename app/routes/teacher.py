from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import teacher_required
from app.forms import ProfileForm
from app import db
from app.utils.email import send_enrollment_email
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
    from app.models import Course  # Moved here
    if current_user.role != 'teacher':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/dashboard.html', courses=courses)

@teacher_bp.route('/course/<int:course_id>/delete-draft', methods=['POST'])
@teacher_required
def delete_draft_course(course_id):
    """Allow a teacher to permanently delete their own draft course."""
    from app.models import Course, db
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    # Only allow deletion for drafts
    is_draft = getattr(course, 'is_draft', False) or getattr(course, 'status', '') == 'draft'
    if not is_draft:
        flash('Only draft courses can be deleted by teachers. Request admin approval to delete published courses.', 'warning')
        return redirect(url_for('teacher.manage_modules', course_id=course.id))

    try:
        title = course.title
        db.session.delete(course)
        db.session.commit()
        flash(f"Draft course '{title}' was deleted.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete draft: {str(e)}', 'danger')
        return redirect(url_for('teacher.manage_modules', course_id=course.id))

    return_url = request.form.get('return_url')
    if return_url:
        return redirect(return_url)
    return redirect(url_for('teacher.my_courses'))

@teacher_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@teacher_required
def profile():
    """Teacher profile edit page"""
    form = ProfileForm()

    if form.validate_on_submit():
        # Verify current password
        if not current_user.verify_password(form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return render_template('teacher/profile.html', form=form)

        # Check for email/username conflicts
        from app.models import User
        if form.email.data != current_user.email:
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already in use by another account', 'danger')
                return render_template('teacher/profile.html', form=form)

        if form.username.data != current_user.username:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash('Username already in use', 'danger')
                return render_template('teacher/profile.html', form=form)

        # Update fields
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        current_user.contact = form.contact.data

        # Handle profile image upload (optional)
        file = request.files.get('profile_image')
        if file and file.filename:
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
            if ext in allowed:
                # Remove old image if any
                if getattr(current_user, 'profile_image', None):
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.profile_image)
                    try:
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception:
                        pass
                new_name = f"avatar_teacher_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
                file.save(save_path)
                current_user.profile_image = new_name

        if form.new_password.data:
            current_user.password = form.new_password.data

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('teacher.profile'))

    # Pre-populate on GET
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = getattr(current_user, 'bio', '')
        form.contact.data = getattr(current_user, 'contact', '')

    return render_template('teacher/profile.html', form=form)

@teacher_bp.route('/course/<int:course_id>/analytics')
@teacher_required
def course_analytics(course_id):
    """Comprehensive analytics dashboard for a course"""
    from app.models import (Course, Enrollment, EnrollmentSection, Section, 
                           Quiz, QuizAttempt, QuizQuestion, QuizAnswer, 
                           Assignment, AssignmentSubmission, User,
                           VideoWatchProgress, VideoInteractiveQuestion, VideoQuestionResponse)
    from sqlalchemy import func
    
    course = Course.query.get_or_404(course_id)
    
    # Verify teacher owns this course
    if course.teacher_id != current_user.id:
        abort(403)
    
    # === BASIC STATS ===
    total_enrollments = Enrollment.query.filter_by(course_id=course_id).count()
    completed_enrollments = Enrollment.query.filter_by(course_id=course_id, completed=True).count()
    completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
    
    # === STUDENT PROGRESS DETAILS ===
    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    total_sections = Section.query.filter_by(course_id=course_id).count()
    
    student_progress = []
    for enrollment in enrollments:
        student = User.query.get(enrollment.student_id)
        completed_sections = EnrollmentSection.query.filter_by(
            enrollment_id=enrollment.id, 
            completed=True
        ).count()
        
        progress_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0
        
        # Total time spent
        total_time = db.session.query(func.sum(EnrollmentSection.time_spent)).filter_by(
            enrollment_id=enrollment.id
        ).scalar() or 0
        
        # Last activity
        last_activity = db.session.query(func.max(EnrollmentSection.last_accessed)).filter_by(
            enrollment_id=enrollment.id
        ).scalar()
        
        # Quiz scores
        quiz_attempts = QuizAttempt.query.filter_by(student_id=student.id).join(
            Quiz
        ).filter(Quiz.section_id.in_(
            [s.id for s in course.sections]
        )).all()
        
        avg_quiz_score = sum([attempt.score for attempt in quiz_attempts]) / len(quiz_attempts) if quiz_attempts else 0
        
        # Assignment submissions
        assignments_submitted = AssignmentSubmission.query.filter_by(student_id=student.id).join(
            Assignment
        ).join(Section).filter(Section.course_id == course_id).count()
        
        total_assignments = Assignment.query.join(Section).filter(
            Section.course_id == course_id
        ).count()
        
        student_progress.append({
            'student': student,
            'enrollment': enrollment,
            'completed_sections': completed_sections,
            'total_sections': total_sections,
            'progress_percentage': round(progress_percentage, 1),
            'total_time_minutes': round(total_time / 60, 1),
            'last_activity': last_activity,
            'avg_quiz_score': round(avg_quiz_score, 1),
            'assignments_submitted': assignments_submitted,
            'total_assignments': total_assignments
        })
    
    # === SECTION-WISE ANALYTICS ===
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()
    section_analytics = []
    
    for section in sections:
        # Completion rate for this section
        section_completions = EnrollmentSection.query.filter_by(
            section_id=section.id,
            completed=True
        ).count()
        
        section_completion_rate = (section_completions / total_enrollments * 100) if total_enrollments > 0 else 0
        
        # Average time spent on this section
        avg_time = db.session.query(func.avg(EnrollmentSection.time_spent)).filter_by(
            section_id=section.id
        ).scalar() or 0
        
        # View count
        total_views = db.session.query(func.sum(EnrollmentSection.view_count)).filter_by(
            section_id=section.id
        ).scalar() or 0
        
        # Dropout point detection (sections with low completion but high starts)
        section_starts = EnrollmentSection.query.filter_by(section_id=section.id).count()
        dropout_rate = ((section_starts - section_completions) / section_starts * 100) if section_starts > 0 else 0
        
        section_analytics.append({
            'section': section,
            'completion_rate': round(section_completion_rate, 1),
            'avg_time_minutes': round(avg_time / 60, 1),
            'total_views': total_views,
            'dropout_rate': round(dropout_rate, 1),
            'is_bottleneck': dropout_rate > 50  # Flag sections where >50% drop out
        })
    
    # === QUIZ PERFORMANCE ANALYTICS ===
    quizzes = Quiz.query.join(Section).filter(Section.course_id == course_id).all()
    quiz_analytics = []
    
    for quiz in quizzes:
        attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).all()
        
        # Show ALL quizzes, even without attempts
        if attempts:
            avg_score = sum([a.score for a in attempts]) / len(attempts)
            max_score = max([a.score for a in attempts])
            min_score = min([a.score for a in attempts])
        else:
            avg_score = 0
            max_score = 0
            min_score = 0
        
        # Question-level analysis
        questions = QuizQuestion.query.filter_by(quiz_id=quiz.id).all()
        question_analysis = []
        
        for question in questions:
            # Count correct vs incorrect answers
            answers = QuizAnswer.query.filter_by(question_id=question.id).all()
            correct_count = sum([1 for a in answers if a.selected_answer == question.correct_answer])
            total_answers = len(answers)
            
            success_rate = (correct_count / total_answers * 100) if total_answers > 0 else 0
            
            question_analysis.append({
                'question': question,
                'success_rate': round(success_rate, 1),
                'total_attempts': total_answers,
                'is_difficult': success_rate < 50  # Flag questions with <50% success
            })
        
        quiz_analytics.append({
            'quiz': quiz,
            'section': quiz.section,
            'total_attempts': len(attempts),
            'avg_score': round(avg_score, 1),
            'max_score': round(max_score, 1),
            'min_score': round(min_score, 1),
            'questions': question_analysis,
            'has_attempts': len(attempts) > 0  # Flag for template
        })
    
    # === ENGAGEMENT METRICS ===
    # Active students (accessed in last 7 days)
    from datetime import datetime, timedelta
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    active_students = db.session.query(func.count(func.distinct(EnrollmentSection.enrollment_id))).join(
        Enrollment
    ).filter(
        Enrollment.course_id == course_id,
        EnrollmentSection.last_accessed >= seven_days_ago
    ).scalar() or 0
    
    # Average session duration
    avg_session_duration = db.session.query(func.avg(EnrollmentSection.time_spent)).join(
        Enrollment
    ).filter(Enrollment.course_id == course_id).scalar() or 0
    
    engagement_metrics = {
        'active_students_7days': active_students,
        'avg_session_minutes': round(avg_session_duration / 60, 1),
        'engagement_rate': round((active_students / total_enrollments * 100), 1) if total_enrollments > 0 else 0
    }
    
    # === VIDEO ANALYTICS ===
    video_sections = Section.query.filter(
        Section.course_id == course_id,
        db.or_(
            Section.section_type == 'video',
            Section.video_url != None,
            Section.media_file.like('%.mp4')
        )
    ).all()
    
    video_analytics = []
    for video_section in video_sections:
        # Get all watch progress for this video
        watch_data = VideoWatchProgress.query.filter_by(section_id=video_section.id).all()
        
        if watch_data:
            total_views = len(watch_data)
            avg_watch_pct = sum([w.watch_percentage for w in watch_data]) / total_views if total_views > 0 else 0
            avg_watch_time = sum([w.total_watch_time for w in watch_data]) / total_views if total_views > 0 else 0
            completed_count = sum([1 for w in watch_data if w.completed])
            completion_rate_video = (completed_count / total_views * 100) if total_views > 0 else 0
            avg_speed = sum([w.playback_speed for w in watch_data]) / total_views if total_views > 0 else 1.0
            total_play_count = sum([w.play_count for w in watch_data])
        else:
            total_views = 0
            avg_watch_pct = 0
            avg_watch_time = 0
            completed_count = 0
            completion_rate_video = 0
            avg_speed = 1.0
            total_play_count = 0
        
        # Get interactive question stats for this video
        interactive_questions = VideoInteractiveQuestion.query.filter_by(section_id=video_section.id).all()
        question_stats = []
        
        for question in interactive_questions:
            responses = VideoQuestionResponse.query.filter_by(question_id=question.id).all()
            if responses:
                correct_count = sum([1 for r in responses if r.is_correct])
                success_rate = (correct_count / len(responses) * 100) if len(responses) > 0 else 0
                avg_time_taken = sum([r.time_taken for r in responses]) / len(responses) if len(responses) > 0 else 0
            else:
                success_rate = 0
                avg_time_taken = 0
            
            question_stats.append({
                'question': question,
                'total_responses': len(responses),
                'success_rate': round(success_rate, 1),
                'avg_time_taken': round(avg_time_taken, 1)
            })
        
        video_analytics.append({
            'section': video_section,
            'total_views': total_views,
            'avg_watch_percentage': round(avg_watch_pct, 1),
            'avg_watch_time_minutes': round(avg_watch_time / 60, 1),
            'completed_count': completed_count,
            'completion_rate': round(completion_rate_video, 1),
            'avg_playback_speed': round(avg_speed, 2),
            'total_play_count': total_play_count,
            'has_interactive_questions': len(interactive_questions) > 0,
            'question_stats': question_stats
        })
    
    return render_template('teacher/course_analytics.html',
                         course=course,
                         total_enrollments=total_enrollments,
                         completed_enrollments=completed_enrollments,
                         completion_rate=round(completion_rate, 1),
                         student_progress=student_progress,
                         section_analytics=section_analytics,
                         quiz_analytics=quiz_analytics,
                         engagement_metrics=engagement_metrics,
                         video_analytics=video_analytics)

@teacher_bp.route('/create-course-wizard', methods=['GET', 'POST'])
@teacher_required
def create_course_wizard():
    from app.models import Course, db
    from app.forms import CourseForm
    from app.course_templates import get_course_template
    import json

    current_step = int(request.args.get('step', 1))
    course_id = request.args.get('course_id')

    # Handle autosave
    if request.method == 'POST' and request.form.get('is_draft') == 'true':
        return handle_autosave()

    # Load existing course if editing draft
    course = None
    if course_id:
        course = Course.query.get_or_404(course_id)
        if course.teacher_id != current_user.id or not course.is_draft:
            abort(403)

    form = CourseForm(obj=course) if course else CourseForm()

    # Handle template selection and pre-population
    if request.method == 'POST':
        selected_template = request.form.get('selected_template', 'blank')
        subject = request.form.get('subject', '')

        # If template is selected and subject provided, pre-populate form
        if selected_template != 'blank' and subject:
            template_data = get_course_template(selected_template, subject)
            if template_data:
                # Pre-populate form with template data
                form.title.data = template_data['title']
                form.description.data = template_data['description']
                # Store template data in session for later steps
                session[f'course_wizard_template_{current_user.id}'] = template_data

    # Load template data from session for later steps
    template_data = session.get(f'course_wizard_template_{current_user.id}')

    # Handle form submission
    if request.method == 'POST':
        action = request.form.get('action')

        # Store current step data in session
        session_key = f'course_wizard_data_{current_user.id}'
        if session_key not in session:
            session[session_key] = {}
        
        # Merge current form data into session (excluding files and CSRF)
        for key, value in request.form.items():
            if key not in ['action', 'csrf_token', 'current_step']:
                session[session_key][key] = value
        session.modified = True

        if action == 'previous':
            current_step = max(1, current_step - 1)
            return redirect(url_for('teacher.create_course_wizard', step=current_step, course_id=course_id))

        elif action == 'next':
            if validate_step(current_step, request.form):
                current_step = min(4, current_step + 1)
                return redirect(url_for('teacher.create_course_wizard', step=current_step, course_id=course_id))
            else:
                flash('Please fill in all required fields.', 'danger')

        elif action == 'create':
            if create_course_from_wizard(session.get(session_key, {})):
                # Clear session data after successful creation
                session.pop(session_key, None)
                session.pop(f'course_wizard_template_{current_user.id}', None)
                flash('Course created successfully!', 'success')
                return redirect(url_for('teacher.my_courses'))
            else:
                flash('Error creating course. Please try again.', 'danger')

    return render_template('teacher/create_course_wizard.html',
                         form=form,
                         current_step=current_step,
                         course=course,
                         template_data=template_data)

def validate_step(step, form_data):
    """Validate form data for current step"""
    if step == 1:
        return bool(form_data.get('title', '').strip() and
                   form_data.get('description', '').strip())
    return True  # Other steps are optional

def create_course_from_wizard(session_data):
    """Create course from wizard form data"""
    try:
        from app.models import Course, db
        import json

        # Merge current request form data with session data
        data = {**session_data, **dict(request.form)}

        # Handle file uploads
        banner_image = None
        pdf_filename = None

        # Banner image
        banner_file = request.files.get('banner_image')
        if banner_file and banner_file.filename:
            if allowed_file(banner_file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
                banner_filename = f"banner_{uuid.uuid4().hex}{os.path.splitext(banner_file.filename)[1]}"
                banner_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], banner_filename)
                banner_file.save(banner_save_path)
                banner_image = banner_filename

        # PDF upload
        if 'pdf_upload' in request.files:
            pdf_file = request.files['pdf_upload']
            if pdf_file and pdf_file.filename and allowed_file(pdf_file.filename):
                pdf_filename = f"course_{uuid.uuid4().hex}.pdf"
                pdf_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
                pdf_file.save(pdf_save_path)

        # Create course
        course = Course(
            title=data.get('title'),
            description=data.get('description'),
            category=data.get('category'),
            difficulty_level=data.get('difficulty_level', 'intermediate'),
            estimated_duration=int(data.get('estimated_duration')) if data.get('estimated_duration') else None,
            language=data.get('language', 'english'),
            learning_objectives=data.get('learning_objectives'),
            prerequisites=data.get('prerequisites'),
            tags=data.get('tags'),
            teacher_id=current_user.id,
            status='draft' if data.get('status') == 'draft' else 'pending',
            banner_image=banner_image,
            pdf_filename=pdf_filename,
            intro_video=data.get('intro_video'),
            is_draft=data.get('status') == 'draft'
        )

        db.session.add(course)
        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        print(f"Error creating course: {e}")
        return False

def handle_autosave():
    """Handle autosave requests"""
    try:
        from app.models import Course, db
        import json

        course_id = request.form.get('course_id')
        course = None

        if course_id:
            course = Course.query.get_or_404(course_id)
            if course.teacher_id != current_user.id:
                return jsonify({'success': False, 'message': 'Unauthorized'})

        # Create or update draft
        if not course:
            course = Course(
                title=request.form.get('title', 'Draft Course'),
                description=request.form.get('description', ''),
                teacher_id=current_user.id,
                is_draft=True,
                status='draft'
            )
            db.session.add(course)
        else:
            # Update existing draft
            course.title = request.form.get('title') or course.title
            course.description = request.form.get('description') or course.description
            course.category = request.form.get('category') or course.category
            course.difficulty_level = request.form.get('difficulty_level') or course.difficulty_level
            course.estimated_duration = int(request.form.get('estimated_duration')) if request.form.get('estimated_duration') else course.estimated_duration
            course.language = request.form.get('language') or course.language
            course.learning_objectives = request.form.get('learning_objectives') or course.learning_objectives
            course.prerequisites = request.form.get('prerequisites') or course.prerequisites
            course.tags = request.form.get('tags') or course.tags

        course.last_autosave = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'course_id': course.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@teacher_bp.route('/save-course-draft', methods=['POST'])
@teacher_required
def save_course_draft():
    """AJAX endpoint for saving course drafts"""
    return handle_autosave()

@teacher_bp.route('/edit-course/<int:course_id>', methods=['GET', 'POST'])
@teacher_required
def edit_course(course_id):
    from app.models import Course, db  # Moved here
    from app.forms import CourseForm  # Moved here
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
    from app.models import Course  # Moved here
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
    from app.models import Course, User, Enrollment, db  # Moved here
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
        
        # Send enrollment notification email
        try:
            send_enrollment_email(student, course)
            flash(f'Student {student.email} enrolled successfully! Notification email sent.', 'success')
        except Exception as e:
            flash(f'Student {student.email} enrolled but email failed to send: {str(e)}', 'warning')
        
        return redirect(url_for('teacher.enroll_students', course_id=course_id))

    enrolled_students = User.query.join(Enrollment).filter(Enrollment.course_id == course.id).all()
    return render_template('teacher/enroll_students.html', course=course, enrolled_students=enrolled_students)

@teacher_bp.route('/course/<int:course_id>/add-section', methods=['GET', 'POST'])
@teacher_required
def create_section(course_id):
    from app.models import Course, Section, db  # Moved here
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
    """Redirect old section management to new module-based system"""
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('You are not authorized to manage this course.', 'danger')
        return redirect(url_for('teacher.my_courses'))
    
    flash('Section management has been updated. Please use the Modules system.', 'info')
    return redirect(url_for('teacher.manage_modules', course_id=course_id))

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/add-assignment', methods=['GET', 'POST'])
@teacher_required
def add_assignment(course_id, section_id):
    from app.models import Course, Section, Assignment, db  # Moved here
    from app.forms import AssignmentForm  # Moved here
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

        # Persist coding assignment fields from the plain HTML controls
        is_coding = request.form.get('is_coding_assignment') == 'on'
        assignment.is_coding_assignment = is_coding
        assignment.programming_language = request.form.get('programming_language') or None
        assignment.starter_code = request.form.get('starter_code') or None
        assignment.enable_code_execution = (request.form.get('enable_code_execution') == 'on') if is_coding else False
        assignment.allow_file_upload = (request.form.get('allow_file_upload') == 'on') if is_coding else True

        db.session.add(assignment)
        db.session.commit()
        flash(('Coding ' if is_coding else '') + 'Assignment created successfully.', 'success')
        return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=section.module_id))
    return render_template('teacher/add_assignment.html', form=form, course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/assignment/<int:assignment_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_assignment(course_id, section_id, assignment_id):
    from app.models import Course, Section, Assignment, db  # Moved here
    from app.forms import AssignmentForm  # Moved here
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    assignment = Assignment.query.get_or_404(assignment_id)
    if section.course_id != course_id or course.teacher_id != current_user.id or assignment.section_id != section_id:
        abort(403)

    form = AssignmentForm(obj=assignment)
    if form.validate_on_submit():
        assignment.title = form.title.data
        assignment.description = form.description.data
        assignment.due_date = form.due_date.data

        # Update coding fields if present
        if 'is_coding_assignment' in request.form:
            is_coding = request.form.get('is_coding_assignment') == 'on'
            assignment.is_coding_assignment = is_coding
            assignment.programming_language = request.form.get('programming_language') or assignment.programming_language
            assignment.starter_code = request.form.get('starter_code') or assignment.starter_code
            assignment.enable_code_execution = (request.form.get('enable_code_execution') == 'on') if is_coding else False
            assignment.allow_file_upload = (request.form.get('allow_file_upload') == 'on') if is_coding else assignment.allow_file_upload

        db.session.commit()
        flash('Assignment updated successfully.', 'success')
        return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=section.module_id))
    return render_template('teacher/edit_assignment.html', form=form, course=course, section=section, assignment=assignment)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/add-quiz', methods=['GET', 'POST'])
@teacher_required
def add_quiz(course_id, section_id):
    from app.models import Course, Section, Quiz, QuizQuestion, db  # Moved here
    from app.forms import QuizForm  # Moved here
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)

    form = QuizForm()
    if form.validate_on_submit():
        # Get quiz settings from form
        time_limit = request.form.get('time_limit', type=int)
        passing_score = request.form.get('passing_score', type=float) or 60.0
        max_attempts = request.form.get('max_attempts', type=int)
        randomize_questions = 'randomize_questions' in request.form
        show_correct_answers = 'show_correct_answers' in request.form
        
        quiz = Quiz(
            title=form.title.data,
            section_id=section_id,
            time_limit=time_limit,
            passing_score=passing_score,
            max_attempts=max_attempts,
            randomize_questions=randomize_questions,
            show_correct_answers=show_correct_answers
        )
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
        return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=section.module_id))
    return render_template('teacher/add_quiz.html', form=form, course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_quiz(course_id, section_id, quiz_id):
    from app.models import Course, Section, Quiz, QuizQuestion, db  # Moved here
    from app.forms import QuizForm  # Moved here
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    quiz = Quiz.query.get_or_404(quiz_id)
    if section.course_id != course_id or course.teacher_id != current_user.id or quiz.section_id != section_id:
        abort(403)

    form = QuizForm(obj=quiz)
    # Pre-populate questions
    if request.method == 'GET':
        for i, question in enumerate(quiz.questions):
            if i < len(form.questions):
                form.questions[i].question.data = question.question_text
                form.questions[i].a.data = question.option_a
                form.questions[i].b.data = question.option_b
                form.questions[i].c.data = question.option_c
                form.questions[i].d.data = question.option_d
                form.questions[i].correct.data = question.correct_answer

    if form.validate_on_submit():
        quiz.title = form.title.data
        # Delete existing questions
        QuizQuestion.query.filter_by(quiz_id=quiz.id).delete()
        # Add new questions
        for q in form.questions.data:
            question = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q['question'],
                option_a=q['a'], option_b=q['b'], option_c=q['c'], option_d=q['d'],
                correct_answer=q['correct']
            )
            db.session.add(question)
        db.session.commit()
        flash('Quiz updated successfully.', 'success')
        return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=section.module_id))
    return render_template('teacher/edit_quiz.html', form=form, course=course, section=section, quiz=quiz)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/submissions')
@teacher_required
def view_submissions(course_id, section_id):
    from app.models import Course, Section, Assignment, AssignmentSubmission  # Moved here
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    assignments = Assignment.query.filter_by(section_id=section_id).all()
    submissions = []
    for assignment in assignments:
        for submission in assignment.submissions:
            submissions.append(submission)
    return render_template('teacher/view_submissions.html', course=course, section=section, submissions=submissions)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/submission/<int:submission_id>/review', methods=['POST'])
@teacher_required
def review_submission(course_id, section_id, submission_id):
    from app.models import Course, Section, AssignmentSubmission, db  # Moved here
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)
    
    feedback = request.form.get('feedback')
    if feedback:
        submission.feedback = feedback
        submission.reviewed = True
        db.session.commit()
        flash('Submission reviewed successfully.', 'success')
    return redirect(url_for('teacher.view_submissions', course_id=course_id, section_id=section_id))

@teacher_bp.route('/course/<int:course_id>/reorder-sections', methods=['POST'])
@teacher_required
def reorder_sections(course_id):
    from app.models import Course, Section, db  # Moved here
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
    from app.models import Section, db  # Moved here
    section = db.session.get(Section, section_id) or abort(404)
    course_id = section.course_id
    module_id = section.module_id
    
    if section.course.teacher_id != current_user.id:
        abort(403)

    try:
        db.session.delete(section)
        db.session.commit()
        flash('Section deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=module_id))

@teacher_bp.route('/submit_feedback/<int:submission_id>', methods=['POST'])
@login_required
@teacher_required
def submit_feedback(submission_id):
    from app.models import AssignmentSubmission, db  # Moved here
    from app.utils.notifications import NotificationService
    
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    if not current_user.is_teacher_for_course(submission.assignment.section.course_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    feedback = data.get('feedback')
    grade = data.get('grade')  # Can be None, float, or null
    
    submission.feedback = feedback
    submission.reviewed = True
    
    # Save grade if provided (0-100 percentage)
    if grade is not None:
        try:
            grade_float = float(grade)
            if 0 <= grade_float <= 100:
                submission.grade = grade_float
            else:
                return jsonify({'success': False, 'message': 'Grade must be between 0 and 100'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid grade format'}), 400
    else:
        # If grade is explicitly null, clear it
        submission.grade = None
    
    db.session.commit()
    
    # Send notification to student
    try:
        grade_text = f"{submission.grade}%" if submission.grade is not None else "reviewed"
        message = f"Your assignment '{submission.assignment.title}' has been {grade_text}"
        if feedback:
            message += f": {feedback[:100]}..."
        
        # Link directly to the assignment page where student can see grade & feedback
        assignment_url = url_for(
            'student.submit_assignment',
            section_id=submission.assignment.section_id,
            assignment_id=submission.assignment_id,
            _external=False
        )
        
        NotificationService.create_notification(
            user_id=submission.student_id,
            notification_type='assignment_feedback',
            title=f'Assignment Graded: {submission.assignment.title}',
            message=message,
            link_url=assignment_url,
            priority='normal',
            related_course_id=submission.assignment.section.course_id,
            related_assignment_id=submission.assignment_id,
            send_email=True
        )
    except Exception as e:
        # Don't fail the feedback submission if notification fails
        print(f"Failed to send notification: {e}")
    
    return jsonify({'success': True})

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/quiz-attempts')
@teacher_required
def view_quiz_attempts(course_id, section_id):
    from app.models import Course, Section, Quiz, QuizAttempt, User, QuizAnswer  # Moved here
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

@teacher_bp.route('/course/<int:course_id>/ratings', methods=['GET'])
@login_required
@teacher_required
def teacher_view_ratings(course_id):
    from app.models import Course, Rating, User, db  # Moved here
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        flash('You can only view ratings for your own courses.', 'error')
        return redirect(url_for('teacher.dashboard'))
    ratings = Rating.query.filter_by(course_id=course_id).join(User, Rating.user_id == User.id).all()
    return render_template('teacher/course_ratings.html', course=course, ratings=ratings)

@teacher_bp.route('/course/<int:course_id>/modules', methods=['GET', 'POST'])
@teacher_required
def manage_modules(course_id):
    """Manage course modules (chapters)"""
    from app.models import Course, Module, Section, Quiz, db
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_module':
            title = request.form.get('title')
            description = request.form.get('description')

            if not title:
                flash('Module title is required.', 'danger')
                return redirect(url_for('teacher.manage_modules', course_id=course_id))

            # Get the highest order number and add 1
            max_order = db.session.query(db.func.max(Module.order)).filter_by(course_id=course_id).scalar() or 0
            new_order = max_order + 1

            module = Module(
                course_id=course_id,
                title=title,
                description=description,
                order=new_order
            )
            db.session.add(module)
            db.session.commit()
            flash('Module created successfully!', 'success')

        elif action == 'delete_module':
            module_id = request.form.get('module_id')
            module = Module.query.get_or_404(module_id)
            if module.course_id != course_id:
                abort(403)

            db.session.delete(module)
            db.session.commit()
            flash('Module deleted successfully!', 'success')

        elif action == 'reorder_modules':
            # Handle drag-and-drop reordering
            order_data = request.get_json()
            for idx, module_id in enumerate(order_data):
                module = Module.query.get(module_id)
                if module and module.course_id == course_id:
                    module.order = idx + 1
            db.session.commit()
            return jsonify({'success': True})

    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    
    # Load sections with their assignments and quizzes for each module
    for module in modules:
        from sqlalchemy.orm import joinedload
        sections = Section.query.options(
            joinedload(Section.assignments),
            joinedload(Section.quizzes).joinedload(Quiz.questions)
        ).filter_by(module_id=module.id).order_by(Section.order).all()
        module.sections = sections
    
    return render_template('teacher/manage_modules.html', course=course, modules=modules)

@teacher_bp.route('/course/<int:course_id>/module/<int:module_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_module(course_id, module_id):
    """Edit a module"""
    from app.models import Course, Module, db
    course = Course.query.get_or_404(course_id)
    module = Module.query.get_or_404(module_id)

    if course.teacher_id != current_user.id or module.course_id != course_id:
        abort(403)

    if request.method == 'POST':
        module.title = request.form.get('title')
        module.description = request.form.get('description')
        db.session.commit()
        flash('Module updated successfully!', 'success')
        return redirect(url_for('teacher.manage_modules', course_id=course_id))

    return render_template('teacher/edit_module.html', course=course, module=module)

@teacher_bp.route('/course/<int:course_id>/module/<int:module_id>/sections', methods=['GET', 'POST'])
@teacher_required
def manage_module_sections(course_id, module_id):
    """Manage sections within a specific module"""
    from app.models import Course, Module, Section, db
    course = Course.query.get_or_404(course_id)
    module = Module.query.get_or_404(module_id)

    if course.teacher_id != current_user.id or module.course_id != course_id:
        abort(403)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_section':
            title = request.form.get('title')
            content = request.form.get('content')
            section_type = request.form.get('section_type', 'text')

            if not title:
                flash('Section title is required.', 'danger')
                return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=module_id))

            # Get the highest order number for this module and add 1
            max_order = db.session.query(db.func.max(Section.order)).filter_by(module_id=module_id).scalar() or 0
            new_order = max_order + 1

            section = Section(
                course_id=course_id,
                module_id=module_id,
                title=title,
                content=content,
                section_type=section_type,
                order=new_order
            )

            # Handle file upload for new section
            if 'media_file' in request.files:
                file = request.files['media_file']
                if file and file.filename:
                    # Validate file type
                    allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mp3'}
                    if '.' in file.filename:
                        extension = file.filename.rsplit('.', 1)[1].lower()
                        if extension in allowed_extensions:
                            # Generate unique filename
                            import uuid
                            import os
                            unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
                            
                            # Ensure upload directory exists
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Save file
                            file_path = os.path.join(upload_dir, unique_filename)
                            file.save(file_path)
                            
                            # Set file on section
                            section.media_file = unique_filename
                        else:
                            flash('Invalid file type. Allowed: PDF, JPG, PNG, GIF, MP4, MP3', 'danger')
                            return redirect(request.url)
                    else:
                        flash('Invalid file format.', 'danger')
                        return redirect(request.url)

            db.session.add(section)
            db.session.commit()
            flash('Section created successfully!', 'success')

        elif action == 'delete_section':
            section_id = request.form.get('section_id')
            if section_id:
                section = Section.query.filter_by(id=section_id, module_id=module_id, course_id=course_id).first()
                if section:
                    db.session.delete(section)
                    db.session.commit()
                    flash('Section deleted successfully!', 'success')
                else:
                    flash('Section not found.', 'danger')
            else:
                flash('Section ID required.', 'danger')

    sections = Section.query.filter_by(module_id=module_id).order_by(Section.order).all()
    return render_template('teacher/manage_module_sections.html', course=course, module=module, sections=sections)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_section(course_id, section_id):
    """Edit a specific section"""
    from app.models import Course, Section, Module, db
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)

    if course.teacher_id != current_user.id or section.course_id != course_id:
        abort(403)

    # Get the module for navigation
    module = Module.query.filter_by(id=section.module_id, course_id=course_id).first()
    if not module:
        abort(404)

    if request.method == 'POST':
        section.title = request.form.get('title')
        section.content = request.form.get('content')
        section.section_type = request.form.get('section_type', 'text')
        section.duration = int(request.form.get('duration', 0)) if request.form.get('duration') else None
        section.video_url = request.form.get('video_url') or None

        # Handle file upload for media_file (especially for presentations)
        if 'media_file' in request.files:
            file = request.files['media_file']
            if file and file.filename:
                # Validate file type and size
                allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mp3'}
                if '.' in file.filename:
                    extension = file.filename.rsplit('.', 1)[1].lower()
                    if extension in allowed_extensions:
                        # Generate unique filename
                        import uuid
                        unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
                        
                        # Ensure upload directory exists
                        import os
                        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
                        os.makedirs(upload_dir, exist_ok=True)
                        
                        # Save file
                        file_path = os.path.join(upload_dir, unique_filename)
                        file.save(file_path)
                        
                        # Update section with new file
                        section.media_file = unique_filename
                    else:
                        flash('Invalid file type. Allowed: PDF, JPG, PNG, GIF, MP4, MP3', 'danger')
                        return redirect(request.url)
                else:
                    flash('Invalid file format.', 'danger')
                    return redirect(request.url)

        # Handle quiz/assignment specific fields if applicable
        if section.section_type == 'quiz':
            # Quiz-specific fields can be added here later
            pass
        elif section.section_type == 'assignment':
            # Assignment-specific fields can be added here later
            pass

        db.session.commit()
        flash('Section updated successfully!', 'success')
        return redirect(url_for('teacher.manage_module_sections', course_id=course_id, module_id=section.module_id))

    return render_template('teacher/edit_section.html', course=course, module=module, section=section, quizzes=section.quizzes, assignments=section.assignments)

@teacher_bp.route('/course/<int:course_id>/preview')
def preview_course(course_id):
    """Preview how the course will look to students - public access for published courses"""
    from app.models import Course, Section, Module
    course = Course.query.get_or_404(course_id)

    # Only allow preview if user is the teacher OR the course is published
    if current_user.is_authenticated and course.teacher_id == current_user.id:
        # Teacher can see all content
        pass
    elif not course.is_published:
        # Unauthenticated users can only see published courses
        abort(404)

    # Get course structure for preview
    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()

    return render_template('teacher/course_preview.html', course=course, modules=modules, sections=sections)

@teacher_bp.route('/course/<int:course_id>/calendar')
@teacher_required
def course_calendar(course_id):
    """Calendar view of all course deadlines"""
    from app.models import Course, Assignment, Section, Module
    from datetime import datetime, timedelta
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Get all assignments with due dates
    assignments = Assignment.query.join(Section).filter(
        Section.course_id == course_id,
        Assignment.due_date.isnot(None)
    ).order_by(Assignment.due_date).all()
    
    # Group assignments by date
    calendar_data = {}
    today = datetime.utcnow().date()
    
    for assignment in assignments:
        date_key = assignment.due_date.date()
        days_until = (date_key - today).days
        
        if date_key not in calendar_data:
            calendar_data[date_key] = {
                'date': date_key,
                'assignments': [],
                'is_past': date_key < today,
                'is_today': date_key == today,
                'is_soon': 0 <= days_until <= 7,
                'days_until': days_until
            }
        
        calendar_data[date_key]['assignments'].append({
            'assignment': assignment,
            'section': assignment.section,
            'module': assignment.section.module
        })
    
    # Convert to sorted list
    calendar_items = sorted(calendar_data.values(), key=lambda x: x['date'])
    
    # Stats
    total_assignments = len(assignments)
    upcoming_assignments = sum(1 for a in assignments if a.due_date and a.due_date.date() >= today)
    past_due = sum(1 for a in assignments if a.due_date and a.due_date.date() < today)
    due_this_week = sum(1 for a in assignments if a.due_date and 0 <= (a.due_date.date() - today).days <= 7)
    
    return render_template('teacher/course_calendar.html',
                         course=course,
                         calendar_items=calendar_items,
                         total_assignments=total_assignments,
                         upcoming_assignments=upcoming_assignments,
                         past_due=past_due,
                         due_this_week=due_this_week)

@teacher_bp.route('/course/<int:course_id>/view-as-student')
@teacher_required
def view_as_student(course_id):
    """View course exactly as students see it"""
    from app.models import Course, Module, Section, Enrollment, EnrollmentSection
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Create a temporary "preview" enrollment to simulate student experience
    # Get course structure
    modules = Module.query.filter_by(course_id=course_id).order_by(Module.order).all()
    
    # Get first enrolled student for realistic preview (if any)
    sample_enrollment = Enrollment.query.filter_by(course_id=course_id).first()
    
    return render_template('teacher/view_as_student.html',
                         course=course,
                         modules=modules,
                         sample_enrollment=sample_enrollment,
                         preview_mode=True)