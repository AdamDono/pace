from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory, jsonify, make_response
from flask_login import login_required, current_user
from app.models import Course, User, Enrollment, AssignmentSubmission, QuizAttempt, Rating, Assignment, Section
from app import db
from app.decorators import admin_required
from app.forms import ProfileForm
from app.utils.email import send_welcome_email
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import os
import csv
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.context_processor
def inject_pending_count():
    """Inject pending course count into all admin templates"""
    try:
        if current_user.is_authenticated and current_user.role == 'admin':
            pending_count = Course.query.filter_by(status='pending').count()
            return dict(pending_count=pending_count)
    except Exception:
        pass
    return dict(pending_count=0)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Course stats
    approved_count = Course.query.filter_by(status='approved').count()
    pending_count = Course.query.filter_by(status='pending').count()
    rejected_count = Course.query.filter_by(status='rejected').count()
    total_courses = Course.query.count()
    
    # User stats
    total_users = User.query.count()
    student_count = User.query.filter_by(role='student').count()
    teacher_count = User.query.filter_by(role='teacher').count()
    admin_count = User.query.filter_by(role='admin').count()
    
    # Active users (logged in last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = User.query.filter(User.last_login >= thirty_days_ago).count() if thirty_days_ago else 0
    
    # Enrollment stats
    total_enrollments = Enrollment.query.count()
    
    # Assignment stats
    total_assignments = AssignmentSubmission.query.count()
    graded_assignments = AssignmentSubmission.query.filter_by(reviewed=True).count()
    pending_grading = total_assignments - graded_assignments
    
    # Average grade
    avg_grade_result = db.session.query(func.avg(AssignmentSubmission.grade)).filter(
        AssignmentSubmission.grade.isnot(None)
    ).scalar()
    avg_grade = round(avg_grade_result, 1) if avg_grade_result else 0
    
    # Recent activity (last 10 logins)
    recent_logins = User.query.filter(User.last_login.isnot(None)).order_by(
        desc(User.last_login)
    ).limit(10).all()
    
    # Most popular courses (by enrollment)
    popular_courses = db.session.query(
        Course, func.count(Enrollment.id).label('enrollment_count')
    ).join(Enrollment).group_by(Course.id).order_by(
        desc('enrollment_count')
    ).limit(5).all()
    
    # Growth data (users created per month - last 6 months)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    monthly_signups = []
    try:
        # Check database engine type
        engine_name = db.engine.name
        if engine_name == 'postgresql':
            month_expr = func.to_char(User.created_at, 'YYYY-MM')
        else:
            month_expr = func.strftime('%Y-%m', User.created_at)
            
        monthly_signups = db.session.query(
            month_expr.label('month'),
            func.count(User.id).label('count')
        ).filter(User.created_at >= six_months_ago).group_by(month_expr).all()
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning(f"Error querying monthly signups: {e}")
        monthly_signups = []
    
    return render_template('admin/dashboard.html',
                         user=current_user,
                         approved_count=approved_count,
                         pending_count=pending_count,
                         rejected_count=rejected_count,
                         total_courses=total_courses,
                         total_users=total_users,
                         student_count=student_count,
                         teacher_count=teacher_count,
                         admin_count=admin_count,
                         active_users=active_users,
                         total_enrollments=total_enrollments,
                         total_assignments=total_assignments,
                         graded_assignments=graded_assignments,
                         pending_grading=pending_grading,
                         avg_grade=avg_grade,
                         recent_logins=recent_logins,
                         popular_courses=popular_courses,
                         monthly_signups=monthly_signups)

@admin_bp.route('/approvals')
@admin_required
def pending_approvals():
    pending_courses = Course.query.filter_by(status='pending').all()
    return render_template('admin/approvals.html', courses=pending_courses)

@admin_bp.route('/approve-course/<int:course_id>')
@admin_required
def approve_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.status = 'approved'
    db.session.commit()
    flash('Course approved!', 'success')
    return redirect(url_for('admin.pending_approvals'))

@admin_bp.route('/reject-course/<int:course_id>', methods=['POST'])
@admin_required
def reject_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.status = 'rejected'
    course.admin_feedback = request.form.get('feedback', '')
    db.session.commit()
    flash('Course rejected', 'info')
    return redirect(url_for('admin.pending_approvals'))

