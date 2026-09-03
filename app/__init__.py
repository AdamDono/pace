from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_session import Session
from jinja2 import Environment
from flask_wtf import CSRFProtect  # Add this import

def format_datetime(value, format='medium'):
    if format == 'full':
        format = "%Y-%m-%d %H:%M:%S"
    elif format == 'medium':
        format = "%Y-%m-%d"
    return value.strftime(format)

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()  # Add this line
mail = Mail()

def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Enable ProxyFix middleware for Render HTTPS proxy support
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.jinja_env.filters['datetimeformat'] = format_datetime

    # Register custom Jinja filter for average
    def average_filter(items):
        if not items:
            return 0
        items_list = list(items)
        if not items_list:
            return 0
        return sum(items_list) / len(items_list)

    app.jinja_env.filters['average'] = average_filter

    def avatar_url_filter(img):
        if not img:
            return ''
        if img.startswith('http://') or img.startswith('https://'):
            return img
        if img.startswith('/static/'):
            return img
        return f"/static/uploads/{img}"

    app.jinja_env.filters['avatar_url'] = avatar_url_filter
    app.jinja_env.filters['media_url'] = avatar_url_filter
    app.jinja_env.globals.update(min=min, max=max)

    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///default.db')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['BASE_URL'] = os.getenv('BASE_URL', 'http://localhost:5000')
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
    }

    # Configure uploads & form payload limits (Prevent 413 Content Too Large on rich text & images)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max payload limit
    app.config['MAX_FORM_MEMORY_SIZE'] = 50 * 1024 * 1024  # 50MB form field memory limit for Base64 rich content
    app.config['WTF_CSRF_ENABLED'] = True  # Enabled for security
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Do not expire CSRF tokens during session
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'zip', 'rar', '7z', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'doc', 'txt', 'csv', 'py', 'js', 'html', 'css', 'mp4', 'webm'}

    # Configure email
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@paceacademy.com')

    # Enable template auto-reload for instant design updates
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Configure 9-hour session inactivity limit
    from datetime import timedelta
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=9)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    # Remember Me cookie configuration (30 days persistent login)
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_REFRESH_EACH_REQUEST'] = True

    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Add this line
    mail.init_app(app)
    login_manager.login_view = 'auth.login'

    # Auto-migrate Postgres database columns if running on Render/Production DB
    with app.app_context():
        try:
            # Create any missing tables (like modules, leads, etc.) without affecting existing ones
            db.create_all()
            
            from sqlalchemy import inspect, text
            
            def add_column_if_missing(table_name, column_name, column_type):
                try:
                    insp = inspect(db.engine)
                    columns = [c['name'] for c in insp.get_columns(table_name)]
                    if column_name not in columns:
                        db_type = column_type
                        if db.engine.name == 'sqlite':
                            db_type = column_type.replace('VARCHAR', 'TEXT').replace('BOOLEAN', 'INTEGER')
                        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {db_type};"))
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    if 'already exists' in str(e).lower() or 'duplicate column' in str(e).lower():
                        pass
                    else:
                        app.logger.warning(f"Note on {table_name}.{column_name}: {e}")
            
            # Check and add columns to users
            add_column_if_missing('users', 'id_number', 'VARCHAR(30)')

            # Check and add columns to enrollments
            add_column_if_missing('enrollments', 'completed_at', 'TIMESTAMP')
            add_column_if_missing('enrollments', 'certificate_path', 'VARCHAR(255)')
            add_column_if_missing('enrollments', 'is_blocked', 'BOOLEAN DEFAULT FALSE')
            add_column_if_missing('enrollments', 'block_reason', 'VARCHAR(500)')
            add_column_if_missing('enrollments', 'last_nudge_sent_at', 'TIMESTAMP')
            
            # Check and add columns to courses
            add_column_if_missing('courses', 'accreditation_name', 'VARCHAR(255)')
            add_column_if_missing('courses', 'updated_at', 'TIMESTAMP')
            add_column_if_missing('courses', 'category', 'VARCHAR(50)')
            add_column_if_missing('courses', 'difficulty_level', 'VARCHAR(20)')
            add_column_if_missing('courses', 'estimated_duration', 'INTEGER')
            add_column_if_missing('courses', 'language', 'VARCHAR(20)')
            add_column_if_missing('courses', 'learning_objectives', 'TEXT')
            add_column_if_missing('courses', 'prerequisites', 'TEXT')
            add_column_if_missing('courses', 'tags', 'VARCHAR(255)')
            add_column_if_missing('courses', 'is_draft', 'BOOLEAN DEFAULT FALSE')
            add_column_if_missing('courses', 'last_autosave', 'TIMESTAMP')
            add_column_if_missing('courses', 'visibility', 'VARCHAR(20) DEFAULT \'public\'')
            add_column_if_missing('courses', 'is_coming_soon', 'BOOLEAN DEFAULT FALSE')
            add_column_if_missing('courses', 'max_seats', 'INTEGER')
            add_column_if_missing('courses', 'certificate_theme', 'VARCHAR(30) DEFAULT \'gold\'')
            add_column_if_missing('courses', 'custom_certificate_title', 'VARCHAR(120)')
            add_column_if_missing('courses', 'instructor_signature', 'VARCHAR(255)')
            add_column_if_missing('courses', 'partner_name', 'VARCHAR(150)')
            add_column_if_missing('courses', 'partner_logo', 'VARCHAR(255)')
            add_column_if_missing('courses', 'partner_accreditation_number', 'VARCHAR(120)')
            add_column_if_missing('courses', 'partner_signatory_name', 'VARCHAR(120)')
            add_column_if_missing('courses', 'partner_signatory_title', 'VARCHAR(120)')
            add_column_if_missing('courses', 'partner_signatory_signature', 'VARCHAR(255)')
            add_column_if_missing('courses', 'price', 'FLOAT DEFAULT 250.0')
            add_column_if_missing('courses', 'pricing_type', 'VARCHAR(30) DEFAULT \'monthly\'')
            add_column_if_missing('courses', 'slug', 'VARCHAR(140)')

            # Auto-backfill slugs for existing courses missing a slug
            try:
                from app.models import Course
                unslugged = Course.query.filter((Course.slug == None) | (Course.slug == '')).all()
                for c in unslugged:
                    base = Course.generate_slug(c.title, c.id)
                    cand = base
                    ctr = 1
                    while Course.query.filter(Course.slug == cand, Course.id != c.id).first():
                        cand = f"{base}-{ctr}"
                        ctr += 1
                    c.slug = cand
                if unslugged:
                    db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.warning(f"Note on backfilling course slugs: {e}")
            
            # Check and add columns for multi-attempt limits (3 tries default)
            add_column_if_missing('assignments', 'max_attempts', 'INTEGER DEFAULT 3')
            add_column_if_missing('quizzes', 'max_attempts', 'INTEGER DEFAULT 3')
            add_column_if_missing('assignment_submissions', 'attempt_number', 'INTEGER DEFAULT 1')
            
            # Check and add columns to sections
            add_column_if_missing('sections', 'module_id', 'INTEGER')
            
            # Check and add columns to users
            add_column_if_missing('users', 'profile_image', 'VARCHAR(255)')
            add_column_if_missing('users', 'bio', 'TEXT')
            add_column_if_missing('users', 'contact', 'VARCHAR(120)')
            add_column_if_missing('users', 'first_name', 'VARCHAR(80)')
            add_column_if_missing('users', 'last_name', 'VARCHAR(80)')
            add_column_if_missing('users', 'specialization', 'VARCHAR(200)')
            
            # Adjust specific postgres columns
            if db.engine.name == 'postgresql':
                db.session.execute(text("ALTER TABLE assignment_submissions ALTER COLUMN file_path TYPE TEXT;"))
                db.session.execute(text("ALTER TABLE assignment_submissions ALTER COLUMN submission_text DROP NOT NULL;"))
                db.session.execute(text("ALTER TABLE quiz_questions ALTER COLUMN question_text TYPE TEXT;"))
                db.session.execute(text("ALTER TABLE quiz_questions ALTER COLUMN option_a TYPE TEXT;"))
                db.session.execute(text("ALTER TABLE quiz_questions ALTER COLUMN option_b TYPE TEXT;"))
                db.session.execute(text("ALTER TABLE quiz_questions ALTER COLUMN option_c TYPE TEXT;"))
                db.session.execute(text("ALTER TABLE quiz_questions ALTER COLUMN option_d TYPE TEXT;"))
                
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Startup DB self-healing error: {e}")

    # Define login_manager.user_loader here to avoid circular imports
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 10-Minute Server-Side Inactivity Lockout Check
    @app.before_request
    def check_session_inactivity():
        try:
            from flask import session, request, redirect, url_for, flash
            from flask_login import current_user, logout_user
            from datetime import datetime, timezone

            # Skip static assets and public auth endpoints
            if request.endpoint and (request.endpoint.startswith('static') or request.endpoint in ('auth.login', 'auth.logout', 'auth.forgot_password', 'auth.ping_session', 'health.health_check')):
                return

            if current_user and current_user.is_authenticated:
                session.permanent = True
                now_ts = datetime.now(timezone.utc).timestamp()
                last_activity = session.get('last_activity')

                # 9 hours = 32400 seconds
                if last_activity:
                    try:
                        if (now_ts - float(last_activity)) > 32400:
                            logout_user()
                            session.pop('last_activity', None)
                            flash('Your session has expired due to 9 hours of inactivity. Please log in again.', 'warning')
                            return redirect(url_for('auth.login'))
                    except (ValueError, TypeError):
                        pass

                # Refresh last activity timestamp
                session['last_activity'] = now_ts
        except Exception as err:
            app.logger.warning(f"Inactivity check hook notice: {err}")
    
    # Context processor for sidebar counts
    @app.context_processor
    def inject_sidebar_counts():
        from flask_login import current_user
        from app.models import Assignment, AssignmentSubmission, Enrollment, Section, Announcement, Notification
        from datetime import datetime
        
        if current_user and current_user.is_authenticated and current_user.role == 'student':
            try:
                # Get enrolled course IDs
                enrolled_course_ids = [e.course_id for e in Enrollment.query.filter_by(student_id=current_user.id).all()]
                
                # Count pending assignments (not submitted)
                all_assignments = Assignment.query.join(Section).filter(
                    Section.course_id.in_(enrolled_course_ids) if enrolled_course_ids else False
                ).all()
                
                pending_assignments = 0
                for assignment in all_assignments:
                    submission = AssignmentSubmission.query.filter_by(
                        assignment_id=assignment.id,
                        student_id=current_user.id
                    ).first()
                    if not submission:
                        pending_assignments += 1
                
                # Count unread announcements (last 7 days as "new")
                from datetime import timedelta
                week_ago = datetime.utcnow() - timedelta(days=7)
                unread_announcements = Announcement.query.filter(
                    Announcement.course_id.in_(enrolled_course_ids) if enrolled_course_ids else False,
                    Announcement.created_at >= week_ago
                ).count()
                
                # Count unread notifications
                unread_notifications = Notification.query.filter_by(
                    user_id=current_user.id,
                    read=False
                ).count() if hasattr(Notification, 'read') else 0
                
                # Count completed courses
                completed_courses = Enrollment.query.filter_by(
                    student_id=current_user.id,
                    completed=True
                ).count()

                # Active or upcoming live sessions for enrolled courses
                from app.models import LiveSession
                from datetime import datetime, timedelta
                
                # Auto-expire stale live sessions whose duration has passed
                now = datetime.utcnow()
                stale_sessions = LiveSession.query.filter_by(status='live').all()
                for s in stale_sessions:
                    start_ref = s.started_at or s.scheduled_at
                    if start_ref and now > (start_ref + timedelta(minutes=s.duration_minutes or 60)):
                        s.status = 'ended'
                        s.ended_at = now
                db.session.commit()

                active_live_session = LiveSession.query.filter(
                    LiveSession.course_id.in_(enrolled_course_ids) if enrolled_course_ids else False,
                    LiveSession.status == 'live'
                ).first()
                
                return {
                    'sidebar_counts': {
                        'pending_assignments': pending_assignments,
                        'unread_announcements': unread_announcements,
                        'unread_notifications': unread_notifications,
                        'completed_courses': completed_courses,
                        'has_active_live': active_live_session is not None,
                        'active_live_session': active_live_session
                    }
                }
            except Exception as e:
                # Fallback to zero counts if there's an error
                return {
                    'sidebar_counts': {
                        'pending_assignments': 0,
                        'unread_announcements': 0,
                        'unread_notifications': 0,
                        'completed_courses': 0
                    }
                }
        return {
            'sidebar_counts': {
                'pending_assignments': 0,
                'unread_announcements': 0,
                'unread_notifications': 0,
                'completed_courses': 0
            }
        }

    # Import decorators after app initialization
    from .decorators import student_required, teacher_required

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.teacher import teacher_bp
    from app.routes.student import student_bp
    from app.routes.notifications import notifications_bp
    from app.routes.code_execution import code_execution_bp
    from app.routes.importer import importer_bp
    from app.routes.health import health_bp
    from app.routes.forum import forum_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(code_execution_bp)
    app.register_blueprint(importer_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(forum_bp)

    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Context processor to override url_for for Cloudinary URLs
    from flask import url_for as flask_url_for
    @app.context_processor
    def override_url_for():
        def custom_url_for(endpoint, **values):
            if endpoint == 'static' and values.get('filename', '').startswith('uploads/http'):
                return values['filename'].replace('uploads/', '', 1)
            if endpoint in ('teacher.media', 'admin.serve_pdf') and values.get('filename', '').startswith('http'):
                return values['filename']
            return flask_url_for(endpoint, **values)
        return dict(url_for=custom_url_for)

    # CLI Commands
    @app.cli.command('send-inactivity-nudges')
    def cli_send_inactivity_nudges():
        """Find inactive learners (7+ days) and dispatch personalized progress nudge emails."""
        from app.utils.nudge import send_inactivity_nudges
        import click
        click.echo("Scanning for inactive learners...")
        res = send_inactivity_nudges(app)
        click.echo(f"Done! {res['nudges_sent']} nudge email(s) sent out of {res['total_candidates']} candidate(s).")

    return app

