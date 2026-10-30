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

    # Live stats
    learner_count = User.query.filter_by(role='student').count()
    course_count  = Course.query.filter(Course.status == 'approved').count()

    # Up to 5 users who have uploaded a profile picture (for avatar stack)
    users_with_avatars = User.query.filter(
        User.profile_image.isnot(None),
        User.profile_image != ''
    ).limit(5).all()

    return render_template(
        'auth/landing.html',
        courses=courses,
        learner_count=learner_count,
        course_count=course_count,
        users_with_avatars=users_with_avatars,
    )

@auth_bp.route('/privacy')
def privacy_policy():
    return render_template('auth/privacy.html')

@auth_bp.route('/terms')
def terms_of_service():
    return render_template('auth/terms.html')

@auth_bp.route('/pricing')
def pricing():
    plan = request.args.get('plan')
    tab = request.args.get('tab')
    if plan:
        return redirect(url_for('auth.landing', plan=plan, _anchor='pricing'))
    if tab:
        return redirect(url_for('auth.landing', tab=tab, _anchor='pricing'))
    return redirect(url_for('auth.landing', _anchor='pricing'))

@auth_bp.route('/courses/<identifier>')
@auth_bp.route('/course/<identifier>')
def public_course_detail(identifier):
    from app.models import Course
    from flask import abort
    
    course = None
    # If accessed via numeric ID, check and redirect to canonical SEO slug
    if str(identifier).isdigit():
        course = Course.query.get(int(identifier))
        if course and course.slug:
            return redirect(url_for('auth.public_course_detail', identifier=course.slug), code=301)
    
    if not course:
        course = Course.query.filter_by(slug=identifier).first()
        
    if not course:
        if str(identifier).isdigit():
            course = Course.query.get_or_404(int(identifier))
        else:
            abort(404)

    if course.status != 'approved':
        if not (current_user.is_authenticated and (current_user.role == 'admin' or (current_user.role == 'teacher' and course.teacher_id == current_user.id))):
            abort(404)

    return render_template('auth/public_course.html', course=course)

@auth_bp.route('/apply-course/<identifier>', methods=['POST'])
@csrf.exempt
def apply_course(identifier):
    from flask import jsonify
    from app.models import Course, Lead
    from app.utils.email import send_email
    
    course = None
    if str(identifier).isdigit():
        course = Course.query.get(int(identifier))
    if not course:
        course = Course.query.filter_by(slug=identifier).first()
    if not course:
        return jsonify({'success': False, 'message': 'Course not found.'}), 404
    
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
        from app.routes.analytics import record_analytics_event
        record_analytics_event('lead_submitted', event_label=f"Course: {course.title}", page_path=request.path)
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

