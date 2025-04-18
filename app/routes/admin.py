from flask import Blueprint, render_template, redirect, url_for,request,flash
from flask_login import login_required, current_user
from app.models import Course, User
from app import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Add to existing admin routes
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    
    approved_count = Course.query.filter_by(status='approved').count()
    pending_count = Course.query.filter_by(status='pending').count()
    
    return render_template('admin/dashboard.html',
                         user=current_user,
                         approved_count=approved_count,
                         pending_count=pending_count)

@admin_bp.route('/approvals')
@login_required
def pending_approvals():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    
    pending_courses = Course.query.filter_by(status='pending').all()
    return render_template('admin/approvals.html', courses=pending_courses)


@admin_bp.route('/approve-course/<int:course_id>')
@login_required
def approve_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.status = 'approved'
    db.session.commit()
    flash('Course approved!', 'success')
    return redirect(url_for('admin.pending_approvals'))

@admin_bp.route('/reject-course/<int:course_id>', methods=['POST'])
@login_required
def reject_course(course_id):
    course = Course.query.get_or_404(course_id)
    course.status = 'rejected'
    course.admin_feedback = request.form.get('feedback', '')
    db.session.commit()
    flash('Course rejected', 'info')
    return redirect(url_for('admin.pending_approvals'))
@admin_bp.route('/courses')
@login_required
def manage_courses():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    
    approved_courses = Course.query.filter_by(status='approved').all()
    return render_template('admin/courses.html', courses=approved_courses)

@admin_bp.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    return render_template('admin/course_detail.html', course=course)