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

    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///default.db')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configure uploads
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
    app.config['WTF_CSRF_ENABLED'] = True  # Enabled for security
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Do not expire CSRF tokens during session
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx'}  # Updated to match forms

    # Configure email
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@paceacademy.com')

    # Configure session
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)

    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Add this line
    mail.init_app(app)
    login_manager.login_view = 'auth.login'

    # Define login_manager.user_loader here to avoid circular imports
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Context processor for sidebar counts
    @app.context_processor
    def inject_sidebar_counts():
        from flask_login import current_user
        from app.models import Assignment, AssignmentSubmission, Enrollment, Section, Announcement, Notification
        from datetime import datetime
        
        if current_user.is_authenticated and current_user.role == 'student':
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
                
                return {
                    'sidebar_counts': {
                        'pending_assignments': pending_assignments,
                        'unread_announcements': unread_announcements,
                        'unread_notifications': unread_notifications,
                        'completed_courses': completed_courses
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(code_execution_bp)
    app.register_blueprint(importer_bp)

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

    return app

