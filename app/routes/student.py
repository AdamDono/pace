from flask import Blueprint, render_template, redirect, url_for, jsonify, send_from_directory, request
from flask_login import login_required, current_user
from app.models import Course, Section, Enrollment, EnrollmentSection
from app import db
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    return render_template('student/dashboard.html', user=current_user)

@student_bp.route('/course/<int:course_id>')
@login_required
def course_detail(course_id):
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if not enrollment:
        enrollment = Enrollment(student_id=current_user.id, course_id=course_id)
        db.session.add(enrollment)
        db.session.commit()
    
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()
    enrollment_sections = {es.section_id: es for es in enrollment.sections}
    
    # Determine which sections are locked
    locked_sections = set()
    for i, section in enumerate(sections):
        es = enrollment_sections.get(section.id)
        if i == 0:  # First section is always unlocked
            continue
        prev_section = sections[i-1]
        prev_es = enrollment_sections.get(prev_section.id)
        if not prev_es or not prev_es.completed:
            locked_sections.add(section.id)
    
    return render_template('student/course_detail.html', 
                         course=course, 
                         sections=sections,
                         enrollment=enrollment,
                         locked_sections=locked_sections)

@student_bp.route('/section/<int:section_id>/content')
@login_required
def get_section_content(section_id):
    # Allow access for students and admins
    if current_user.role not in ['student', 'admin']:
        return jsonify({"error": "Unauthorized"}), 403
    
    section = Section.query.get_or_404(section_id)
    
    # For students, check enrollment and section locking
    if current_user.role == 'student':
        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
        if not enrollment:
            return jsonify({"error": "Not enrolled"}), 403
        
        # Check if section is locked
        sections = Section.query.filter_by(course_id=section.course_id).order_by(Section.order).all()
        section_idx = next(i for i, s in enumerate(sections) if s.id == section_id)
        if section_idx > 0:
            prev_section = sections[section_idx - 1]
            prev_es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=prev_section.id).first()
            if not prev_es or not prev_es.completed:
                return jsonify({"error": "Section locked"}), 403

    # Generate the content HTML
    content_html = ""
    if section.section_type == 'video':
        youtube_id = section.content.split('v=')[1].split('&')[0] if 'v=' in section.content else section.content.split('/')[-1]
        content_html = f"""
            <div class="aspect-w-16 aspect-h-9">
                <iframe id="youtube-player-{section.id}" 
                        class="w-full h-64 md:h-96" 
                        src="https://www.youtube.com/embed/{youtube_id}?enablejsapi=1" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowfullscreen></iframe>
            </div>
        """
    elif section.section_type == 'pdf':
        # For admins, use the admin route to serve PDFs; for students, use the student route
        pdf_url = url_for('admin.serve_pdf', filename=section.content) if current_user.role == 'admin' else url_for('student.view_pdf', section_id=section.id)
        content_html = f"""
            <a href="{pdf_url}" 
               class="text-blue-600 hover:underline flex items-center" target="_blank">
                <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                </svg>
                View PDF
            </a>
        """
    else:  # text
        content_html = f"""
            <div class="prose max-w-none mt-2" id="text-content-{section.id}">
                {section.content}
            </div>
        """
    
    # Return raw HTML for admins (since admin template uses hx-swap="innerHTML")
    # Return JSON for students (since student template expects JSON)
    if current_user.role == 'admin':
        return content_html
    else:
        return jsonify({
            "content": content_html,
            "section_type": section.section_type,
            "section_id": section.id
        })

@student_bp.route('/section/<int:section_id>/mark-completed', methods=['POST'])
@login_required
def mark_section_completed(section_id):
    if current_user.role != 'student':
        return jsonify({"error": "Unauthorized"}), 403
    
    section = Section.query.get_or_404(section_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        return jsonify({"error": "Not enrolled"}), 403
    
    es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not es:
        es = EnrollmentSection(
            enrollment_id=enrollment.id,
            section_id=section_id,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(es)
    else:
        es.completed = True
        es.completed_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"message": "Section marked as completed"}), 200

@student_bp.route('/view-pdf/<int:section_id>')
@login_required
def view_pdf(section_id):
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    
    section = Section.query.get_or_404(section_id)
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=section.course_id).first()
    if not enrollment:
        abort(403)
    
    # Mark as completed when PDF is viewed
    es = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id, section_id=section_id).first()
    if not es:
        es = EnrollmentSection(
            enrollment_id=enrollment.id,
            section_id=section_id,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(es)
    else:
        es.completed = True
        es.completed_at = datetime.utcnow()
    
    db.session.commit()
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], section.content)