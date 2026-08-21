from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from app.models import User
from app import db, csrf
from app.forms import LoginForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    if current_user.is_authenticated:
        return redirect_based_on_role()
    
    from app.models import Course, Enrollment, User
    # Get approved public courses for display on the landing page
    courses = Course.query.filter(Course.status == 'approved', Course.visibility != 'private').limit(6).all()

    # Live stats for about section
    learner_count = User.query.filter_by(role='student').count()
    course_count  = Course.query.filter(Course.status == 'approved').count()

    return render_template(
        'auth/landing.html',
        courses=courses,
        learner_count=learner_count,
        course_count=course_count,
    )

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
@csrf.exempt
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
@csrf.exempt
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

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Cleanly log out current user without 500 errors"""
    try:
        if current_user and current_user.is_authenticated:
            logout_user()
    except Exception:
        pass
    session.pop('last_activity', None)
    session.pop('_user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/ping-session', methods=['POST', 'GET'])
def ping_session():
    """Lightweight endpoint to refresh the 10-minute inactivity session timer"""
    from flask import session, jsonify
    from datetime import datetime, timezone
    if current_user and current_user.is_authenticated:
        session['last_activity'] = datetime.now(timezone.utc).timestamp()
        return jsonify({'status': 'active', 'timestamp': session['last_activity']})
    return jsonify({'status': 'unauthenticated'}), 401

def redirect_based_on_role():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher.dashboard'))
    elif current_user.role == 'student':
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect_based_on_role()
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if user:
            from itsdangerous import URLSafeTimedSerializer
            from flask import current_app
            from app.utils.email import send_email
            
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(user.email, salt='password-reset-salt')
            
            # Generate absolute reset URL
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            send_email(
                subject='Reset Your Password - Pace Academy',
                recipient=user.email,
                template='reset_password',
                user=user,
                reset_url=reset_url
            )
            
        flash('If this email is registered in our system, a password reset link has been sent to it.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect_based_on_role()
        
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
    from flask import current_app
    
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # Token is valid for 1 hour (3600 seconds)
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))
        
    user = User.query.filter_by(email=email).first_or_404()
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/reset_password.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html')
            
        user.password = password
        db.session.commit()
        
        flash('Your password has been reset successfully. You can now login.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html')