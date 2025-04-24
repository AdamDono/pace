from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import Course, User
from app import db
from app.decorators import admin_required
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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
    course = Course.query.get_or_404(course_id)
    return render_template('admin/course_detail.html', course=course)

@admin_bp.route('/pdf/<filename>')
@admin_required
def serve_pdf(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)