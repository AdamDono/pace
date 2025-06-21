# app/utils.py
from flask import render_template, current_app
from flask_mail import Message
from app import mail

def send_email(to, subject, template, **kwargs):
    msg = Message(
        subject,
        recipients=[to],
        sender=current_app.config['MAIL_USERNAME']
    )
    msg.html = render_template(template, **kwargs)
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}") 