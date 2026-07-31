from functools import wraps
from flask import abort
from flask_login import current_user
from app.models import User

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def student_enrolled(course_id):
    from app.models import Enrollment, Course
    if not current_user.is_authenticated or current_user.role != 'student':
        return False
    course = Course.query.get(course_id)
    if not course or course.status != 'approved':
        return False
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()
    if not enrollment or getattr(enrollment, 'is_blocked', False):
        return False
    return True

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function