@auth_bp.route('/apply-plan', methods=['POST'])
@csrf.exempt
def apply_plan():
    from flask import jsonify
    from app.models import Lead
    from app.utils.email import send_email
    
    plan_id = request.form.get('plan_id', 'general')
    plan_name = request.form.get('plan_name', 'Pace Academy Plan')
    plan_category = request.form.get('plan_category', 'school')
    billing_cycle = request.form.get('billing_cycle', '')
    
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    
    # Specific fields based on plan category
    school_name = request.form.get('school_name', '').strip()
    grade_level = request.form.get('grade_level', '').strip()
    struggle_subjects = request.form.get('struggle_subjects', '').strip()
    
    employment_status = request.form.get('employment_status', '').strip()
    career_interest = request.form.get('career_interest', '').strip()
    id_number = request.form.get('id_number', '').strip()
    
    organization = request.form.get('organization', '').strip()
    raw_learners = request.form.get('estimated_learners', '').strip()
    estimated_learners = int(raw_learners) if raw_learners and raw_learners.isdigit() else None
    
    user_message = request.form.get('message', '').strip()
    
    if not (full_name and email and phone):
        return jsonify({'success': False, 'message': 'Please provide your full name, email address, and phone number.'}), 400

    # Categorize lead_type
    lead_type = 'individual'
    org_field = organization or school_name or None
    emp_field = grade_level or employment_status or None
    
    if plan_category in ['school', 'High School & Matric']:
        lead_type = 'school_plan'
    elif plan_category in ['skills', 'Digital Career Skills']:
        lead_type = 'skills_plan'
    elif plan_category in ['enterprise', 'Enterprise B2B']:
        lead_type = 'enterprise'
    
    # Build clean inquiry_type for admin dashboard
    inquiry_label = f"{plan_name} ({billing_cycle})" if billing_cycle else plan_name
    
    # Build rich details string
    details = [f"Plan: {inquiry_label}"]
    if school_name:
        details.append(f"School: {school_name}")
    if grade_level:
        details.append(f"Grade: {grade_level}")
    if struggle_subjects:
        details.append(f"Target Subjects: {struggle_subjects}")
    if employment_status:
        details.append(f"Status: {employment_status}")
    if career_interest:
        details.append(f"Career Focus: {career_interest}")
    if id_number:
        details.append(f"National ID: {id_number}")
    if organization:
        details.append(f"Organization: {organization}")
    if estimated_learners:
        details.append(f"Learners: {estimated_learners}")
    if user_message:
        details.append(f"Note: {user_message}")
        
    full_message = " | ".join(details)
    
    lead = Lead(
        full_name=full_name,
        email=email,
        phone=phone,
        lead_type=lead_type,
        organization=org_field,
        employment_status=emp_field,
        inquiry_type=inquiry_label,
        estimated_learners=estimated_learners,
        message=full_message
    )
    db.session.add(lead)
    try:
        db.session.commit()
        from app.routes.analytics import record_analytics_event
        record_analytics_event('lead_submitted', event_label=f"Plan: {inquiry_label}", page_path='/')
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Database storage failed. Please try again.'}), 500
        
    # Send email notifications
    admin_recipient = 'adam@pacetech.co.za'
    try:
        send_email(
            subject=f'New Plan Registration: {inquiry_label} - {full_name}',
            recipient=admin_recipient,
            template='admin_admission_alert',
            full_name=full_name,
            email=email,
            phone=phone,
            employment_status=emp_field,
            message=full_message,
            course_title=inquiry_label
        )
    except Exception:
        pass
        
    try:
        send_email(
            subject=f'Welcome to Pace Academy - {plan_name} Application Received',
            recipient=email,
            template='student_admission_confirm',
            full_name=full_name,
            course_title=inquiry_label
        )
    except Exception:
        pass
        
    return jsonify({
        'success': True,
        'message': f'Thank you {full_name}! Your enrollment application for {plan_name} has been received. Our team will contact you on WhatsApp/phone to activate your account.',
        'plan_name': plan_name,
        'inquiry_label': inquiry_label
    })

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If student or lead clicked a pricing plan link (?plan=matric_core etc.), route directly to pricing modal
    plan = request.args.get('plan')
    if plan and request.method == 'GET':
        return redirect(url_for('auth.landing', plan=plan, _anchor='pricing'))

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
    user_email = (getattr(current_user, 'email', '') or '').strip().lower()
    if user_email == 'analytics@gmail.com' or current_user.role == 'analytics':
        return redirect(url_for('analytics.dashboard'))
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
            
            # Generate absolute reset URL using BASE_URL config to ensure correct scheme and domain
            base_url = current_app.config.get('BASE_URL', 'https://pace-academy.co.za').rstrip('/')
            reset_url = f"{base_url}{url_for('auth.reset_password', token=token)}"
            
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


