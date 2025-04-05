from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user
from app.models import User
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))  # Change to your dashboard route
    return render_template('auth/login.html')

@auth_bp.route('/register')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))  # Change to your dashboard route
    return render_template('auth/register.html')