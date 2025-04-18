from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, StringField, validators

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
    
    class CourseForm(FlaskForm):
     title = StringField('Title', validators=[
        validators.DataRequired(),
        validators.Length(min=5, max=100)
    ])
    description = TextAreaField('Description', validators=[
        validators.DataRequired(),
        validators.Length(min=10)
    ])
    youtube_url = StringField('YouTube Video URL', validators=[
        validators.Optional(),
        validators.URL()
    ])
    pdf_upload = FileField('PDF Material', validators=[
        FileAllowed(['pdf'], 'Only PDF files allowed!')
    ])