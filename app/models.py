from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from datetime import datetime
from flask_login import UserMixin
import hashlib
import os

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        # Force use of PBKDF2-SHA256 which is universally available
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    
    

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


from datetime import datetime

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    youtube_url = db.Column(db.String(255))
    status = db.Column(db.String(20), default='draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_feedback = db.Column(db.Text)
    pdf_filename = db.Column(db.String(120))
    
    teacher = db.relationship('User', backref='courses')
    sections = db.relationship('Section', 
                             back_populates='course',
                             order_by='Section.order',
                             cascade='all, delete-orphan')

    
    # Add after your existing Course model
class Section(db.Model):
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    section_type = db.Column(db.String(20), default='text')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False)

    course = db.relationship('Course', back_populates='sections')
class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)
    
    # Relationships
    student = db.relationship('User', backref='enrollments')
    course = db.relationship('Course', backref='course_enrollments')
    sections = db.relationship('EnrollmentSection', backref='enrollment', cascade='all, delete-orphan')

class EnrollmentSection(db.Model):
    __tablename__ = 'enrollment_sections'
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    section = db.relationship('Section', backref='enrollment_sections')