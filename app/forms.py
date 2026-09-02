from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SelectField, BooleanField, TextAreaField, IntegerField, DateTimeField, FieldList, FormField, SubmitField
from werkzeug.utils import secure_filename
from wtforms.validators import DataRequired, Email, EqualTo, Length, URL, Optional

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
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
    submit = SubmitField('Submit for Approval')  # Added to match the template

class AssignmentForm(FlaskForm):
    title = StringField('Assignment Title', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Length(max=50000), Optional()])
    due_date = DateTimeField('Due Date', format='%Y-%m-%dT%H:%M', validators=[Optional()])

class QuestionForm(FlaskForm):
    question = StringField('Question', validators=[DataRequired(), Length(max=10000)])
    a = StringField('Option A', validators=[DataRequired(), Length(max=10000)])
    b = StringField('Option B', validators=[DataRequired(), Length(max=10000)])
    c = StringField('Option C', validators=[Length(max=10000), Optional()])
    d = StringField('Option D', validators=[Length(max=10000), Optional()])
    correct = SelectField('Correct Answer', choices=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')], validators=[DataRequired()])

class QuizForm(FlaskForm):
    title = StringField('Quiz Title', validators=[DataRequired(), Length(max=100)])
    questions = FieldList(FormField(QuestionForm), min_entries=1, max_entries=10)
    submit = SubmitField('Create Quiz')

class SubmissionForm(FlaskForm):
    submission_text = TextAreaField('Your Submission', validators=[Optional(), Length(max=50000)])

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    bio = TextAreaField('Bio/About', validators=[Optional(), Length(max=500)])
    contact = StringField('Contact Information', validators=[Optional(), Length(max=120)])
    first_name = StringField('First Name', validators=[Optional(), Length(max=80)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=80)])
    id_number = StringField('National ID / Passport Number', validators=[Optional(), Length(max=30)])
    specialization = StringField('Specialization / Area of Interest', validators=[Optional(), Length(max=200)])
    current_password = PasswordField('Current Password (only needed when changing password)', validators=[Optional()])
    new_password = PasswordField('New Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Update Profile')