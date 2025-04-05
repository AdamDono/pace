from flask import Blueprint, render_template
from flask_login import login_required, current_user

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/teacher/dashboard')
@login_required
def dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('auth.login'))
    return render_template('teacher/dashboard.html')