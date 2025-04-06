from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'student':
        return redirect(url_for('auth.login'))
    return render_template('student/dashboard.html', user=current_user)