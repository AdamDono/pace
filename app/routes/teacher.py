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
        try:
            course = Course(
                title=form.title.data,
                description=form.description.data,
                youtube_url=form.youtube_url.data,
                teacher_id=current_user.id,
                status='pending'
            )
            db.session.add(course)
            db.session.commit()  # This line often fails
            flash('Course submitted!', 'success')
            return redirect(url_for('teacher.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')  # This will show the actual error
            # Remove this in production - just for debugging
            return f"<pre>Error: {str(e)}\n\n{repr(form.data)}</pre>", 500
    
    return render_template('teacher/create_course.html', form=form)