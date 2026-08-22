from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify, session, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import teacher_required
from app.forms import ProfileForm
from app import db, csrf
from app.utils.email import send_enrollment_email
from app.utils.file_helpers import allowed_file, allowed_file_size
import os
import uuid
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    from app.models import Course, AssignmentSubmission, Assignment, Section  # Moved here
    if current_user.role != 'teacher':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    course_ids = [c.id for c in courses]

    # Count pending (unreviewed) submissions across all teacher's courses
    pending_grading = 0
    if course_ids:
        pending_grading = (
            AssignmentSubmission.query
            .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
            .join(Section, Assignment.section_id == Section.id)
            .join(Course, Section.course_id == Course.id)
            .filter(Course.id.in_(course_ids), AssignmentSubmission.reviewed == False)
            .count()
        )

    return render_template('teacher/dashboard.html', courses=courses, pending_grading=pending_grading)

@teacher_bp.route('/media/<path:filename>')
@login_required
def media(filename):
    """Serve uploaded media files (avatars, banners) for teachers."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

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
@teacher_required
def profile():
    """Teacher profile edit page"""
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
                return render_template('teacher/profile.html', form=form)
            if not current_user.verify_password(curr_pwd):
                flash('Current password is incorrect.', 'danger')
                return render_template('teacher/profile.html', form=form)
            if len(new_pwd) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return render_template('teacher/profile.html', form=form)
            if new_pwd != confirm_pwd:
                flash('New password and confirm password do not match.', 'danger')
                return render_template('teacher/profile.html', form=form)
            
            current_user.password = new_pwd
            password_changed = True
        
        # Update other profile fields
        username_val = (request.form.get('username') or form.username.data or current_user.username).strip()
        email_val = (request.form.get('email') or form.email.data or current_user.email).strip()
        
        from app.models import User
        if email_val != current_user.email:
            existing_user = User.query.filter_by(email=email_val).first()
            if existing_user:
                flash('Email is already in use by another account.', 'danger')
                return render_template('teacher/profile.html', form=form)
        
        if username_val != current_user.username:
            existing_user = User.query.filter_by(username=username_val).first()
            if existing_user:
                flash('Username is already in use.', 'danger')
                return render_template('teacher/profile.html', form=form)
        
        current_user.username = username_val
        current_user.email = email_val
        current_user.bio = request.form.get('bio', current_user.bio or '')
        current_user.contact = request.form.get('contact', current_user.contact or '')
        current_user.first_name = request.form.get('first_name', current_user.first_name or '')
        current_user.last_name = request.form.get('last_name', current_user.last_name or '')
        current_user.specialization = request.form.get('specialization', current_user.specialization or '')
        
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
                    new_name = f"avatar_teacher_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
                    file.save(save_path)
                    current_user.profile_image = new_name
        
        db.session.commit()
        if password_changed:
            flash('Profile and password updated successfully! 🔐', 'success')
        else:
            flash('Profile updated successfully!', 'success')
        return redirect(url_for('teacher.profile'))

    # Pre-populate on GET
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = getattr(current_user, 'bio', '')
        form.contact.data = getattr(current_user, 'contact', '')
        form.first_name.data = getattr(current_user, 'first_name', '')
        form.last_name.data = getattr(current_user, 'last_name', '')
        form.specialization.data = getattr(current_user, 'specialization', '')

    return render_template('teacher/profile.html', form=form)

@teacher_bp.route('/calendar')
@login_required
@teacher_required
def calendar():
    """Teacher calendar index: list courses and quick links."""
    from app.models import Course
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    upcoming = []
    try:
        for c in courses:
            upcoming.append({
                'course': c,
                'sections_count': len(getattr(c, 'sections', []))
            })
    except Exception:
        pass
    return render_template('teacher/calendar.html', courses=courses, upcoming=upcoming)

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
    import uuid

    # If it's an edit mode for an existing draft
    course_id = request.args.get('course_id')
    course = None
    if course_id:
        course = Course.query.get_or_404(course_id)
        if course.teacher_id != current_user.id or not course.is_draft:
            abort(403)
    
    # Use the form
    form = CourseForm(obj=course) if course else CourseForm()

    if request.method == 'POST':
        # Custom validation since we are bypassing some form fields or using direct form access for non-form fields
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not title or not description:
            flash('Title and Description are required options.', 'danger')
        else:
            try:
                if not course:
                    course = Course(
                        teacher_id=current_user.id,
                        status='draft',
                        is_draft=True
                    )
                    db.session.add(course)
                
                # Update fields
                course.title = title
                course.description = description
                course.category = request.form.get('category')
                course.accreditation_name = request.form.get('accreditation_name')
                course.difficulty_level = request.form.get('difficulty_level', 'intermediate')
                course.language = request.form.get('language', 'english')
                course.estimated_duration = int(request.form.get('estimated_duration')) if request.form.get('estimated_duration') else None
                course.learning_objectives = request.form.get('learning_objectives')
                course.prerequisites = request.form.get('prerequisites')
                course.tags = request.form.get('tags')
                
                # Handle optional file uploads if provided immediately
                banner_file = request.files.get('banner_image')
                if banner_file and banner_file.filename:
                    if allowed_file(banner_file.filename, {'png', 'jpg', 'jpeg', 'gif', 'webp'}):
                        from app.utils.cloudinary_helper import upload_file_to_cloudinary
                        cloudinary_url = upload_file_to_cloudinary(banner_file, folder="pace_banners")
                        if cloudinary_url:
                            course.banner_image = cloudinary_url
                        else:
                            ext = os.path.splitext(banner_file.filename)[1]
                            filename = f"banner_{uuid.uuid4().hex}{ext}"
                            banner_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                            course.banner_image = filename
                
                db.session.commit()
                flash('Course created! You can now add modules and content.', 'success')
                
                # Redirect to the course management/dashboard for this course (Phase 2 content builder)
                # Currently we point to my_courses, but ideally we go to the "Notion-like" builder.
                # For now, let's keep it consistent with the user's request to "fix phase 1".
                # We will send them to the edit page or a new "manage course" page.
                # Let's send them to edit_course for now, or maybe create a specific "structure" page later.
                return redirect(url_for('teacher.edit_course', course_id=course.id))

            except Exception as e:
                db.session.rollback()
                flash(f'Error creating course: {str(e)}', 'danger')

    return render_template('teacher/create_course_wizard.html', form=form, course=course)

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

        # Get file uploads from session (already saved in step 2)
        banner_image = data.get('banner_image')
        pdf_filename = data.get('pdf_filename')

        # Create course
        course = Course(
            title=data.get('title'),
            description=data.get('description'),
            category=data.get('category'),
            accreditation_name=data.get('accreditation_name'),
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
            is_draft=data.get('status') == 'draft',
            visibility=data.get('visibility', 'public'),
            is_coming_soon=data.get('is_coming_soon') in ('true', 'on', '1', True),
            max_seats=int(data.get('max_seats')) if data.get('max_seats') and str(data.get('max_seats')).isdigit() else None
        )

        db.session.add(course)
        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating course: {e}", exc_info=True)
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
            course.accreditation_name = request.form.get('accreditation_name') or course.accreditation_name
            course.difficulty_level = request.form.get('difficulty_level') or course.difficulty_level
            course.estimated_duration = int(request.form.get('estimated_duration')) if request.form.get('estimated_duration') else course.estimated_duration
            course.language = request.form.get('language') or course.language
            course.learning_objectives = request.form.get('learning_objectives') or course.learning_objectives
            course.prerequisites = request.form.get('prerequisites') or course.prerequisites
            course.tags = request.form.get('tags') or course.tags

        # Handle banner image upload
        banner_file = request.files.get('banner_image')
        if banner_file and banner_file.filename:
            if allowed_file(banner_file.filename, {'png', 'jpg', 'jpeg', 'gif', 'webp'}):
                from app.utils.cloudinary_helper import upload_file_to_cloudinary
                cloudinary_url = upload_file_to_cloudinary(banner_file, folder="pace_banners")
                if cloudinary_url:
                    course.banner_image = cloudinary_url
                else:
                    banner_filename = f"banner_{uuid.uuid4().hex}{os.path.splitext(banner_file.filename)[1]}"
                    banner_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], banner_filename)
                    banner_file.save(banner_save_path)
                    course.banner_image = banner_filename

        course.last_autosave = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Draft saved', 'course_id': course.id})

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
    if course.teacher_id != current_user.id:
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
                # Try Cloudinary first for persistent storage
                from app.utils.cloudinary_helper import upload_file_to_cloudinary
                cloudinary_url = upload_file_to_cloudinary(pdf, folder="pace_pdfs", resource_type="raw")
                if cloudinary_url:
                    course.pdf_filename = cloudinary_url
                else:
                    save_path = os.path.join(
                        current_app.config['UPLOAD_FOLDER'],
                        pdf_filename
                    )
                    pdf.save(save_path)
                    course.pdf_filename = pdf_filename

            # Handle banner image upload
            banner_file = request.files.get('banner_image')
            if banner_file and banner_file.filename:
                if not allowed_file(banner_file.filename, allowed_extensions={'png', 'jpg', 'jpeg', 'gif', 'webp'}):
                    flash('Only image files (PNG, JPG, JPEG, GIF, WEBP) are allowed for banner', 'danger')
                    return redirect(url_for('teacher.edit_course', course_id=course_id))

                from app.utils.cloudinary_helper import upload_file_to_cloudinary
                cloudinary_url = upload_file_to_cloudinary(banner_file, folder="pace_banners")
                if cloudinary_url:
                    course.banner_image = cloudinary_url
                else:
                    if course.banner_image and not course.banner_image.startswith('http'):
                        old_banner_path = os.path.join(current_app.config['UPLOAD_FOLDER'], course.banner_image)
                        if os.path.exists(old_banner_path):
                            os.remove(old_banner_path)
                    
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

            # Update visibility, coming soon, and max seats
            if 'visibility' in request.form:
                course.visibility = request.form.get('visibility', 'public')
            course.is_coming_soon = request.form.get('is_coming_soon') in ('true', 'on', '1', True)
            if 'max_seats' in request.form:
                seats_val = request.form.get('max_seats', '').strip()
                course.max_seats = int(seats_val) if seats_val.isdigit() else None

            # Update other fields
            form.populate_obj(course)
            db.session.commit()
            flash('Course updated successfully!', 'success')
            next_url = request.referrer or url_for('teacher.course_builder', course_id=course_id)
            return redirect(next_url)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('teacher/edit_course.html', form=form, course=course)

@teacher_bp.route('/my-courses')
@teacher_required
def my_courses():
    from app.models import Course  # Moved here
    status_filter = request.args.get('status', 'all')
    # Teachers can view their owned courses, unassigned courses, and imported Moodle courses
    query = Course.query.filter(
        (Course.teacher_id == current_user.id) | 
        (Course.teacher_id == None) |
        (Course.description.like('%Moodle%'))
    ).order_by(Course.created_at.desc())

    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    courses = query.all()
    return render_template('teacher/my_courses.html', courses=courses, status_filter=status_filter)

@teacher_bp.route('/course/<int:course_id>/claim', methods=['POST'])
@login_required
@teacher_required
def claim_course(course_id):
    from app.models import Course, db
    course = Course.query.get_or_404(course_id)
    course.teacher_id = current_user.id
    db.session.commit()
    flash(f'You are now assigned as the instructor for "{course.title}". You can edit all modules and sections!', 'success')
    return redirect(url_for('teacher.course_builder', course_id=course.id))

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
    from app.models import Course, Section, Assignment, db
    from app.forms import AssignmentForm
    from datetime import datetime

    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)

    # Check if an assignment already exists for this section!
    existing_assignment = Assignment.query.filter_by(section_id=section_id).order_by(Assignment.id.desc()).first()
    if existing_assignment and request.method == 'GET':
        return redirect(url_for('teacher.edit_assignment', course_id=course_id, section_id=section_id, assignment_id=existing_assignment.id))

    form = AssignmentForm()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Assignment title is required.', 'danger')
            return render_template('teacher/add_assignment.html', form=form, course=course, section=section)

        due_date = None
        due_date_str = request.form.get('due_date', '').strip()
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                except ValueError:
                    due_date = None

        if existing_assignment:
            assignment = existing_assignment
            assignment.title = title
            assignment.description = description
            assignment.due_date = due_date
        else:
            assignment = Assignment(
                title=title,
                description=description,
                section_id=section_id,
                due_date=due_date
            )
            db.session.add(assignment)

        # Persist coding assignment fields from the plain HTML controls
        is_coding = request.form.get('is_coding_assignment') == 'on' or request.form.get('submission_type') == 'code'
        assignment.is_coding_assignment = is_coding
        assignment.programming_language = request.form.get('programming_language') or None
        assignment.starter_code = request.form.get('starter_code') or None
        assignment.enable_code_execution = (request.form.get('enable_code_execution') == 'on') if is_coding else False
        assignment.allow_file_upload = (request.form.get('allow_file_upload') == 'on') if is_coding else True

        db.session.commit()
        flash('Assignment saved successfully.', 'success')
        return redirect(url_for('teacher.course_builder', course_id=course_id))

    return render_template('teacher/add_assignment.html', form=form, course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/assignment/<int:assignment_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_assignment(course_id, section_id, assignment_id):
    from app.models import Course, Section, Assignment, db
    from app.forms import AssignmentForm
    from datetime import datetime

    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    assignment = Assignment.query.get_or_404(assignment_id)
    if section.course_id != course_id or course.teacher_id != current_user.id or assignment.section_id != section_id:
        abort(403)

    form = AssignmentForm(obj=assignment)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Assignment title is required.', 'danger')
            return render_template('teacher/edit_assignment.html', form=form, course=course, section=section, assignment=assignment)

        assignment.title = title
        assignment.description = description

        due_date_str = request.form.get('due_date', '').strip()
        if due_date_str:
            try:
                assignment.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                try:
                    assignment.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                except ValueError:
                    assignment.due_date = None
        else:
            assignment.due_date = None

        if 'is_coding_assignment' in request.form or 'submission_type' in request.form:
            is_coding = request.form.get('is_coding_assignment') == 'on' or request.form.get('submission_type') == 'code'
            assignment.is_coding_assignment = is_coding
            assignment.programming_language = request.form.get('programming_language') or assignment.programming_language
            assignment.starter_code = request.form.get('starter_code') or assignment.starter_code
            assignment.enable_code_execution = (request.form.get('enable_code_execution') == 'on') if is_coding else False

        db.session.commit()
        flash('Assignment updated successfully.', 'success')
        return redirect(url_for('teacher.course_builder', course_id=course_id))

    return render_template('teacher/edit_assignment.html', form=form, course=course, section=section, assignment=assignment)

def _save_quiz_questions(quiz_id, form_data):
    from app.models import QuizQuestion, db
    questions_data = {}
    for key in form_data:
        if key.startswith('q_') and '_' in key[2:]:
            parts = key.split('_')
            if len(parts) >= 3:
                q_id = parts[1]
                field = parts[-1]  # text, a, b, c, d, correct
                if q_id not in questions_data:
                    questions_data[q_id] = {'question': '', 'a': '', 'b': '', 'c': '', 'd': '', 'correct': 'a'}
                if field == 'text':
                    questions_data[q_id]['question'] = form_data[key].strip()
                elif field in ['a', 'b', 'c', 'd']:
                    questions_data[q_id][field] = form_data[key].strip()
                elif field == 'correct':
                    questions_data[q_id]['correct'] = form_data[key].strip()

    for q_id, q in questions_data.items():
        if q['question'] and q['a'] and q['b']:
            question = QuizQuestion(
                quiz_id=quiz_id,
                question_text=q['question'],
                option_a=q['a'],
                option_b=q['b'],
                option_c=q.get('c') or None,
                option_d=q.get('d') or None,
                correct_answer=q.get('correct', 'a')
            )
            db.session.add(question)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/add-quiz', methods=['GET', 'POST'])
@teacher_required
def add_quiz(course_id, section_id):
    from app.models import Course, Section, Quiz, db
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    if section.course_id != course_id or course.teacher_id != current_user.id:
        abort(403)

    existing_quiz = Quiz.query.filter_by(section_id=section_id).order_by(Quiz.id.desc()).first()
    if existing_quiz and request.method == 'GET':
        return redirect(url_for('teacher.edit_quiz', course_id=course_id, section_id=section_id, quiz_id=existing_quiz.id))

    if request.method == 'POST':
        title = request.form.get('title', 'New Quiz').strip()
        if not title:
            flash('Quiz title is required', 'danger')
            return render_template('teacher/add_quiz.html', course=course, section=section)

        try:
            if existing_quiz:
                quiz = existing_quiz
                quiz.title = title
                quiz.time_limit = int(request.form.get('time_limit')) if request.form.get('time_limit') else None
                quiz.passing_score = int(request.form.get('passing_score', 60))
                from app.models import QuizQuestion
                QuizQuestion.query.filter_by(quiz_id=quiz.id).delete()
            else:
                quiz = Quiz(
                    title=title,
                    section_id=section_id,
                    time_limit=int(request.form.get('time_limit')) if request.form.get('time_limit') else None,
                    passing_score=int(request.form.get('passing_score', 60)),
                    max_attempts=int(request.form.get('max_attempts')) if request.form.get('max_attempts') else None
                )
                db.session.add(quiz)
                db.session.flush()

            _save_quiz_questions(quiz.id, request.form)
            db.session.commit()
            flash('Quiz saved successfully!', 'success')
            return redirect(url_for('teacher.course_builder', course_id=course.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving quiz: {str(e)}', 'danger')

    return render_template('teacher/add_quiz.html', course=course, section=section)

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/quiz/<int:quiz_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_quiz(course_id, section_id, quiz_id):
    from app.models import Course, Section, Quiz, QuizQuestion, db
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    quiz = Quiz.query.get_or_404(quiz_id)
    if section.course_id != course_id or course.teacher_id != current_user.id or quiz.section_id != section_id:
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', quiz.title).strip()
        if not title:
            flash('Quiz title is required', 'danger')
            return render_template('teacher/add_quiz.html', course=course, section=section, quiz=quiz)

        try:
            quiz.title = title
            quiz.passing_score = int(request.form.get('passing_score', 60))
            quiz.time_limit = int(request.form.get('time_limit')) if request.form.get('time_limit') else None

            QuizQuestion.query.filter_by(quiz_id=quiz.id).delete()
            _save_quiz_questions(quiz.id, request.form)

            db.session.commit()
            flash('Quiz updated successfully.', 'success')
            return redirect(url_for('teacher.course_builder', course_id=course.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating quiz: {str(e)}', 'danger')

    return render_template('teacher/add_quiz.html', course=course, section=section, quiz=quiz)

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
        data = request.get_json()
        if isinstance(data, dict):
            section_ids = data.get('section_ids', [])
            module_id = data.get('module_id')
        else:
            section_ids = data
            module_id = None

        for idx, section_id in enumerate(section_ids):
            section = Section.query.get(section_id)
            if section and section.course_id == course_id:
                section.order = idx + 1
                if module_id:
                    section.module_id = module_id
        db.session.commit()
        return jsonify({"message": "Sections reordered successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@teacher_bp.route('/course/<int:course_id>/reorder-modules', methods=['POST'])
@teacher_required
def reorder_modules(course_id):
    from app.models import Course, Module, db
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    try:
        order_data = request.get_json()
        for idx, module_id in enumerate(order_data):
            module = Module.query.get(module_id)
            if module and module.course_id == course_id:
                module.order = idx + 1
        db.session.commit()
        return jsonify({"message": "Modules reordered successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



@teacher_bp.route('/submit_feedback/<int:submission_id>', methods=['POST'])
@login_required
@teacher_required
def submit_feedback(submission_id):
    from app.models import AssignmentSubmission, db  # Moved here
    from app.utils.notifications import NotificationService
    
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    course = submission.assignment.section.course
    if course.teacher_id is None:
        course.teacher_id = current_user.id
        db.session.commit()
    elif not current_user.is_teacher_for_course(course.id) and current_user.role != 'admin':
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
    """Old module manager - now redirects to builder"""
    return redirect(url_for('teacher.course_builder', course_id=course_id))

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
        flash('Topic updated successfully!', 'success')
        return redirect(url_for('teacher.course_builder', course_id=course_id))

    return render_template('teacher/edit_module.html', course=course, module=module)

@teacher_bp.route('/course/<int:course_id>/module/<int:module_id>/sections', methods=['GET', 'POST'])
@teacher_required
def manage_module_sections(course_id, module_id):
    """Old module section manager - now redirects to builder"""
    return redirect(url_for('teacher.course_builder', course_id=course_id))

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
        section.section_type = request.form.get('section_type', 'lesson')
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
                        
                        # Try Cloudinary first for persistent storage
                        from app.utils.cloudinary_helper import upload_file_to_cloudinary
                        resource = "raw" if extension in ('pdf', 'mp3') else ("video" if extension == 'mp4' else "image")
                        cloudinary_url = upload_file_to_cloudinary(file, folder="pace_media", resource_type=resource)
                        if cloudinary_url:
                            section.media_file = cloudinary_url
                        else:
                            # Fallback to local disk
                            import os
                            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
                            os.makedirs(upload_dir, exist_ok=True)
                            file_path = os.path.join(upload_dir, unique_filename)
                            file.save(file_path)
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

@teacher_bp.route('/gradebook')
@login_required
@teacher_required
def gradebook():
    """Main gradebook overview showing all courses with grading summaries"""
    from app.models import Course, Enrollment, AssignmentSubmission, QuizAttempt, Assignment, Quiz, Section
    from sqlalchemy import func
    
    # Get all courses for this teacher
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    
    gradebook_data = []
    
    for course in courses:
        # Get enrollments for this course
        enrollments = Enrollment.query.filter_by(course_id=course.id).all()
        total_students = len(enrollments)
        
        # Get all assignments and quizzes in this course
        assignments = Assignment.query.join(Section).filter(Section.course_id == course.id).all()
        quizzes = Quiz.query.join(Section).filter(Section.course_id == course.id).all()
        
        total_assignments = len(assignments)
        total_quizzes = len(quizzes)
        
        # Count graded vs ungraded submissions
        graded_submissions = 0
        total_submissions = 0
        
        for assignment in assignments:
            submissions = AssignmentSubmission.query.filter_by(assignment_id=assignment.id).all()
            total_submissions += len(submissions)
            graded_submissions += sum(1 for s in submissions if s.reviewed)
        
        # Count graded quiz attempts
        quiz_attempts = 0
        for quiz in quizzes:
            attempts = QuizAttempt.query.filter_by(quiz_id=quiz.id).all()
            quiz_attempts += len(attempts)
        
        # Calculate completion and grading percentages
        completion_rate = (sum(1 for e in enrollments if e.completed) / total_students * 100) if total_students > 0 else 0
        grading_completion = (graded_submissions / total_submissions * 100) if total_submissions > 0 else 100
        
        gradebook_data.append({
            'course': course,
            'total_students': total_students,
            'total_assignments': total_assignments,
            'total_quizzes': total_quizzes,
            'total_submissions': total_submissions,
            'graded_submissions': graded_submissions,
            'quiz_attempts': quiz_attempts,
            'completion_rate': round(completion_rate, 1),
            'grading_completion': round(grading_completion, 1),
            'needs_grading': total_submissions - graded_submissions
        })
    
    return render_template('teacher/gradebook.html', gradebook_data=gradebook_data)

@teacher_bp.route('/course/<int:course_id>/gradebook')
@teacher_required
def course_gradebook(course_id):
    """Detailed gradebook view for a specific course"""
    from app.models import Course, Enrollment, AssignmentSubmission, QuizAttempt, Assignment, Quiz, Section, User
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Get all enrollments for this course
    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    
    # Get all assignments and quizzes in this course
    assignments = Assignment.query.join(Section).filter(Section.course_id == course_id).order_by(Assignment.due_date).all()
    quizzes = Quiz.query.join(Section).filter(Section.course_id == course_id).order_by(Quiz.id).all()
    
    # Build student grade data
    student_grades = []
    
    for enrollment in enrollments:
        student = User.query.get(enrollment.student_id)
        
        # Get grades for all assignments
        assignment_grades = {}
        for assignment in assignments:
            submission = AssignmentSubmission.query.filter_by(
                assignment_id=assignment.id, 
                student_id=student.id
            ).first()
            if submission and submission.grade is not None:
                assignment_grades[assignment.id] = {
                    'grade': submission.grade,
                    'reviewed': submission.reviewed,
                    'submitted_at': submission.submitted_at
                }
            else:
                assignment_grades[assignment.id] = None
        
        # Get grades for all quizzes
        quiz_grades = {}
        for quiz in quizzes:
            attempt = QuizAttempt.query.filter_by(
                quiz_id=quiz.id,
                student_id=student.id
            ).order_by(QuizAttempt.attempted_at.desc()).first()
            if attempt:
                quiz_grades[quiz.id] = {
                    'score': attempt.score,
                    'attempted_at': attempt.attempted_at
                }
            else:
                quiz_grades[quiz.id] = None
        
        # Calculate overall grade (weighted average)
        total_points = 0
        earned_points = 0
        
        # Assignments count as 60% of grade, quizzes as 40%
        assignment_weight = 0.6
        quiz_weight = 0.4
        
        # Calculate assignment average
        assignment_scores = [grade['grade'] for grade in assignment_grades.values() if grade is not None]
        assignment_avg = sum(assignment_scores) / len(assignment_scores) if assignment_scores else 0
        
        # Calculate quiz average  
        quiz_scores = [grade['score'] for grade in quiz_grades.values() if grade is not None]
        quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0
        
        # Overall grade
        if assignments or quizzes:
            overall_grade = (assignment_avg * assignment_weight + quiz_avg * quiz_weight)
        else:
            overall_grade = 0
        
        student_grades.append({
            'student': student,
            'enrollment': enrollment,
            'assignment_grades': assignment_grades,
            'quiz_grades': quiz_grades,
            'assignment_avg': round(assignment_avg, 1) if assignment_scores else None,
            'quiz_avg': round(quiz_avg, 1) if quiz_scores else None,
            'overall_grade': round(overall_grade, 1) if overall_grade > 0 else None
        })
    
    # Sort by overall grade (highest first)
    student_grades.sort(key=lambda x: x['overall_grade'] or 0, reverse=True)
    
    return render_template('teacher/course_gradebook.html',
                         course=course,
                         assignments=assignments,
                         quizzes=quizzes,
                         student_grades=student_grades)

@teacher_bp.route('/course/<int:course_id>/bulk-grade')
@teacher_required
def bulk_grade_course(course_id):
    """Bulk grading interface for a course"""
    from app.models import Course, AssignmentSubmission, Assignment, Section
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Get all ungraded submissions
    ungraded_submissions = AssignmentSubmission.query.join(Assignment).join(Section).filter(
        Section.course_id == course_id,
        AssignmentSubmission.reviewed == False
    ).order_by(AssignmentSubmission.submitted_at).all()
    
    # Group by assignment
    submissions_by_assignment = {}
    for submission in ungraded_submissions:
        assignment_id = submission.assignment_id
        if assignment_id not in submissions_by_assignment:
            submissions_by_assignment[assignment_id] = {
                'assignment': submission.assignment,
                'submissions': []
            }
        submissions_by_assignment[assignment_id]['submissions'].append(submission)
    
    return render_template('teacher/bulk_grade.html',
                         course=course,
                         submissions_by_assignment=submissions_by_assignment,
                         total_ungraded=len(ungraded_submissions))

@teacher_bp.route('/course/<int:course_id>/student/<int:student_id>/grades')
@teacher_required
def student_detail_grades(course_id, student_id):
    """Detailed view of a student's grades in a course"""
    from app.models import Course, User, Enrollment, AssignmentSubmission, QuizAttempt, Assignment, Quiz, Section
    
    course = Course.query.get_or_404(course_id)
    student = User.query.get_or_404(student_id)
    
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Get enrollment
    enrollment = Enrollment.query.filter_by(course_id=course_id, student_id=student_id).first()
    if not enrollment:
        abort(404)
    
    # Get all assignments and quizzes
    assignments = Assignment.query.join(Section).filter(Section.course_id == course_id).all()
    quizzes = Quiz.query.join(Section).filter(Section.course_id == course_id).all()
    
    # Get student's submissions and attempts
    assignment_data = []
    for assignment in assignments:
        submissions = AssignmentSubmission.query.filter_by(
            assignment_id=assignment.id,
            student_id=student_id
        ).order_by(AssignmentSubmission.submitted_at.desc()).all()
        
        graded_scores = [s.grade for s in submissions if s.grade is not None]
        best_grade = max(graded_scores) if graded_scores else None
        latest_submission = submissions[0] if submissions else None
        has_pending = any(not s.reviewed for s in submissions)
        
        assignment_data.append({
            'assignment': assignment,
            'submission': latest_submission,
            'submissions': submissions,
            'best_grade': best_grade,
            'status': 'graded' if graded_scores else ('submitted' if submissions else 'not_submitted'),
            'has_pending': has_pending
        })
    
    quiz_data = []
    for quiz in quizzes:
        attempts = QuizAttempt.query.filter_by(
            quiz_id=quiz.id,
            student_id=student_id
        ).order_by(QuizAttempt.attempted_at.desc()).all()
        
        quiz_data.append({
            'quiz': quiz,
            'attempts': attempts,
            'best_score': max([a.score for a in attempts]) if attempts else None
        })
    
    # Calculate overall statistics
    total_assignments = len(assignments)
    graded_assignments = sum(1 for a in assignment_data if a['status'] == 'graded')
    submitted_assignments = sum(1 for a in assignment_data if a['submission'])
    
    total_quizzes = len(quizzes)
    attempted_quizzes = sum(1 for q in quiz_data if q['attempts'])
    
    # Grade averages (uses official best score across attempts)
    assignment_grades = [a['best_grade'] for a in assignment_data if a['best_grade'] is not None]
    assignment_avg = sum(assignment_grades) / len(assignment_grades) if assignment_grades else None
    
    quiz_scores = [q['best_score'] for q in quiz_data if q['best_score'] is not None]
    quiz_avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else None
    
    # Overall grade (60% assignments, 40% quizzes)
    overall_grade = None
    if assignment_avg is not None or quiz_avg is not None:
        assignment_contrib = (assignment_avg or 0) * 0.6
        quiz_contrib = (quiz_avg or 0) * 0.4
        overall_grade = assignment_contrib + quiz_contrib
    
    return render_template('teacher/student_detail_grades.html',
                         course=course,
                         student=student,
                         enrollment=enrollment,
                         assignment_data=assignment_data,
                         quiz_data=quiz_data,
                         stats={
                             'total_assignments': total_assignments,
                             'graded_assignments': graded_assignments,
                             'submitted_assignments': submitted_assignments,
                             'total_quizzes': total_quizzes,
                             'attempted_quizzes': attempted_quizzes,
                             'assignment_avg': round(assignment_avg, 1) if assignment_avg else None,
                             'quiz_avg': round(quiz_avg, 1) if quiz_avg else None,
                             'overall_grade': round(overall_grade, 1) if overall_grade else None
                         })

