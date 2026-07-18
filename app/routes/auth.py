from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from app.models import User
from app import db
from app.forms import LoginForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect_based_on_role()
    
    from app.models import Course
    # Get up to 6 approved courses for public display on the landing page
    courses = Course.query.filter_by(status='approved').limit(6).all()
    return render_template('auth/landing.html', courses=courses)

@auth_bp.route('/course/<int:course_id>')
def public_course_detail(course_id):
    from app.models import Course
    course = Course.query.get_or_404(course_id)
    if course.status != 'approved':
        if not (current_user.is_authenticated and (current_user.role == 'admin' or (current_user.role == 'teacher' and course.teacher_id == current_user.id))):
            from flask import abort
            abort(404)
    return render_template('auth/public_course.html', course=course)

@auth_bp.route('/apply-course/<int:course_id>', methods=['POST'])
def apply_course(course_id):
    from flask import jsonify
    from app.models import Course, Lead
    from app.utils.email import send_email
    
    course = Course.query.get_or_404(course_id)
    
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    employment_status = request.form.get('employment_status')
    message = request.form.get('message', '')
    
    if not (full_name and email and phone):
        return jsonify({'success': False, 'message': 'Please fill in all required fields.'}), 400
        
    # Save lead to database
    lead = Lead(
        full_name=full_name,
        email=email,
        phone=phone,
        course_id=course.id,
        employment_status=employment_status,
        message=message
    )
    db.session.add(lead)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log error or return failure if DB fails
        return jsonify({'success': False, 'message': 'Database storage failed. Please try again later.'}), 500
        
    admin_recipient = 'adam@pacetech.co.za'
    send_email(
        subject=f'New Course Application - {full_name}',
        recipient=admin_recipient,
        template='admin_admission_alert',
        full_name=full_name,
        email=email,
        phone=phone,
        employment_status=employment_status,
        message=message,
        course_title=course.title
    )
    
    send_email(
        subject='Admission Application Received - Pace Academy',
        recipient=email,
        template='student_admission_confirm',
        full_name=full_name,
        course_title=course.title
    )
    
    return jsonify({'success': True, 'message': 'Application submitted successfully!'})

@auth_bp.route('/apply-enterprise', methods=['POST'])
def apply_enterprise():
    from flask import jsonify
    from app.models import Lead
    from app.utils.email import send_email
    
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    organization = request.form.get('organization')
    inquiry_type = request.form.get('inquiry_type')
    message = request.form.get('message', '')
    
    raw_learners = request.form.get('estimated_learners')
    estimated_learners = int(raw_learners) if raw_learners and raw_learners.isdigit() else None
    
    if not (full_name and email and phone and organization and inquiry_type):
        return jsonify({'success': False, 'message': 'Please fill in all required fields.'}), 400
        
    lead = Lead(
        full_name=full_name,
        email=email,
        phone=phone,
        lead_type='enterprise',
        organization=organization,
        inquiry_type=inquiry_type,
        estimated_learners=estimated_learners,
        message=message
    )
    db.session.add(lead)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Database storage failed. Please try again later.'}), 500
        
    admin_recipient = 'adam@pacetech.co.za'
    send_email(
        subject=f'New Enterprise Inquiry - {organization}',
        recipient=admin_recipient,
        template='admin_enterprise_alert',
        full_name=full_name,
        email=email,
        phone=phone,
        organization=organization,
        inquiry_type=inquiry_type,
        estimated_learners=estimated_learners,
        message=message
    )
    
    send_email(
        subject='Institutional Proposal Request Received - Pace Academy',
        recipient=email,
        template='student_enterprise_confirm',
        full_name=full_name,
        organization=organization
    )
    
    return jsonify({'success': True, 'message': 'Proposal request submitted successfully!'})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_based_on_role()
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.verify_password(form.password.data):
            # Check if account is banned
            if user.is_banned:
                flash('Your account has been permanently banned. Reason: ' + (user.suspension_reason or 'Violation of terms'), 'danger')
                return render_template('auth/login.html', form=form)
            
            # Check if account is suspended
            if user.is_suspended:
                from datetime import datetime
                # Check if suspension has expired
                if user.suspended_until and datetime.utcnow() > user.suspended_until:
                    # Auto-unsuspend
                    user.is_suspended = False
                    user.suspended_until = None
                    db.session.commit()
                else:
                    # Still suspended
                    if user.suspended_until:
                        flash(f'Your account is suspended until {user.suspended_until.strftime("%B %d, %Y at %I:%M %p")}. Reason: {user.suspension_reason or "Not specified"}', 'warning')
                    else:
                        flash(f'Your account is suspended indefinitely. Reason: {user.suspension_reason or "Not specified"}', 'warning')
                    return render_template('auth/login.html', form=form)
            
            # Track login activity
            from datetime import datetime
            user.last_login = datetime.utcnow()
            user.login_count = (user.login_count or 0) + 1
            db.session.commit()
            
            login_user(user, remember=form.remember.data)
            return redirect_based_on_role()
        flash('Invalid email or password', 'danger')
    return render_template('auth/login.html', form=form)

# Public registration disabled - users are created by admin/teachers only

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

def redirect_based_on_role():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher.dashboard'))
    elif current_user.role == 'student':
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))