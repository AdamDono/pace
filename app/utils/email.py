import os
from flask import current_app, render_template
from flask_mail import Message
from app import mail
from threading import Thread
import logging

logger = logging.getLogger(__name__)

def send_async_email(app, msg):
    """Send email asynchronously (SMTP with HTTPS Web API fallback)"""
    with app.app_context():
        # Check if an HTTPS API Key is configured to bypass blocked SMTP ports on Render Free Tier
        sendgrid_key = os.getenv('SENDGRID_API_KEY')
        resend_key = os.getenv('RESEND_API_KEY')
        brevo_key = os.getenv('BREVO_API_KEY')
        
        if sendgrid_key:
            try:
                import urllib.request
                import json
                
                url = "https://api.sendgrid.com/v3/mail/send"
                headers = {
                    "Authorization": f"Bearer {sendgrid_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "personalizations": [{
                        "to": [{"email": r} for r in msg.recipients],
                        "subject": msg.subject
                    }],
                    "from": {"email": msg.sender or app.config['MAIL_DEFAULT_SENDER']},
                    "content": [{
                        "type": "text/html",
                        "value": msg.html
                    }]
                }
                
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(payload).encode('utf-8'), 
                    headers=headers, 
                    method='POST'
                )
                with urllib.request.urlopen(req) as response:
                    if response.status in [200, 202]:
                        logger.info(f"Email sent successfully via SendGrid HTTP API to {msg.recipients}")
                        return
                    else:
                        raise Exception(f"SendGrid API returned status {response.status}")
            except Exception as api_err:
                logger.error(f"SendGrid HTTP API failed: {str(api_err)}. Falling back to SMTP...")

        elif resend_key:
            try:
                import urllib.request
                import json
                
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "from": msg.sender or app.config['MAIL_DEFAULT_SENDER'],
                    "to": msg.recipients,
                    "subject": msg.subject,
                    "html": msg.html
                }
                
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(payload).encode('utf-8'), 
                    headers=headers, 
                    method='POST'
                )
                with urllib.request.urlopen(req) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Email sent successfully via Resend HTTP API to {msg.recipients}")
                        return
                    else:
                        raise Exception(f"Resend API returned status {response.status}")
            except Exception as api_err:
                logger.error(f"Resend HTTP API failed: {str(api_err)}. Falling back to SMTP...")

        elif brevo_key:
            try:
                import urllib.request
                import json
                
                url = "https://api.brevo.com/v3/smtp/email"
                headers = {
                    "api-key": brevo_key,
                    "Content-Type": "application/json"
                }
                
                sender_email = msg.sender or app.config['MAIL_DEFAULT_SENDER']
                sender_name = "Pace Academy"
                if "<" in sender_email:
                    parts = sender_email.split("<")
                    sender_name = parts[0].strip()
                    sender_email = parts[1].replace(">", "").strip()
                    
                payload = {
                    "sender": {"email": sender_email, "name": sender_name},
                    "to": [{"email": r} for r in msg.recipients],
                    "subject": msg.subject,
                    "htmlContent": msg.html
                }
                
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(payload).encode('utf-8'), 
                    headers=headers, 
                    method='POST'
                )
                with urllib.request.urlopen(req) as response:
                    if response.status in [200, 201, 202]:
                        logger.info(f"Email sent successfully via Brevo HTTP API to {msg.recipients}")
                        return
                    else:
                        raise Exception(f"Brevo API returned status {response.status}")
            except Exception as api_err:
                logger.error(f"Brevo HTTP API failed: {str(api_err)}. Falling back to SMTP...")
        else:
            logger.warning("No HTTP email API keys (SendGrid, Resend, or Brevo) configured. Falling back to SMTP (which may be blocked by cloud host providers).")

        # Standard SMTP fallback
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

def send_suspension_email(user, reason, suspended_until=None):
    """Notify user when their account is suspended"""
    from datetime import datetime
    if suspended_until:
        duration_text = f"until {suspended_until.strftime('%B %d, %Y at %I:%M %p')}"
    else:
        duration_text = "indefinitely"
    
    return send_email(
        subject='Your Pace Academy account has been suspended',
        recipient=user.email,
        template='suspension',
        user=user,
        reason=reason,
        duration_text=duration_text,
        suspended_until=suspended_until,
        support_email=current_app.config.get('MAIL_DEFAULT_SENDER', 'support@paceacademy.com')
    )

def send_ban_email(user, reason):
    """Notify user when their account is permanently banned"""
    return send_email(
        subject='Your Pace Academy account has been banned',
        recipient=user.email,
        template='ban',
        user=user,
        reason=reason,
        support_email=current_app.config.get('MAIL_DEFAULT_SENDER', 'support@paceacademy.com')
    )

def send_unsuspension_email(user):
    """Notify user when their suspension is lifted"""
    return send_email(
        subject='Your Pace Academy account has been restored',
        recipient=user.email,
        template='unsuspension',
        user=user,
        login_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + '/login'
    )

def send_unban_email(user):
    """Notify user when their ban is lifted"""
    return send_email(
        subject='Your Pace Academy account has been restored',
        recipient=user.email,
        template='unban',
        user=user,
        login_url=current_app.config.get('BASE_URL', 'http://localhost:5000') + '/login'
    )
