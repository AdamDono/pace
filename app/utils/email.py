from flask import current_app, render_template
from flask_mail import Message
from app import mail
from threading import Thread
import logging

logger = logging.getLogger(__name__)

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            mail.send(msg)
            logger.info(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            logger.error(f"Failed to send email to {msg.recipients}: {str(e)}")

def send_email(subject, recipient, template, **kwargs):
    """
    Send email with HTML template
    
    Args:
        subject: Email subject
        recipient: Recipient email address
        template: Path to email template (without .html)
        **kwargs: Additional context variables for template
    """
    try:
        msg = Message(
            subject,
            recipients=[recipient],
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Render HTML template
        msg.html = render_template(f'emails/{template}.html', **kwargs)
        
        # Send asynchronously
        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg)
        ).start()
        
        logger.info(f"Email queued for {recipient}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to queue email for {recipient}: {str(e)}")
        return False

def send_welcome_email(user, password):
    """Send welcome email to new user with login credentials"""
    return send_email(
        subject='Welcome to Pace Academy!',
        recipient=user.email,
        template='welcome',
        user=user,
        password=password,
        login_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + '/login'
    )

def send_enrollment_email(student, course):
    """Send enrollment notification to student"""
    return send_email(
        subject=f'You\'ve been enrolled in {course.title}',
        recipient=student.email,
        template='enrollment',
        student=student,
        course=course,
        course_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + f'/student/course/{course.id}'
    )

def send_course_approved_email(teacher, course):
    """Notify teacher when their course is approved"""
    return send_email(
        subject=f'Your course "{course.title}" has been approved!',
        recipient=teacher.email,
        template='course_approved',
        teacher=teacher,
        course=course,
        course_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + f'/teacher/course/{course.id}/manage-sections'
    )

def send_course_rejected_email(teacher, course, feedback):
    """Notify teacher when their course is rejected"""
    return send_email(
        subject=f'Your course "{course.title}" needs revision',
        recipient=teacher.email,
        template='course_rejected',
        teacher=teacher,
        course=course,
        feedback=feedback,
        edit_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + f'/teacher/edit-course/{course.id}'
    )
