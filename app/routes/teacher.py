from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.forms import CourseForm
from app.models import Course
from app import db
import os
from werkzeug.utils import secure_filename

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('auth.login'))
    return render_template('teacher/dashboard.html', user=current_user)


@teacher_bp.route('/create-course', methods=['GET', 'POST'])
@login_required
def create_course():
    if current_user.role != 'teacher':
        return redirect(url_for('auth.login'))
    
    form = CourseForm()
    if form.validate_on_submit():
        course = Course(
            title=form.title.data,
            description=form.description.data,
            youtube_url=form.youtube_url.data,
            teacher_id=current_user.id,
            status='pending'  # Submitted for approval
        )
        
        db.session.add(course)
        db.session.commit()
        
        flash('Course submitted for approval!', 'success')
        return redirect(url_for('teacher.dashboard'))
    
    return render_template('teacher/create_course.html', form=form)