@teacher_bp.route('/serve-upload/<path:filename>')
@login_required
def serve_upload(filename):
    """Serve uploaded student assignment files reliably with inline and download support."""
    from flask import render_template_string, request, send_from_directory, redirect, current_app
    upload_dir = current_app.config['UPLOAD_FOLDER']
    clean_filename = filename.lstrip('/')
    is_download = request.args.get('download') == '1'
    
    if clean_filename.startswith(('http://', 'https://')):
        target_url = clean_filename
        # Auto-fix Cloudinary URLs where PDFs were uploaded as image/upload instead of raw/upload
        if clean_filename.lower().endswith('.pdf') and '/image/upload/' in clean_filename:
            target_url = clean_filename.replace('/image/upload/', '/raw/upload/')
        return redirect(target_url)

    mimetype = None
    if clean_filename.lower().endswith('.pdf'):
        mimetype = 'application/pdf'

    target_path = os.path.join(upload_dir, clean_filename)
    if os.path.exists(target_path):
        return send_from_directory(upload_dir, clean_filename, as_attachment=is_download, mimetype=mimetype)

    static_dir = os.path.join(current_app.root_path, 'static')
    if os.path.exists(os.path.join(static_dir, clean_filename)):
        return send_from_directory(static_dir, clean_filename, as_attachment=is_download, mimetype=mimetype)
    elif os.path.exists(os.path.join(static_dir, 'uploads', clean_filename)):
        return send_from_directory(os.path.join(static_dir, 'uploads'), clean_filename, as_attachment=is_download, mimetype=mimetype)

    # Friendly fallback explaining ephemeral storage reset
    return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>File Notice - Pace Academy</title><script src="https://cdn.tailwindcss.com"></script></head>
        <body class="bg-gray-50 h-screen flex items-center justify-center p-4">
            <div class="bg-white p-8 rounded-3xl shadow-xl border border-gray-100 max-w-md text-center">
                <div class="text-5xl mb-4">⚠️</div>
                <h3 class="text-xl font-extrabold text-gray-900 mb-2">File Notice</h3>
                <p class="text-sm text-gray-600 mb-6 leading-relaxed">
                    This file was saved during a previous deployment session and has expired from local temporary storage. Please ask the student to re-submit if needed.
                </p>
                <button onclick="window.close()" class="px-6 py-2.5 bg-indigo-600 text-white font-bold text-xs rounded-xl shadow hover:bg-indigo-700 transition">Close Window</button>
            </div>
        </body>
        </html>
    '''), 404

@teacher_bp.route('/preview-submission/<int:submission_id>')
@teacher_required
def preview_submission(submission_id):
    """AJAX endpoint to preview a submission and return all sibling attempt records"""
    from app.models import AssignmentSubmission, db
    from flask import url_for
    
    submission = AssignmentSubmission.query.get_or_404(submission_id)
    course = submission.assignment.section.course
    
    if course.teacher_id is None:
        course.teacher_id = current_user.id
        db.session.commit()
    elif not current_user.is_teacher_for_course(course.id) and current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    # Fetch all attempts for this student & assignment
    sibling_submissions = AssignmentSubmission.query.filter_by(
        assignment_id=submission.assignment_id,
        student_id=submission.student_id
    ).order_by(AssignmentSubmission.submitted_at.desc()).all()
    
    attempts_list = []
    for sub in sibling_submissions:
        f_url = None
        if sub.file_path:
            clean_fp = sub.file_path
            if clean_fp.startswith(('http://', 'https://')):
                if clean_fp.lower().endswith('.pdf') and '/image/upload/' in clean_fp:
                    clean_fp = clean_fp.replace('/image/upload/', '/raw/upload/')
                f_url = url_for('teacher.serve_upload', filename=clean_fp)
            else:
                f_url = url_for('teacher.serve_upload', filename=clean_fp.lstrip('/'))
        
        attempts_list.append({
            'id': sub.id,
            'attempt_number': sub.attempt_number or (len(sibling_submissions) - sibling_submissions.index(sub)),
            'submission_text': sub.submission_text or '',
            'submission_type': sub.submission_type or 'text',
            'code_submission': sub.code_submission or '',
            'programming_language': sub.programming_language or '',
            'file_path': sub.file_path or '',
            'file_url': f_url or '',
            'feedback': sub.feedback or '',
            'grade': sub.grade,
            'reviewed': sub.reviewed,
            'submitted_at': sub.submitted_at.strftime('%d %b %Y, %H:%M') if sub.submitted_at else ''
        })

    return jsonify({
        'current_id': submission.id,
        'assignment_title': submission.assignment.title,
        'attempts': attempts_list
    })
    
@teacher_bp.route('/course/<int:course_id>/builder')
@teacher_required
def course_builder(course_id):
    """Notion-style course content builder"""
    from app.models import Course, Module, Section, db
    course = Course.query.get_or_404(course_id)
    # If course is unassigned or imported, auto-assign current teacher
    if course.teacher_id is None:
        course.teacher_id = current_user.id
        db.session.commit()
    
    # Ensure modules are loaded with sections
    modules = Module.query.filter_by(course_id=course.id).order_by(Module.order).all()
    
    return render_template('teacher/course_builder.html', course=course, modules=modules)

@teacher_bp.route('/course-builder/<int:course_id>')
@teacher_required
def course_builder_alias(course_id):
    """Alias redirect for course builder"""
    return redirect(url_for('teacher.course_builder', course_id=course_id))

@teacher_bp.route('/course/<int:course_id>/submit-review', methods=['POST'])
@teacher_required
def submit_course_for_review(course_id):
    """Change status from draft to pending for admin approval"""
    from app.models import Course, db
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    # Only allow submission if it's currently a draft or rejected
    if course.status in ['draft', 'rejected']:
        course.status = 'pending'
        course.is_draft = False
        db.session.commit()
        flash('Course submitted for admin review!', 'success')
    else:
        flash('Course is already pending or approved.', 'info')
        
    return redirect(url_for('teacher.my_courses'))

@teacher_bp.route('/course/<int:course_id>/quick-create-module', methods=['POST'])
@teacher_required
def quick_create_module(course_id):
    from app.models import Course, Module, db
    from sqlalchemy import func
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    title = data.get('title')
    
    if not title:
        return jsonify({'success': False, 'message': 'Title required'}), 400
        
    # Get max order
    max_order = db.session.query(func.max(Module.order)).filter_by(course_id=course_id).scalar() or 0
    
    module = Module(
        title=title,
        course_id=course.id,
        order=max_order + 1
    )
    db.session.add(module)
    db.session.commit()
    
    return jsonify({'success': True, 'module_id': module.id})

@teacher_bp.route('/course/<int:course_id>/quick-create-section', methods=['POST'])
@teacher_required
def quick_create_section(course_id):
    from app.models import Course, Section, Module, Quiz, Assignment, db, ACTIVITY_TYPES
    from sqlalchemy import func
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    module_id = data.get('module_id')
    activity_type = data.get('type', 'lesson')
    title = data.get('title', 'Untitled')

    # Validate type
    if activity_type not in ACTIVITY_TYPES:
        activity_type = 'lesson'

    module = Module.query.get(module_id)
    if not module or module.course_id != course_id:
        return jsonify({'success': False, 'message': 'Invalid topic'}), 400

    max_order = db.session.query(func.max(Section.order)).filter_by(module_id=module_id).scalar() or 0

    section = Section(
        title=title,
        section_type=activity_type,
        course_id=course_id,
        module_id=module_id,
        order=max_order + 1,
        content=''
    )
    db.session.add(section)
    db.session.flush()  # get section.id

    # Auto-create the Quiz or Assignment row so teachers can immediately add content
    if activity_type == 'quiz':
        quiz = Quiz(
            section_id=section.id,
            title=title,
            passing_score=70.0,
            time_limit=30,
            max_attempts=3,
            show_correct_answers=True,
        )
        db.session.add(quiz)
    elif activity_type == 'assignment':
        assignment = Assignment(
            section_id=section.id,
            title=title,
            description='',
            allow_file_upload=True,
        )
        db.session.add(assignment)

    db.session.commit()
    return jsonify({'success': True, 'section_id': section.id, 'activity_type': activity_type})

@teacher_bp.route('/delete-module/<int:module_id>', methods=['POST'])
@teacher_required
def delete_module(module_id):
    from app.models import Module, Section, EnrollmentSection, VideoWatchProgress, VideoInteractiveQuestion, VideoSubtitle, db
    module = Module.query.get_or_404(module_id)
    # Check ownership via course
    if module.course.teacher_id != current_user.id:
        return jsonify({'success': False}), 403
        
    try:
        # Get all sections inside this module
        sections = Section.query.filter_by(module_id=module.id).all()
        for section in sections:
            # Delete referencing progress and tracking rows first
            VideoWatchProgress.query.filter_by(section_id=section.id).delete(synchronize_session=False)
            iqs = VideoInteractiveQuestion.query.filter_by(section_id=section.id).all()
            for iq in iqs:
                db.session.delete(iq)
            VideoSubtitle.query.filter_by(section_id=section.id).delete(synchronize_session=False)
            EnrollmentSection.query.filter_by(section_id=section.id).delete(synchronize_session=False)
            
            # Delete section
            db.session.delete(section)
            
        # Finally delete the module
        db.session.delete(module)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@teacher_bp.route('/delete-section/<int:section_id>', methods=['POST'])
@teacher_required
def delete_section(section_id):
    from app.models import Section, EnrollmentSection, VideoWatchProgress, VideoInteractiveQuestion, VideoSubtitle, db
    section = Section.query.get_or_404(section_id)
    # Check ownership via course
    if section.course.teacher_id != current_user.id:
        return jsonify({'success': False}), 403
        
    try:
        # Delete referencing VideoWatchProgress
        VideoWatchProgress.query.filter_by(section_id=section.id).delete(synchronize_session=False)
        
        # Delete referencing VideoInteractiveQuestion
        iqs = VideoInteractiveQuestion.query.filter_by(section_id=section.id).all()
        for iq in iqs:
            db.session.delete(iq)
            
        # Delete referencing VideoSubtitle
        VideoSubtitle.query.filter_by(section_id=section.id).delete(synchronize_session=False)
        
        # Delete referencing EnrollmentSection
        EnrollmentSection.query.filter_by(section_id=section.id).delete(synchronize_session=False)
        
        # Finally delete the section
        db.session.delete(section)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@teacher_bp.route('/course/<int:course_id>/section/<int:section_id>/edit-content', methods=['GET', 'POST'])
@teacher_required
def edit_section_content(course_id, section_id):
    """Dedicated simplified content editor"""
    from app.models import Course, Section, db
    course = Course.query.get_or_404(course_id)
    section = Section.query.get_or_404(section_id)
    
    if section.course_id != course_id:
        abort(404)
    if course.teacher_id is None:
        course.teacher_id = current_user.id
        db.session.commit()
        
    if request.method == 'POST':
        section.title = request.form.get('title')
        section.content = request.form.get('content')
        section.video_url = request.form.get('video_url')
        # Handle file uploads
        if 'media_file' in request.files:
            file = request.files['media_file']
            if file and file.filename:
                from werkzeug.utils import secure_filename
                import os
                import uuid
                
                # Basic validation
                ext = os.path.splitext(file.filename)[1].lower()
                if ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.ppt', '.pptx']:
                    filename = secure_filename(f"{uuid.uuid4().hex[:8]}_{file.filename}")
                    # Try Cloudinary first for persistent storage
                    from app.utils.cloudinary_helper import upload_file_to_cloudinary
                    resource = "raw" if ext in ('.pdf', '.doc', '.docx', '.ppt', '.pptx') else "image"
                    cloudinary_url = upload_file_to_cloudinary(file, folder="pace_media", resource_type=resource)
                    if cloudinary_url:
                        section.media_file = cloudinary_url
                    else:
                        upload_path = os.path.join(current_app.root_path, 'static/uploads')
                        os.makedirs(upload_path, exist_ok=True)
                        file.save(os.path.join(upload_path, filename))
                        section.media_file = filename
        
        db.session.commit()
        flash('Content updated!', 'success')
        return redirect(url_for('teacher.course_builder', course_id=course_id))
        
    return render_template('teacher/simple_content_editor.html', course=course, section=section)


@teacher_bp.route('/live-classrooms', methods=['GET'])
@teacher_required
def live_classrooms():
    """List all scheduled, live, and past virtual classrooms for the teacher's courses"""
    from app.models import LiveSession, Course, LiveAttendance
    from datetime import datetime, timedelta

    # Auto-expire stale live sessions whose duration has passed
    now = datetime.utcnow()
    stale_sessions = LiveSession.query.filter_by(status='live').all()
    for s in stale_sessions:
        start_ref = s.started_at or s.scheduled_at
        if start_ref and now > (start_ref + timedelta(minutes=s.duration_minutes or 60)):
            s.status = 'ended'
            s.ended_at = now
    db.session.commit()

    my_courses = Course.query.filter_by(teacher_id=current_user.id).all()
    course_ids = [c.id for c in my_courses]
    
    sessions = LiveSession.query.filter(LiveSession.course_id.in_(course_ids)).order_by(LiveSession.scheduled_at.desc()).all() if course_ids else []
    
    upcoming_sessions = [s for s in sessions if s.status == 'scheduled']
    live_sessions_list = [s for s in sessions if s.status == 'live']
    past_sessions = [s for s in sessions if s.status in ('ended', 'cancelled')]
    
    return render_template('teacher/live_sessions.html', 
                           courses=my_courses,
                           upcoming_sessions=upcoming_sessions,
                           live_sessions=live_sessions_list,
                           past_sessions=past_sessions)


@teacher_bp.route('/live-classroom/create', methods=['POST'])
@teacher_required
def create_live_session():
    """Schedule a new live video classroom session"""
    from app.models import LiveSession, Course, Enrollment, Notification
    from uuid import uuid4
    
    course_id = request.form.get('course_id', type=int)
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    scheduled_at_str = request.form.get('scheduled_at')
    duration_minutes = request.form.get('duration_minutes', type=int, default=60)
    custom_url = request.form.get('custom_meeting_url', '').strip()
    
    if not course_id or not title or not scheduled_at_str:
        flash('Please fill in Course, Title, and Scheduled Date/Time.', 'warning')
        return redirect(url_for('teacher.live_classrooms'))
        
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized course access.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))
        
    try:
        scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
    except Exception:
        scheduled_at = datetime.utcnow()
        
    unique_room_name = f"pace_live_c{course_id}_{uuid4().hex[:10]}"
    
    new_session = LiveSession(
        course_id=course_id,
        created_by_id=current_user.id,
        title=title,
        description=description,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        room_name=unique_room_name,
        custom_meeting_url=custom_url if custom_url else None,
        status='scheduled'
    )
    db.session.add(new_session)
    db.session.commit()
    
    # Notify enrolled students via In-App Notification and Email
    from app.utils.email import send_email
    meeting_link = url_for('student.live_classrooms', _external=True)
    
    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    for e in enrollments:
        notif = Notification(
            user_id=e.student_id,
            notification_type='live_session',
            title=f"📅 New Live Classroom Scheduled: {title}",
            message=f"Live Session scheduled for {course.title} on {scheduled_at.strftime('%d %b %Y, %H:%M')}.",
            link_url=url_for('student.live_classrooms'),
            related_course_id=course_id
        )
        db.session.add(notif)
        
        # Send Email Notification
        if e.student and e.student.email:
            try:
                send_email(
                    subject=f"🎥 Live Classroom Scheduled: {title} ({course.title})",
                    recipient=e.student.email,
                    template='live_session_notification',
                    student=e.student,
                    course=course,
                    session=new_session,
                    instructor_name=current_user.full_name,
                    meeting_url=meeting_link
                )
            except Exception as err:
                current_app.logger.warning(f"Failed sending live session email to {e.student.email}: {err}")
                
    db.session.commit()
    
    flash('🎥 Live Classroom scheduled successfully! Enrolled students have been notified via app & email.', 'success')
    return redirect(url_for('teacher.live_classrooms'))


@teacher_bp.route('/live-classroom/<int:session_id>/start', methods=['POST'])
@teacher_required
def start_live_session(session_id):
    """Launch a scheduled live classroom and switch status to 'live'"""
    from app.models import LiveSession
    session_obj = LiveSession.query.get_or_404(session_id)
    if session_obj.course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))
        
    session_obj.status = 'live'
    session_obj.started_at = datetime.utcnow()
    db.session.commit()
    
    flash(f"🔴 Live Classroom '{session_obj.title}' is now LIVE!", 'success')
    return redirect(url_for('teacher.live_room', session_id=session_id))


@teacher_bp.route('/live-classroom/<int:session_id>/end', methods=['POST'])
@teacher_required
def end_live_session(session_id):
    """End a live classroom session"""
    from app.models import LiveSession
    session_obj = LiveSession.query.get_or_404(session_id)
    if session_obj.course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))
        
    session_obj.status = 'ended'
    session_obj.ended_at = datetime.utcnow()
    db.session.commit()
    
    flash(f"Live Session '{session_obj.title}' has ended.", 'info')
    return redirect(url_for('teacher.live_classrooms'))


@teacher_bp.route('/live-classroom/<int:session_id>/room')
@teacher_required
def live_room(session_id):
    """Fullscreen host video room for the teacher"""
    from app.models import LiveSession
    session_obj = LiveSession.query.get_or_404(session_id)
    if session_obj.course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized access to meeting room.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))
        
    return render_template('live_room.html', session_obj=session_obj, is_host=True)


@teacher_bp.route('/live-classroom/<int:session_id>/delete', methods=['POST'])
@teacher_required
def delete_live_session(session_id):
    """Delete or cancel a live session"""
    from app.models import LiveSession
    session_obj = LiveSession.query.get_or_404(session_id)
    if session_obj.course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))
        
    title = session_obj.title
    db.session.delete(session_obj)
    db.session.commit()
    
    flash(f"Live Session '{title}' deleted.", 'info')
    return redirect(url_for('teacher.live_classrooms'))


@teacher_bp.route('/live-classroom/<int:session_id>/attendance/export')
@teacher_required
def export_live_attendance(session_id):
    """Export attendance CSV report for a live classroom session"""
    import csv
    import io
    from flask import Response
    from app.models import LiveSession, LiveAttendance

    session_obj = LiveSession.query.get_or_404(session_id)
    if session_obj.course.teacher_id != current_user.id and current_user.role != 'admin':
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('teacher.live_classrooms'))

    attendances = LiveAttendance.query.filter_by(session_id=session_id).order_by(LiveAttendance.joined_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student Name', 'Email', 'Joined At (UTC)', 'Last Active At (UTC)', 'Active Duration (Mins)'])

    for a in attendances:
        student_name = a.student.full_name if a.student else 'Unknown'
        student_email = a.student.email if a.student else ''
        joined_str = a.joined_at.strftime('%Y-%m-%d %H:%M:%S') if a.joined_at else ''
        last_str = a.last_ping.strftime('%Y-%m-%d %H:%M:%S') if a.last_ping else joined_str
        
        mins = 1
        if a.joined_at and a.last_ping:
            delta = a.last_ping - a.joined_at
            mins = max(1, int(delta.total_seconds() / 60))
            
        writer.writerow([student_name, student_email, joined_str, last_str, mins])

    filename = f"attendance_session_{session_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@teacher_bp.route('/live-classroom/question/<int:question_id>/toggle-answered', methods=['POST'])
@teacher_required
def toggle_live_question(question_id):
    """Mark a pre-meeting question as answered/unanswered"""
    from app.models import LiveQuestion
    q = LiveQuestion.query.get_or_404(question_id)
    if q.session.course.teacher_id != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    q.is_answered = not q.is_answered
    db.session.commit()
    return jsonify({'success': True, 'is_answered': q.is_answered}), 200


# ══════════════════════════════════════════════════════════════
# PACE AI COURSE & QUIZ GENERATOR ENDPOINTS
# ══════════════════════════════════════════════════════════════

@teacher_bp.route('/ai/get-lesson-templates', methods=['GET'])
@teacher_required
@csrf.exempt
def ai_get_lesson_templates():
    """Retrieve teacher's published sections to use as style-cloning templates"""
    from app.models import Course, Section
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    course_ids = [c.id for c in courses]
    
    sections = Section.query.filter(
        Section.course_id.in_(course_ids),
        Section.content.isnot(None)
    ).order_by(Section.created_at.desc()).limit(15).all()
    
    templates = []
    for s in sections:
        if s.content and len(s.content.strip()) > 100:
            templates.append({
                'id': s.id,
                'title': f"{s.course.title} — {s.title}",
                'content': s.content[:1500]  # Reference excerpt
            })
            
    return jsonify({'success': True, 'templates': templates})


@teacher_bp.route('/ai/generate-blueprint', methods=['POST'])
@teacher_required
@csrf.exempt
def ai_generate_blueprint():
    """Generate a multi-module course outline from teacher prompt"""
    from app.services.ai_service import AIService
    data = request.get_json() or {}
    
    title = data.get('title', '').strip()
    topic = data.get('topic', '').strip()
    level = data.get('level', 'Beginner')
    duration_weeks = int(data.get('duration_weeks', 4))
    accreditation = data.get('accreditation', '').strip()
    custom_instructions = data.get('custom_instructions', '').strip()
    reference_template = data.get('reference_template', '').strip()
    model = data.get('model', 'gemini-3.5-flash')
    
    if not title or not topic:
        return jsonify({'success': False, 'message': 'Course Title and Topic are required.'}), 400
        
    try:
        blueprint = AIService.generate_course_blueprint(
            title=title,
            topic=topic,
            level=level,
            duration_weeks=duration_weeks,
            accreditation=accreditation,
            custom_instructions=custom_instructions,
            reference_template=reference_template,
            model=model
        )
        return jsonify({'success': True, 'blueprint': blueprint})
    except Exception as e:
        logger.error(f"AI Blueprint generation error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@teacher_bp.route('/ai/generate-lesson-content', methods=['POST'])
@teacher_required
@csrf.exempt
def ai_generate_lesson_content():
    """Generate Quill-compatible rich HTML for a single lesson"""
    from app.services.ai_service import AIService
    data = request.get_json() or {}
    
    course_title = data.get('course_title', 'Course').strip()
    module_title = data.get('module_title', 'Module').strip()
    lesson_title = data.get('lesson_title', '').strip()
    custom_instructions = data.get('custom_instructions', '').strip()
    reference_template = data.get('reference_template', '').strip()
    model = data.get('model', 'gemini-3.5-flash')
    
    if not lesson_title:
        return jsonify({'success': False, 'message': 'Lesson title is required.'}), 400
        
    try:
        html_content = AIService.generate_lesson_html(
            course_title=course_title,
            module_title=module_title,
            lesson_title=lesson_title,
            custom_instructions=custom_instructions,
            reference_template=reference_template,
            model=model
        )
        return jsonify({'success': True, 'html_content': html_content})
    except Exception as e:
        logger.error(f"AI Lesson HTML generation error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@teacher_bp.route('/ai/generate-quiz', methods=['POST'])
@teacher_required
@csrf.exempt
def ai_generate_quiz():
    """Generate assessment quiz with choices and explanations"""
    from app.services.ai_service import AIService
    data = request.get_json() or {}
    
    lesson_title = data.get('lesson_title', 'Lesson Assessment').strip()
    lesson_content = data.get('lesson_content', '').strip()
    num_questions = int(data.get('num_questions', 5))
    passing_score = float(data.get('passing_score', 70.0))
    model = data.get('model', 'gemini-3.5-flash')
    
    if not lesson_content:
        return jsonify({'success': False, 'message': 'Lesson content is required to generate quiz.'}), 400
        
    try:
        quiz_data = AIService.generate_quiz_for_lesson(
            lesson_title=lesson_title,
            lesson_content=lesson_content,
            num_questions=num_questions,
            passing_score=passing_score,
            model=model
        )
        return jsonify({'success': True, 'quiz': quiz_data})
    except Exception as e:
        logger.error(f"AI Quiz generation error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@teacher_bp.route('/ai/create-course-bundle', methods=['POST'])
@teacher_required
@csrf.exempt
def ai_create_course_bundle():
    """Commit an AI-generated course blueprint into database tables"""
    from app.models import Course, Module, Section, Quiz, QuizQuestion
    import json
    data = request.get_json() or {}
    blueprint = data.get('blueprint')
    
    if not blueprint or not isinstance(blueprint, dict):
        return jsonify({'success': False, 'message': 'Invalid course blueprint data.'}), 400
        
    try:
        # 1. Create Course
        course = Course(
            teacher_id=current_user.id,
            title=blueprint.get('title', 'Untitled AI Course'),
            description=blueprint.get('short_description', 'Course created with Pace AI.'),
            category=blueprint.get('category', 'programming'),
            difficulty_level=blueprint.get('difficulty_level', 'beginner'),
            estimated_duration=int(blueprint.get('estimated_duration', 10)),
            learning_objectives=json.dumps(blueprint.get('learning_objectives', [])),
            prerequisites=json.dumps(blueprint.get('prerequisites', [])),
            tags=blueprint.get('tags', 'AI Generated'),
            status='draft',
            is_draft=True
        )
        db.session.add(course)
        db.session.flush()  # Obtain course.id
        
        # 2. Iterate through Modules & Lessons
        for mod_idx, mod_data in enumerate(blueprint.get('modules', [])):
            module = Module(
                course_id=course.id,
                title=mod_data.get('title', f"Module {mod_idx + 1}"),
                description=mod_data.get('description', ''),
                order=mod_idx
            )
            db.session.add(module)
            db.session.flush()  # Obtain module.id
            
            for les_idx, les_data in enumerate(mod_data.get('lessons', [])):
                section = Section(
                    course_id=course.id,
                    module_id=module.id,
                    title=les_data.get('title', f"Lesson {les_idx + 1}"),
                    content=les_data.get('content_html', f"<h2>{les_data.get('title', 'Lesson')}</h2><p>{les_data.get('summary', '')}</p>"),
                    section_type='text',
                    order=les_idx,
                    duration=les_data.get('estimated_minutes', 15),
                    is_published=False
                )
                db.session.add(section)
                db.session.flush()
                
                # If quiz is attached to lesson
                quiz_data = les_data.get('quiz')
                if quiz_data and isinstance(quiz_data, dict):
                    quiz = Quiz(
                        section_id=section.id,
                        title=quiz_data.get('title', f"{section.title} - Quiz"),
                        passing_score=float(quiz_data.get('passing_score', 70.0)),
                        time_limit=quiz_data.get('time_limit', 10),
                        show_correct_answers=True
                    )
                    db.session.add(quiz)
                    db.session.flush()
                    
                    for q_item in quiz_data.get('questions', []):
                        qq = QuizQuestion(
                            quiz_id=quiz.id,
                            question_text=q_item.get('question_text', ''),
                            option_a=q_item.get('option_a', 'A'),
                            option_b=q_item.get('option_b', 'B'),
                            option_c=q_item.get('option_c', 'C'),
                            option_d=q_item.get('option_d', 'D'),
                            correct_answer=q_item.get('correct_answer', 'option_a')
                        )
                        db.session.add(qq)

        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Course successfully created with all modules and lessons!',
            'course_id': course.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating course bundle: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500