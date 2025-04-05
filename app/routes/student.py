from flask import Blueprint, render_template
from flask_login import login_required, current_user

student_bp = Blueprint('student', __name__)

@student_bp.route('/student/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    return render_template('student/dashboard.html')