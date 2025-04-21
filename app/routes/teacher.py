from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.forms import CourseForm
from app.models import Course
from app import db
from werkzeug.utils import secure_filename
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app


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
    form = CourseForm()
    if form.validate_on_submit():
        try:
            # Handle PDF upload
            pdf_filename = None
            if form.pdf_upload.data:
                pdf = form.pdf_upload.data
                # Generate unique filename
                ext = pdf.filename.split('.')[-1]
                pdf_filename = f"{uuid.uuid4()}.{ext}"
                secure_name = secure_filename(pdf_filename)
                save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'], 
                    secure_name
                )
                pdf.save(save_path)
                pdf_filename = secure_name  # Store the secure filename

            # Create course
            course = Course(
                title=form.title.data,
                description=form.description.data,
                youtube_url=form.youtube_url.data,
                teacher_id=current_user.id,
                status='pending',
                pdf_filename=pdf_filename
            )
            
            db.session.add(course)
            db.session.commit()
            flash('Course submitted for approval!', 'success')
            return redirect(url_for('teacher.my_courses'))
            
        except Exception as e:
            db.session.rollback()
            # Clean up failed upload
            if pdf_filename and os.path.exists(
                os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
            ):
                os.remove(os.path.join(
                    current_app.config['UPLOAD_FOLDER'], 
                    pdf_filename
                ))
            flash(f'Error: {str(e)}', 'danger')
            current_app.logger.error(f"Course creation failed: {str(e)}")

    return render_template('teacher/create_course.html', form=form)

@teacher_bp.route('/edit-course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'teacher':
        abort(403)
    
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)
    
    form = CourseForm(obj=course)
    
    if form.validate_on_submit():
        form.populate_obj(course)
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('teacher.my_courses'))
    
    return render_template('teacher/edit_course.html', form=form, course=course)


@teacher_bp.route('/my-courses')
@login_required
def my_courses():
    if current_user.role != 'teacher':
        abort(403)
    
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/my_courses.html', 
                         courses=courses)
    
    
    