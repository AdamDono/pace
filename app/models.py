from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from datetime import datetime
from flask_login import UserMixin

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    courses_taught = db.relationship('Course', backref='teacher', lazy=True)
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Course(db.Model):
    __tablename__ = 'courses'
    
    STATUSES = ['draft', 'pending', 'approved', 'rejected']
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    youtube_url = db.Column(db.String(255))
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    admin_feedback = db.Column(db.Text)
    pdf_filename = db.Column(db.String(120))
    thumbnail_url = db.Column(db.String(255))

    # Relationships
    sections = db.relationship('Section', 
                             back_populates='course',
                             order_by='Section.order',
                             cascade='all, delete-orphan')
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)

class Section(db.Model):
    __tablename__ = 'sections'
    
    SECTION_TYPES = ['text', 'pdf', 'video', 'quiz']
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    section_type = db.Column(db.String(20), default='text')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False)
    duration_minutes = db.Column(db.Integer, default=0)

    # Relationships
    course = db.relationship('Course', back_populates='sections')
    completion_records = db.relationship('EnrollmentSection', back_populates='section')

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)
    progress = db.Column(db.Float, default=0.0)

    # Relationships
    section_completions = db.relationship('EnrollmentSection', backref='enrollment', cascade='all, delete-orphan')

class EnrollmentSection(db.Model):
    __tablename__ = 'enrollment_sections'
    
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, default=0)
    last_attempt_at = db.Column(db.DateTime)

    # Relationships
    section = db.relationship('Section', back_populates='completion_records')