@admin_bp.route('/courses')
@admin_required
def manage_courses():
    approved_courses = Course.query.filter_by(status='approved').all()
    return render_template('admin/courses.html', courses=approved_courses)

@admin_bp.route('/course/<int:course_id>/delete', methods=['POST'])
@admin_required
def delete_course(course_id):
    """Hard delete a course (draft or non-draft). Admin-only.

    Accepts optional 'return_url' in form data to redirect back to the originating page.
    This will cascade-delete related entities according to SQLAlchemy relationships.
    """
    course = Course.query.get_or_404(course_id)

    try:
        title = course.title
        db.session.delete(course)
        db.session.commit()
        flash(f"Course '{title}' has been deleted.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete course: {str(e)}', 'danger')

    return_url = request.form.get('return_url')
    if return_url:
        return redirect(return_url)
    # Default fallback destinations based on former status
    if getattr(course, 'is_draft', False) or getattr(course, 'status', '') == 'draft':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.manage_courses'))

@admin_bp.route('/course/<int:course_id>')
@admin_required
def course_detail(course_id):
    course = Course.query.options(
        db.joinedload(Course.sections)
    ).get_or_404(course_id)
    
    return render_template('admin/course_detail.html', course=course)

@admin_bp.route('/pdf/<filename>')
@admin_required
def serve_pdf(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@admin_bp.route('/users')
@admin_required
def manage_users():
    # Get search and filter parameters
    search_query = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')
    sort_by = request.args.get('sort', 'created_at')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = User.query
    
    # Apply search
    if search_query:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%'),
                User.first_name.ilike(f'%{search_query}%'),
                User.last_name.ilike(f'%{search_query}%')
            )
        )
    
    # Apply role filter
    if role_filter:
        query = query.filter_by(role=role_filter)
    
    # Apply sorting
    if sort_by == 'last_login':
        query = query.order_by(desc(User.last_login))
    elif sort_by == 'login_count':
        query = query.order_by(desc(User.login_count))
    elif sort_by == 'username':
        query = query.order_by(User.username)
    elif sort_by == 'email':
        query = query.order_by(User.email)
    else:  # created_at
        query = query.order_by(desc(User.created_at))
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items
    
    # Get activity stats for each user
    for user in users:
        user.enrollment_count = Enrollment.query.filter_by(student_id=user.id).count() if user.role == 'student' else 0
        user.course_count = Course.query.filter_by(teacher_id=user.id).count() if user.role == 'teacher' else 0
        user.submission_count = AssignmentSubmission.query.filter_by(student_id=user.id).count() if user.role == 'student' else 0
    
    return render_template('admin/users.html', 
                         users=users,
                         pagination=pagination,
                         search_query=search_query,
                         role_filter=role_filter,
                         sort_by=sort_by)

