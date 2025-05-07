from flask import Blueprint, send_from_directory, current_app, abort
from flask_login import login_required, current_user
from app.models import Course, Section, Enrollment
from app import db

course_bp = Blueprint('course', __name__)

@course_bp.route('/section/<int:section_id>/content')
@login_required
def get_section_content(section_id):
    section = Section.query.get_or_404(section_id)
    
    # Verify enrollment or teacher status
    if not (current_user.id == section.course.teacher_id or 
            Enrollment.query.filter_by(
                student_id=current_user.id,
                course_id=section.course.id
            ).first()):
        abort(403)

    if section.section_type == 'pdf':
        if not section.content:  # Assuming content stores filename
            abort(404)
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            section.content,
            as_attachment=False
        )
    
    return {'content': section.content}  # For text/video URLs

@course_bp.route('/course/<int:course_id>/sections')
@login_required
def get_course_sections(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Verify access rights
    if current_user.role == 'student':
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.id,
            course_id=course_id
        ).first()
        if not enrollment:
            abort(403)
    
    sections = [{
        'id': s.id,
        'title': s.title,
        'type': s.section_type,
        'order': s.order,
        'is_completed': s.is_completed_by(current_user.id) if current_user.role == 'student' else None
    } for s in course.sections]
    
    return {'sections': sorted(sections, key=lambda x: x['order'])}