# ---------------------------------------------------------------------------
# Guest Bookworm Rate-Limiting & Credit Protection (3-Layer Defense)
# Layer 1: 30-Day Signed HTTP-Only Cookie + Permanent Session + Client localStorage
# Layer 2: 24-Hour Server-Side IP Hash Rate Limit (persisted to instance/ across workers)
# Layer 3: Pre-Cached Starter Chip Responses + Pre-Recorded Puck Voice WAVs (0 API cost)
# ---------------------------------------------------------------------------
_GUEST_BW_MAX_QUESTIONS = 5
_GUEST_BW_TTL_SECONDS = 86400  # 24 hours per IP reset window
_GUEST_BW_COOKIE_NAME = 'pace_guest_bw'
_GUEST_BW_COOKIE_MAX_AGE = 86400 * 30  # 30 days

_PRE_CACHED_GUEST_CHIPS = {
    "how do you help me pass matric life sciences & maths?": {
        "reply": (
            "Instead of just giving away final answers, I coach you step-by-step using Socratic questions, "
            "interactive 3D science models, and past paper drills so you truly master Matric Life Sciences, Maths, and Physics!"
        ),
        "audio_file": "audio/bookworm_chip_matric.wav"
    },
    "which accredited digital skills courses can i study?": {
        "reply": (
            "You can study practical job-ready courses like Web Development, End User Computing, and Business Practice, "
            "and earn verifiable digital certificates with a live QR code for your CV and employers!"
        ),
        "audio_file": "audio/bookworm_chip_skills.wav"
    },
    "how does the report card aps scanner work?": {
        "reply": (
            "Just upload a photo of your school report card! Our scanner automatically calculates your official university APS score, "
            "shows which South African degrees you qualify for, and builds your weekly revision timetable."
        ),
        "audio_file": "audio/bookworm_chip_aps.wav"
    }
}


def _get_guest_ip_hash() -> str:
    import hashlib
    forwarded = request.headers.get('X-Forwarded-For', '')
    raw_ip = forwarded.split(',')[0].strip() if forwarded else (request.remote_addr or 'unknown')
    return hashlib.sha256(f"pace_bw_{raw_ip}".encode('utf-8')).hexdigest()[:24]


def _load_ip_store() -> dict:
    import os, json, time
    from flask import current_app
    store_path = os.path.join(current_app.instance_path, 'guest_bw_limits.json')
    now = time.time()
    try:
        if os.path.exists(store_path):
            with open(store_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(v, dict) and v.get('exp', 0) > now}
    except Exception:
        pass
    return {}