@admin_bp.route('/create-user', methods=['GET', 'POST'])
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists', 'danger')
            return redirect(url_for('admin.create_user'))
        
        # Create new user
        user = User(
            email=email,
            username=username,
            password=password,
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email with credentials
        try:
            send_welcome_email(user, password)
            flash(f'User {email} created successfully! Welcome email sent.', 'success')
        except Exception as e:
            flash(f'User {email} created but email failed to send: {str(e)}', 'warning')
        
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/create_user.html')

@admin_bp.route('/create-teacher', methods=['GET', 'POST'])
@admin_required
def create_teacher():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        bio = request.form.get('bio')
        specialization = request.form.get('specialization')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User with this email already exists', 'danger')
            return redirect(url_for('admin.create_teacher'))
        
        # Create new teacher
        teacher = User(
            email=email,
            username=username,
            password=password,
            role='teacher',
            first_name=first_name,
            last_name=last_name,
            bio=bio,
            specialization=specialization
        )
        db.session.add(teacher)
        db.session.commit()
        
        # Send welcome email with credentials
        try:
            send_welcome_email(teacher, password)
            flash(f'Teacher {first_name} {last_name} created successfully! Welcome email sent.', 'success')
        except Exception as e:
            flash(f'Teacher {first_name} {last_name} created but email failed to send: {str(e)}', 'warning')
        
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/create_teacher.html')

@admin_bp.route('/teachers')
@admin_required
def manage_teachers():
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers.html', teachers=teachers)

@admin_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    # Prevent deleting other admins
    if user.role == 'admin':
        flash('Cannot delete administrator accounts!', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    try:
        email = user.email
        
        # Delete all related records that don't have cascade delete
        from app.models import (
            AssignmentSubmission, QuizAttempt, Rating, 
            VideoWatchProgress, VideoQuestionResponse, Announcement
        )
        
        # Delete assignment submissions
        AssignmentSubmission.query.filter_by(student_id=user.id).delete()
        
        # Delete quiz attempts and their answers via ORM delete (triggers cascade to QuizAnswer)
        attempts = QuizAttempt.query.filter_by(student_id=user.id).all()
        for attempt in attempts:
            db.session.delete(attempt)
        
        # Delete ratings
        Rating.query.filter_by(user_id=user.id).delete()
        
        # Delete video progress and interactive question responses
        VideoWatchProgress.query.filter_by(student_id=user.id).delete()
        VideoQuestionResponse.query.filter_by(student_id=user.id).delete()
        
        # If user is a teacher, delete their announcements
        if user.role == 'teacher':
            Announcement.query.filter_by(teacher_id=user.id).delete()
            
            # Delete all courses created by this teacher
            # This will cascade delete sections, quizzes, enrollments, etc.
            for course in user.taught_courses:
                db.session.delete(course)
                
        # Nullify suspended_by for any users suspended by this user
        User.query.filter_by(suspended_by=user.id).update({User.suspended_by: None})
        
        # Enrollments and notifications will be deleted automatically due to cascade='all, delete-orphan'
        
        # Now delete the user
        db.session.delete(user)
        db.session.commit()
        
        flash(f'User {email} and all associated data have been deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Only require current password when changing password
        if form.new_password.data:
            if not current_user.verify_password(form.current_password.data or ''):
                flash('Current password is incorrect', 'danger')
                return render_template('admin/profile.html', form=form)
        
        # Check if email is already taken by another user
        if form.email.data != current_user.email:
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('Email already in use by another account', 'danger')
                return render_template('admin/profile.html', form=form)
        
        # Check if username is already taken by another user
        if form.username.data != current_user.username:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user:
                flash('Username already in use', 'danger')
                return render_template('admin/profile.html', form=form)
        
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
                new_name = f"avatar_admin_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
                file.save(save_path)
                current_user.profile_image = new_name

        # Update password if provided
        if form.new_password.data:
            current_user.password = form.new_password.data
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('admin.profile'))
    
    # Pre-populate form with current user data
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
        form.contact.data = current_user.contact
    
    return render_template('admin/profile.html', form=form)

# ===== EXPORTS & REPORTS =====

@admin_bp.route('/export/users')
@admin_required
def export_users():
    """Export all users to CSV"""
    users = User.query.all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Username', 'Email', 'Role', 'First Name', 'Last Name', 
                     'Created At', 'Last Login', 'Login Count', 'Enrollments', 'Submissions'])
    
    # Write data
    for user in users:
        enrollment_count = Enrollment.query.filter_by(student_id=user.id).count()
        submission_count = AssignmentSubmission.query.filter_by(student_id=user.id).count()
        
        writer.writerow([
            user.id,
            user.username,
            user.email,
            user.role,
            user.first_name or '',
            user.last_name or '',
            user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else '',
            user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never',
            user.login_count or 0,
            enrollment_count,
            submission_count
        ])
    
    # Prepare response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=users_export_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@admin_bp.route('/export/courses')
@admin_required
def export_courses():
    """Export all courses to CSV"""
    courses = Course.query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Title', 'Teacher', 'Status', 'Enrollments', 'Avg Rating', 
                     'Total Assignments', 'Created At'])
    
    # Write data
    for course in courses:
        enrollment_count = Enrollment.query.filter_by(course_id=course.id).count()
        avg_rating = db.session.query(func.avg(Rating.rating)).filter_by(course_id=course.id).scalar() or 0
        
        # Count assignments in course
        assignment_count = db.session.query(func.count(Assignment.id)).join(
            Section
        ).filter(Section.course_id == course.id).scalar() or 0
        
        writer.writerow([
            course.id,
            course.title,
            course.teacher.username if course.teacher else '',
            course.status,
            enrollment_count,
            round(avg_rating, 2),
            assignment_count,
            course.created_at.strftime('%Y-%m-%d') if hasattr(course, 'created_at') else ''
        ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=courses_export_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@admin_bp.route('/export/grades')
@admin_required
def export_grades():
    """Export all grades to CSV"""
    submissions = AssignmentSubmission.query.filter(
        AssignmentSubmission.grade.isnot(None)
    ).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Student ID', 'Student Name', 'Student Email', 'Course', 'Assignment', 
                     'Grade', 'Submitted At', 'Reviewed'])
    
    # Write data
    for submission in submissions:
        from app.models import Assignment, Section
        assignment = Assignment.query.get(submission.assignment_id)
        if assignment:
            section = Section.query.get(assignment.section_id)
            course = Course.query.get(section.course_id) if section else None
            student = User.query.get(submission.student_id)
            
            writer.writerow([
                submission.student_id,
                student.username if student else '',
                student.email if student else '',
                course.title if course else '',
                assignment.title,
                submission.grade or '',
                submission.submitted_at.strftime('%Y-%m-%d %H:%M') if submission.submitted_at else '',
                'Yes' if submission.reviewed else 'No'
            ])
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=grades_export_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

