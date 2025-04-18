from flask import Blueprint, render_template, redirect, url_for,request,flask
from flask_login import login_required, current_user
from app.models import Course, User
from app import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    return render_template('admin/dashboard.html', user=current_user)


@admin_bp.route('/approvals')
@login_required
def pending_approvals():
    if current_user.role != 'admin':
        return redirect(url_for('auth.login'))
    
    pending_courses = Course.query.filter_by(status='pending').all()
    return render_template('admin/approvals.html', courses=pending_courses)