def _save_ip_store(data: dict) -> None:
    import os, json
    from flask import current_app
    try:
        os.makedirs(current_app.instance_path, exist_ok=True)
        store_path = os.path.join(current_app.instance_path, 'guest_bw_limits.json')
        with open(store_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def _read_signed_guest_cookie() -> int:
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    token = request.cookies.get(_GUEST_BW_COOKIE_NAME)
    if not token:
        return 0
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        payload = s.loads(token, salt='guest-bw-limit', max_age=_GUEST_BW_COOKIE_MAX_AGE)
        return int(payload.get('c', 0))
    except Exception:
        return 0


def _write_signed_guest_cookie(response, count: int):
    from itsdangerous import URLSafeTimedSerializer
    from flask import current_app
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps({'c': int(count)}, salt='guest-bw-limit')
        response.set_cookie(
            _GUEST_BW_COOKIE_NAME,
            token,
            max_age=_GUEST_BW_COOKIE_MAX_AGE,
            httponly=True,
            samesite='Lax'
        )
    except Exception:
        pass
    return response


def _get_effective_guest_count(client_count: int = 0) -> int:
    ip_hash = _get_guest_ip_hash()
    ip_store = _load_ip_store()
    ip_count = int((ip_store.get(ip_hash) or {}).get('count', 0))
    cookie_count = _read_signed_guest_cookie()
    session_count = int(session.get('guest_bookworm_count', 0))
    return max(ip_count, cookie_count, session_count, int(client_count or 0))


def _record_guest_count(new_count: int) -> None:
    import time
    session.permanent = True
    session['guest_bookworm_count'] = new_count
    ip_hash = _get_guest_ip_hash()
    ip_store = _load_ip_store()
    existing_exp = (ip_store.get(ip_hash) or {}).get('exp')
    ip_store[ip_hash] = {
        'count': new_count,
        'exp': existing_exp if existing_exp else (time.time() + _GUEST_BW_TTL_SECONDS)
    }
    _save_ip_store(ip_store)


@auth_bp.route('/guest-bookworm-status', methods=['GET'])
def guest_bookworm_status():
    """Returns the visitor's remaining free questions across IP, signed cookie, and session."""
    used = _get_effective_guest_count(0)
    rem = max(0, _GUEST_BW_MAX_QUESTIONS - used)
    resp = jsonify({
        'success': True,
        'question_count': min(used, _GUEST_BW_MAX_QUESTIONS),
        'remaining': rem,
        'limit_reached': used >= _GUEST_BW_MAX_QUESTIONS
    })
    return _write_signed_guest_cookie(resp, used)


@auth_bp.route('/guest-bookworm-chat', methods=['POST'])
@csrf.exempt
def guest_bookworm_chat():
    """
    Public guest preview endpoint for the Hero Bookworm mascot on the landing page.
    Allows up to 5 free guest questions (enforced by IP + 30-day signed cookie + session + localStorage),
    serves pre-cached starter chips at zero API cost, and then prompts the visitor to choose a course/plan
    or log in to continue.
    """
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    client_count = int(data.get('question_count') or 0)

    if not user_message:
        return jsonify({'success': False, 'message': 'Please type a question first.'}), 400

    effective_before = _get_effective_guest_count(client_count)
    if effective_before >= _GUEST_BW_MAX_QUESTIONS:
        cta_reply = (
            "You've used all 5 of your free guest questions! "
            "To keep studying with me 24/7, choose a course or plan below and submit the enrollment form, or log in to your account."
        )
        resp = jsonify({
            'success': True,
            'reply': cta_reply,
            'audio_url': None,
            'question_count': _GUEST_BW_MAX_QUESTIONS,
            'remaining': 0,
            'limit_reached': True
        })
        return _write_signed_guest_cookie(resp, _GUEST_BW_MAX_QUESTIONS)

    current_count = effective_before + 1
    _record_guest_count(current_count)
    try:
        from app.routes.analytics import record_analytics_event
        record_analytics_event('bookworm_question', event_label=user_message[:140], page_path='/')
    except Exception:
        pass

    remaining = max(0, _GUEST_BW_MAX_QUESTIONS - current_count)
    limit_reached = current_count >= _GUEST_BW_MAX_QUESTIONS

    # Layer 3: Check if this is one of the 3 starter chips (0 API cost + instant pre-recorded Puck WAV!)
    norm_q = user_message.lower().strip()
    if norm_q in _PRE_CACHED_GUEST_CHIPS:
        chip_data = _PRE_CACHED_GUEST_CHIPS[norm_q]
        reply_text = chip_data["reply"]
        if limit_reached:
            reply_text += " You've now used all 5 free trial questions—choose a course and submit the form below, or log in to keep studying with me!"
        audio_url = None
        import os
        from flask import current_app
        wav_abs = os.path.join(current_app.root_path, 'static', chip_data["audio_file"])
        if os.path.exists(wav_abs):
            audio_url = url_for('static', filename=chip_data["audio_file"])
        resp = jsonify({
            'success': True,
            'reply': reply_text,
            'audio_url': audio_url,
            'question_count': current_count,
            'remaining': remaining,
            'limit_reached': limit_reached,
            'cached': True
        })
        return _write_signed_guest_cookie(resp, current_count)

    reply_text = None
    audio_url = None
    try:
        from app.services.ai_service import AIService
        from app.services.ai_tutor import BookwormTutorService, requests as _tutor_requests
        import certifi

        api_key = AIService.get_api_key()
        if api_key:
            system_prompt = (
                "You are Bookworm, the warm, encouraging 24/7 Socratic AI Tutor on Pace Academy's homepage in South Africa. "
                "Keep your response concise (2 to 3 short sentences max, under 55 words) so it is quick to read and speak aloud. "
                "About Pace Academy: "
                "1) High School (Grades 10-12): Free Starter (R0, 2 subjects: English & Home Language), Matric Core (R699/year or R89/month for all 5 CAPS subjects, 3D models, report card APS scanner & unlimited Bookworm AI), and Varsity & Skills Pro (R999/year adding an accredited digital course & university application guidance). "
                "2) Digital Skills & Careers: Single Course Pass (from R150), All-Access Skills Pass (R199/month), and SETA/QCTO Accredited Course Pass (R1,500 once-off). "
                "3) Corporates & Skills Dev: Corporate Upskilling (R5,000/month) and SDP Portal (R500/learner/month). "
                "If the visitor asks a school/coding/study question, guide them Socratically with a helpful hint and one follow-up question. "
                + (
                    " Since this is their 5th and final free guest question, finish by warmly inviting them to choose a course and submit the form, or log in to keep learning with you!"
                    if limit_reached else ""
                )
            )
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{system_prompt}\n\nVisitor question ({current_count}/5): {user_message}"}]}
                ],
                "generationConfig": {"temperature": 0.6, "maxOutputTokens": 160}
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            res = _tutor_requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=8,
                verify=certifi.where()
            )
            if res.status_code == 200:
                resp_json = res.json()
                candidates = resp_json.get("candidates") or []
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts") or []
                    if parts:
                        reply_text = (parts[0].get("text") or "").strip()
    except Exception:
        reply_text = None

    if not reply_text:
        # Instant smart fallback if offline or sandboxed
        q_lower = user_message.lower()
        if any(w in q_lower for w in ['price', 'cost', 'plan', 'how much', 'pay', 'matric']):
            reply_text = (
                "Our Free Starter gives you English and Home Language for R0! "
                "To unlock all 5 CAPS subjects, interactive 3D models, and 24/7 Bookworm coaching, Matric Core is just R699 per year (or Varsity & Skills Pro at R999/year)."
            )
        elif any(w in q_lower for w in ['course', 'skill', 'code', 'coding', 'accredit', 'seta', 'certificate']):
            reply_text = (
                "We offer practical digital skills like Web Development, End User Computing, and Business Practice, with verifiable QR certificates! "
                "You can start a single course from R150, get the R199/month All-Access Pass, or enroll in a full SETA-accredited qualification."
            )
        elif any(w in q_lower for w in ['aps', 'university', 'report', 'wits', 'uj', 'up']):
            reply_text = (
                "With our Report Card Scanner, you upload your school report and we automatically calculate your official APS score, show which South African university degrees you qualify for, and build your study timetable!"
            )
        else:
            reply_text = (
                "Great question! At Pace Academy, I don't just hand out final answers—I coach you step-by-step so you truly master the concept for your exams and career. What subject or digital skill are you most excited to improve this year?"
            )
        if limit_reached:
            reply_text += " You've reached your 5th free guest question—choose a course and submit the form below, or log in to keep studying with me!"

    # Try generating Puck neural voice audio if network is available
    try:
        from app.services.ai_tutor import BookwormTutorService
        tts_res = BookwormTutorService.generate_neural_speech(reply_text, voice="Puck")
        if tts_res and tts_res.get("success") and tts_res.get("audio_url"):
            audio_url = tts_res["audio_url"]
    except Exception:
        audio_url = None

    resp = jsonify({
        'success': True,
        'reply': reply_text,
        'audio_url': audio_url,
        'question_count': current_count,
        'remaining': remaining,
        'limit_reached': limit_reached
    })
    return _write_signed_guest_cookie(resp, current_count)