# ===== COURSE STATISTICS =====

@admin_bp.route('/course-statistics')
@admin_required
def course_statistics():
    """Detailed statistics for all courses"""
    courses = Course.query.filter_by(status='approved').all()
    
    course_stats = []
    for course in courses:
        # Get enrollments
        enrollment_count = Enrollment.query.filter_by(course_id=course.id).count()
        
        # Get completion rate
        completed_enrollments = Enrollment.query.filter_by(
            course_id=course.id,
            completed=True
        ).count()
        completion_rate = (completed_enrollments / enrollment_count * 100) if enrollment_count > 0 else 0
        
        # Get average rating
        avg_rating = db.session.query(func.avg(Rating.rating)).filter_by(course_id=course.id).scalar() or 0
        rating_count = Rating.query.filter_by(course_id=course.id).count()
        
        # Get assignment stats
        from app.models import Assignment, Section
        assignments = db.session.query(Assignment).join(Section).filter(
            Section.course_id == course.id
        ).all()
        
        total_assignments = len(assignments)
        total_submissions = sum(
            AssignmentSubmission.query.filter_by(assignment_id=a.id).count() 
            for a in assignments
        )
        
        # Average grade for course
        avg_grade = 0
        if assignments:
            grades = []
            for assignment in assignments:
                assignment_grades = db.session.query(AssignmentSubmission.grade).filter_by(
                    assignment_id=assignment.id
                ).filter(AssignmentSubmission.grade.isnot(None)).all()
                grades.extend([g[0] for g in assignment_grades])
            
            avg_grade = sum(grades) / len(grades) if grades else 0
        
        course_stats.append({
            'course': course,
            'enrollment_count': enrollment_count,
            'completion_rate': round(completion_rate, 1),
            'avg_rating': round(avg_rating, 2),
            'rating_count': rating_count,
            'total_assignments': total_assignments,
            'total_submissions': total_submissions,
            'avg_grade': round(avg_grade, 1) if avg_grade else 0
        })
    
    # Sort by enrollment count
    course_stats.sort(key=lambda x: x['enrollment_count'], reverse=True)
    
    return render_template('admin/course_statistics.html', course_stats=course_stats)

# ============================================
# USER SUSPENSION/BAN MANAGEMENT
# ============================================

