from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import Course, User
from app import db
from app.decorators import admin_required
from app.forms import ProfileForm
from app.utils.email import send_welcome_email
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.context_processor
def inject_pending_count():
    """Inject pending course count into all admin templates"""
    if current_user.is_authenticated and current_user.role == 'admin':
        pending_count = Course.query.filter_by(status='pending').count()
        return dict(pending_count=pending_count)
    return dict(pending_count=0)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    approved_count = Course.query.filter_by(status='approved').count()
    pending_count = Course.query.filter_by(status='pending').count()
    
    return render_template('admin/dashboard.html',
                         user=current_user,
                         approved_count=approved_count,
                         pending_count=pending_count)

@admin_bp.route('/approvals')
@admin_required
def pending_approvals():
    pending_courses = Course.query.filter_by(status='pending').all()
    print("Pending courses:", [(course.id, course.title, course.status) for course in pending_courses])  # Debug log
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
    users = User.query.all()
    return render_template('admin/users.html', users=users)

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
    from app.models import AssignmentSubmission, QuizAttempt, Rating
    
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
        # Delete assignment submissions
        AssignmentSubmission.query.filter_by(student_id=user.id).delete()
        
        # Delete quiz attempts
        QuizAttempt.query.filter_by(student_id=user.id).delete()
        
        # Delete ratings
        Rating.query.filter_by(user_id=user.id).delete()
        
        # Enrollments will be deleted automatically due to cascade='all, delete-orphan'
        
        # If user is a teacher, handle their courses
        if user.role == 'teacher':
            # Delete all courses created by this teacher
            # This will cascade delete sections, quizzes, enrollments, etc.
            for course in user.courses:
                db.session.delete(course)
        
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
        # Verify current password
        if not current_user.verify_password(form.current_password.data):
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