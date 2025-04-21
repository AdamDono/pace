from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SelectField, BooleanField, TextAreaField
from werkzeug.utils import secure_filename
from wtforms.validators import DataRequired, Email, EqualTo, Length, URL, Optional
import uuid

# Existing Auth Forms (keep these)
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6),
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password')
    role = SelectField('Role', choices=[
        ('student', 'Student'), 
        ('teacher', 'Teacher'),
        ('admin', 'Admin')
    ], validators=[DataRequired()])

# Add the CourseForm (new)
class CourseForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(),
        Length(min=5, max=100)
    ])
    description = TextAreaField('Description', validators=[
        DataRequired(),
        Length(min=10)
    ])
    youtube_url = StringField('YouTube Video URL', validators=[
        Optional(),
        URL(message='Enter a valid URL')
    ])
    pdf_upload = FileField('PDF Material', validators=[
        FileAllowed(['pdf'], 'Only PDF files allowed!')
    ])
    
    class CourseForm(FlaskForm):
     title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    youtube_url = StringField('YouTube URL', validators=[Optional(), URL()])
    pdf_upload = FileField('PDF File', validators=[
        FileAllowed(['pdf'], 'Only PDF files allowed!')
    ])