@admin_bp.route('/user/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Suspend a user account"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from suspending themselves
    if user.id == current_user.id:
        flash('You cannot suspend your own account', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    # Prevent suspending other admins
    if user.role == 'admin':
        flash('You cannot suspend other administrators', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    # Get suspension details from form
    reason = request.form.get('reason', 'No reason provided')
    duration_days = request.form.get('duration_days', type=int)
    
    user.is_suspended = True
    user.suspension_reason = reason
    user.suspended_at = datetime.utcnow()
    user.suspended_by = current_user.id
    
    if duration_days and duration_days > 0:
        user.suspended_until = datetime.utcnow() + timedelta(days=duration_days)
    else:
        user.suspended_until = None  # Indefinite suspension
    
    db.session.commit()
    
    # Send email notification
    try:
        from app.utils.email import send_suspension_email
        send_suspension_email(user, reason, user.suspended_until)
    except Exception as e:
        current_app.logger.error(f"Failed to send suspension email: {e}")
    
    if duration_days:
        flash(f'User {user.username} has been suspended for {duration_days} days', 'success')
    else:
        flash(f'User {user.username} has been suspended indefinitely', 'success')
    
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/user/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    """Permanently ban a user account"""
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from banning themselves
    if user.id == current_user.id:
        flash('You cannot ban your own account', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    # Prevent banning other admins
    if user.role == 'admin':
        flash('You cannot ban other administrators', 'danger')
        return redirect(url_for('admin.manage_users'))
    
    # Get ban reason from form
    reason = request.form.get('reason', 'Violation of terms and conditions')
    
    user.is_banned = True
    user.is_suspended = False  # Clear suspension if any
    user.suspension_reason = reason
    user.suspended_at = datetime.utcnow()
    user.suspended_by = current_user.id
    user.suspended_until = None
    
    db.session.commit()
    
    # Send email notification
    try:
        from app.utils.email import send_ban_email
        send_ban_email(user, reason)
    except Exception as e:
        current_app.logger.error(f"Failed to send ban email: {e}")
    
    flash(f'User {user.username} has been permanently banned', 'success')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/user/<int:user_id>/unsuspend', methods=['POST'])
@admin_required
def unsuspend_user(user_id):
    """Remove suspension from a user account"""
    user = User.query.get_or_404(user_id)
    
    if not user.is_suspended and not user.is_banned:
        flash('User is not suspended or banned', 'info')
        return redirect(url_for('admin.manage_users'))
    
    # Cannot unban through unsuspend - must use separate unban route
    if user.is_banned:
        flash('This user is permanently banned. Use the "Unban" action to restore access', 'warning')
        return redirect(url_for('admin.manage_users'))
    
    user.is_suspended = False
    user.suspended_until = None
    # Keep suspension_reason and suspended_at for history
    
    db.session.commit()
    
    # Send email notification
    try:
        from app.utils.email import send_unsuspension_email
        send_unsuspension_email(user)
    except Exception as e:
        current_app.logger.error(f"Failed to send unsuspension email: {e}")
    
    flash(f'User {user.username} has been unsuspended', 'success')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/user/<int:user_id>/unban', methods=['POST'])
@admin_required
def unban_user(user_id):
    """Remove ban from a user account"""
    user = User.query.get_or_404(user_id)
    
    if not user.is_banned:
        flash('User is not banned', 'info')
        return redirect(url_for('admin.manage_users'))
    
    user.is_banned = False
    user.is_suspended = False
    user.suspended_until = None
    # Keep suspension_reason and suspended_at for history
    
    db.session.commit()
    
    # Send email notification
    try:
        from app.utils.email import send_unban_email
        send_unban_email(user)
    except Exception as e:
        current_app.logger.error(f"Failed to send unban email: {e}")
    
    flash(f'User {user.username} has been unbanned', 'success')
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/leads')
@admin_required
def leads():
    from app.models import Lead
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template('admin/leads.html', leads=leads)

@admin_bp.route('/leads/<int:lead_id>/status/<status>')
@admin_required
def update_lead_status(lead_id, status):
    if status not in ['pending', 'contacted', 'enrolled', 'rejected']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin.leads'))
        
    from app.models import Lead
    lead = Lead.query.get_or_404(lead_id)
    lead.status = status
    db.session.commit()
    flash(f'Lead status updated to {status} successfully.', 'success')
    return redirect(url_for('admin.leads'))

@admin_bp.route('/leads/<int:lead_id>/delete', methods=['POST'])
@admin_required
def delete_lead(lead_id):
    from app.models import Lead
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead deleted successfully.', 'success')
    return redirect(url_for('admin.leads'))

@admin_bp.route('/leads/<int:lead_id>/approve-enroll', methods=['POST'])
@admin_required
def approve_enroll_lead(lead_id):
    from app.models import Lead, User, Enrollment, EnrollmentSection, Course
    import string
    import random
    
    lead = Lead.query.get_or_404(lead_id)
    
    # Check if a user with this email already exists
    user = User.query.filter_by(email=lead.email).first()
    password_generated = None
    
    if not user:
        # Create username: strip email handle or slugify full name
        base_username = lead.full_name.lower().replace(" ", "")
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
            
        # Generate secure random password
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password_generated = ''.join(random.choice(chars) for i in range(12))
        
        # Name split
        parts = lead.full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        
        user = User(
            email=lead.email,
            username=username,
            role='student',
            first_name=first_name,
            last_name=last_name,
            contact=lead.phone
        )
        user.password = password_generated
        db.session.add(user)
        db.session.commit()
    
    # Enroll the student in the requested course (if lead has course_id)
    if lead.course_id:
        course = Course.query.get(lead.course_id)
        if course:
            # Check if already enrolled
            existing_enrollment = Enrollment.query.filter_by(student_id=user.id, course_id=course.id).first()
            if not existing_enrollment:
                enrollment = Enrollment(
                    student_id=user.id,
                    course_id=course.id
                )
                db.session.add(enrollment)
                db.session.commit()
                
                # Auto-populate progress tracking
                for module in course.modules:
                    for section in module.sections:
                        from app.models import EnrollmentSection
                        prog = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section.id).first()
                        if not prog:
                            prog = EnrollmentSection(
                                enrollment_id=enrollment.id,
                                section_id=section.id,
                                completed=False
                            )
                            db.session.add(prog)
                db.session.commit()
                
    # Update lead status
    lead.status = 'enrolled'
    db.session.commit()
    
    # Send email notification if password was generated
    if password_generated:
        try:
            from app.utils.email import send_welcome_email
            send_welcome_email(user, password_generated)
            flash(f'Account created and welcome email sent to {user.email}.', 'success')
        except Exception as e:
            flash(f'Student enrolled, but welcome email sending failed: {str(e)}', 'warning')
    else:
        # User already existed, send standard enrollment notification
        try:
            from app.utils.email import send_enrollment_email
            send_enrollment_email(user, course)
            flash(f'Existing student {user.email} enrolled in course.', 'success')
        except Exception as e:
            flash(f'Student enrolled, but enrollment notification failed: {str(e)}', 'warning')
            
    return redirect(url_for('admin.leads'))

# ── User Detail & Per-Course Enrollment Management ──────────────────────────

@admin_bp.route('/users/<int:user_id>')
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    enrollments = (
        Enrollment.query
        .filter_by(student_id=user_id)
        .join(Enrollment.course)
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    ) if user.role == 'student' else []

    courses_taught = (
        Course.query.filter_by(teacher_id=user_id)
        .order_by(Course.created_at.desc()).all()
    ) if user.role == 'teacher' else []

    return render_template(
        'admin/user_detail.html',
        user=user,
        enrollments=enrollments,
        courses_taught=courses_taught,
    )


@admin_bp.route('/users/<int:user_id>/enrollment/<int:enrollment_id>/block', methods=['POST'])
@admin_required
def block_enrollment(user_id, enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != user_id:
        flash('Invalid request.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    reason = request.form.get('reason', '').strip()
    enrollment.is_blocked = True
    enrollment.block_reason = reason or 'Blocked by admin'
    db.session.commit()

    # Email notification
    try:
        from app.utils.email import send_email
        student = enrollment.student
        user_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or student.username or student.email
        send_email(
            subject=f'Course Access Restricted – {enrollment.course.title}',
            recipient=student.email,
            template='course_blocked',
            user_name=user_name,
            course_title=enrollment.course.title,
            reason=enrollment.block_reason,
            support_email='support@pacetech.co.za',
        )
    except Exception:
        pass  # Don't let an email failure break the action

    flash('Student blocked from that course. They have been notified by email.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/enrollment/<int:enrollment_id>/unblock', methods=['POST'])
@admin_required
def unblock_enrollment(user_id, enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != user_id:
        flash('Invalid request.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    enrollment.is_blocked = False
    enrollment.block_reason = None
    db.session.commit()

    # Email notification
    try:
        from app.utils.email import send_email
        from flask import request as req
        student = enrollment.student
        user_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or student.username or student.email
        login_url = req.host_url.rstrip('/') + '/login'
        send_email(
            subject=f'Course Access Restored – {enrollment.course.title}',
            recipient=student.email,
            template='course_unblocked',
            user_name=user_name,
            course_title=enrollment.course.title,
            login_url=login_url,
            support_email='support@pacetech.co.za',
        )
    except Exception:
        pass  # Don't let an email failure break the action

    flash('Student access restored. They have been notified by email.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/enrollment/<int:enrollment_id>/remove', methods=['POST'])
@admin_required
def remove_enrollment(user_id, enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.student_id != user_id:
        flash('Invalid request.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    db.session.delete(enrollment)
    db.session.commit()
    flash(f'Student fully removed from course.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))
