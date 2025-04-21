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
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    youtube_url = db.Column(db.String(255))
    status = db.Column(db.String(20), default='draft')  # draft/pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_feedback = db.Column(db.Text)  # For rejection comments
    pdf_filename = db.Column(db.String(120))  # Add this line
    teacher = db.relationship('User', backref='courses')
    
    def __repr__(self):
        return f'<Course {self.title}>'