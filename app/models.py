from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
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
        # Fallback to pbkdf2 if scrypt not available
        if hasattr(hashlib, 'scrypt'):
            self.password_hash = generate_password_hash(password)
        else:
            salt = os.urandom(16).hex()
            self.password_hash = f"pbkdf2:sha256:150000${salt}${hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 150000).hex()}"

    def verify_password(self, password):
        if self.password_hash.startswith('pbkdf2:'):
            # Handle our custom hash
            _, algo, iterations, salt, hashval = self.password_hash.split('$')
            return hashval == hashlib.pbkdf2_hmac(algo.split(':')[1], password.encode('utf-8'), salt.encode('utf-8'), int(iterations)).hex()
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))