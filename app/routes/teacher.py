from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Course, db, Section
from app.forms import CourseForm
from app.decorators import teacher_required
import os
import uuid
from datetime import datetime

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@teacher_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('teacher/dashboard.html')

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
                         current_course=None)

@teacher_bp.route('/course/<int:course_id>/add-section', methods=['GET', 'POST'])
@teacher_required
def create_section(course_id):
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
@teacher_required
def manage_sections(course_id):
    course = db.session.get(Course, course_id) or abort(404)
    if course.teacher_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        try:
            last_order = db.session.query(db.func.max(Section.order))\
                         .filter_by(course_id=course.id).scalar() or 0
            
            section = Section(
                title=request.form['title'],
                content=request.form['content'],
                course_id=course.id,
                order=last_order + 1,
                section_type=request.form['section_type'],
                duration=int(request.form.get('duration', 0)),
                created_at=datetime.utcnow()
            )
            
            db.session.add(section)
            db.session.commit()
            flash('Section added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
        
        return redirect(url_for('teacher.manage_sections', course_id=course.id))

    sections = Section.query\
               .filter_by(course_id=course.id)\
               .order_by(Section.order)\
               .all()
    
    return render_template('teacher/section_editor.html',
                         course=course,
                         sections=sections)

@teacher_bp.route('/course/<int:course_id>/reorder-sections', methods=['POST'])
@teacher_required
def reorder_sections(course_id):
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != current_user.id:
        abort(403)

    try:
        order_data = request.get_json()
        for idx, section_id in enumerate(order_data):
            section = Section.query.get(section_id)
            section.order = idx + 1
        db.session.commit()
        return jsonify({"message": "Sections reordered successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@teacher_bp.route('/section/<int:section_id>/delete', methods=['POST'])
@teacher_required
def delete_section(section_id):
    section = db.session.get(Section, section_id) or abort(404)
    course_id = section.course_id
    
    if section.course.teacher_id != current_user.id:
        abort(403)

    try:
        db.session.delete(section)
        db.session.commit()
        flash('Section deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('teacher.manage_sections', course_id=course_id))
