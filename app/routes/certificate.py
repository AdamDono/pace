from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user  # Added current_user import
from app import db
from app.models import Course, Enrollment, Section, EnrollmentSection, Rating

certificate_bp = Blueprint('certificate', __name__, url_prefix='/student')

@certificate_bp.route('/certificates')
@login_required
def certificates():
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    certificates = []
    for enrollment in enrollments:
        course = Course.query.get(enrollment.course_id)
        if course:
            total_sections = Section.query.filter_by(course_id=course.id).count()
            completed_sections = Section.query.join(EnrollmentSection).filter(
                Section.course_id == course.id,
                EnrollmentSection.enrollment_id == enrollment.id,
                EnrollmentSection.completed == True
            ).count()
            completion_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0
            rating = Rating.query.filter_by(course_id=course.id, student_id=current_user.id).first()
            has_rating = bool(rating)
            if completion_percentage == 100 and has_rating:
                certificates.append({
                    'id': course.id,
                    'title': course.title,
                    'enrollment_id': enrollment.id,
                    'banner_image': course.banner_image 
                })
    return render_template('student/certificates.html', certificates=certificates)

@certificate_bp.route('/enhanced-dashboard')
@login_required
def enhanced_dashboard():
    from app.models import Course, Enrollment  
    enrolled_courses = Course.query.join(Enrollment)\
        .filter(Enrollment.student_id == current_user.id)\
        .filter(Course.status == 'approved')\
        .all()
    courses_with_progress = []
    for course in enrolled_courses:
        enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if enrollment:
            total_sections = Section.query.filter_by(course_id=course.id).count()
            completed_sections = Section.query.join(EnrollmentSection).filter(
                Section.course_id == course.id,
                EnrollmentSection.enrollment_id == enrollment.id,
                EnrollmentSection.completed == True
            ).count()
            completion_percentage = (completed_sections / total_sections * 100) if total_sections > 0 else 0
            rating = Rating.query.filter_by(course_id=course.id, student_id=current_user.id).first()
            has_rating = bool(rating)
            courses_with_progress.append({
                'id': course.id,
                'title': course.title,
                'banner_image': course.banner_image,  # Assuming banner_image exists
                'completion_percentage': completion_percentage,
                'enrollment_id': enrollment.id,
                'has_rating': has_rating
            })
    return render_template('student/courses.html', courses=courses_with_progress)