from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Course, db
from app.forms import CourseForm
from app.decorators import teacher_required
import os
import uuid

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@teacher_bp.route('/dashboard')
@teacher_required
def dashboard():
    return render_template('teacher/dashboard.html', user=current_user)

@teacher_bp.route('/create-course', methods=['GET', 'POST'])
@teacher_required
def create_course():
    form = CourseForm()
    if form.validate_on_submit():
        try:
            pdf_filename = None
            if form.pdf_upload.data:
                pdf = form.pdf_upload.data
                if not allowed_file(pdf.filename):
                    flash('Only PDF files are allowed', 'danger')
                    return redirect(url_for('teacher.create_course'))
                
                pdf_filename = f"course_{uuid.uuid4().hex}.pdf"
                save_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    pdf_filename
                )
                pdf.save(save_path)

            youtube_url = None
            if form.youtube_url.data:
                if 'youtube.com' not in form.youtube_url.data and 'youtu.be' not in form.youtube_url.data:
                    flash('Only YouTube URLs are allowed', 'danger')
                    return redirect(url_for('teacher.create_course'))
                youtube_url = form.youtube_url.data

            course = Course(
                title=form.title.data,
                description=form.description.data,
                youtube_url=youtube_url,
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
            if pdf_filename and os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)):
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename))
            flash(f'Error: {str(e)}', 'danger')

    return render_template('teacher/create_course.html', form=form)

@teacher_bp.route('/edit-course/<int:course_id>', methods=['GET', 'POST'])
@teacher_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id or course.status == 'approved':
        abort(403)
    
    form = CourseForm(obj=course)
    
    if form.validate_on_submit():
        try:
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
    courses = Course.query.filter_by(teacher_id=current_user.id)\
               .order_by(Course.created_at.desc())\
               .all()
    return render_template('teacher/my_courses.html', 
                         courses=courses,
                         current_course=None)  # Add this line

@teacher_bp.route('/course/<int:course_id>/add-section', methods=['GET', 'POST'])
@teacher_required
def create_section(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        section = Section(
            title=request.form['title'],
            content=request.form['content'],
            course_id=course.id,
            order=len(course.sections) + 1  # Auto-increment order
        )
        db.session.add(section)
        db.session.commit()
        flash('Section added!', 'success')
        return redirect(url_for('teacher.create_section', course_id=course.id))

    return render_template('teacher/section_editor.html', course=course)

@teacher_bp.route('/course/<int:course_id>/sections', methods=['GET', 'POST'])
@teacher_required
def manage_sections(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        section = Section(
            title=request.form['title'],
            content=request.form['content'],
            course_id=course.id,
            order=len(course.sections) + 1
        )
        db.session.add(section)
        db.session.commit()
        flash('Section added successfully!', 'success')
        return redirect(url_for('teacher.manage_sections', course_id=course.id))

    return render_template('teacher/section_editor.html', course=course)