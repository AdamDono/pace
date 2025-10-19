"""
Notification Service - Handles creating and sending notifications
"""

from app.models import Notification, NotificationPreference, User, db
from app.utils.email import send_email
from flask import url_for, render_template_string
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for creating and sending notifications
    
    Usage:
        NotificationService.create_notification(
            user_id=123,
            notification_type='assignment_feedback',
            title='Assignment Graded',
            message='Your assignment has been graded',
            link_url='/student/course/1',
            send_email=True
        )
    """
    
    NOTIFICATION_TYPES = {
        'assignment_feedback': {
            'email_pref': 'email_assignment_feedback',
            'inapp_pref': 'inapp_assignment_feedback',
            'email_subject': 'Assignment Feedback Received',
        },
        'quiz_graded': {
            'email_pref': 'email_quiz_graded',
            'inapp_pref': 'inapp_quiz_graded',
            'email_subject': 'Quiz Graded',
        },
        'course_announcement': {
            'email_pref': 'email_course_announcement',
            'inapp_pref': 'inapp_course_announcement',
            'email_subject': 'New Course Announcement',
        },
        'course_completion': {
            'email_pref': 'email_course_completion',
            'inapp_pref': 'inapp_course_completion',
            'email_subject': 'Course Completed!',
        },
        'certificate_ready': {
            'email_pref': 'email_certificate_ready',
            'inapp_pref': 'inapp_certificate_ready',
            'email_subject': 'Your Certificate is Ready',
        },
        'new_course_content': {
            'email_pref': 'email_new_course_content',
            'inapp_pref': 'inapp_new_course_content',
            'email_subject': 'New Course Content Available',
        },
        'assignment_due_soon': {
            'email_pref': 'email_assignment_due_soon',
            'inapp_pref': None,  # No in-app for due reminders
            'email_subject': 'Assignment Due Soon',
        },
    }
    
    @staticmethod
    def create_notification(user_id, notification_type, title, message, 
                          link_url=None, priority='normal', 
                          related_course_id=None, related_assignment_id=None, 
                          related_quiz_id=None, send_email=True):
        """
        Create a notification and optionally send email
        
        Args:
            user_id: ID of user to notify
            notification_type: Type of notification (see NOTIFICATION_TYPES)
            title: Notification title
            message: Notification message
            link_url: Optional URL to relevant page
            priority: 'low', 'normal', 'high', 'urgent'
            related_course_id: Optional related course ID
            related_assignment_id: Optional related assignment ID
            related_quiz_id: Optional related quiz ID
            send_email: Whether to send email notification
        """
        try:
            user = User.query.get(user_id)
            if not user:
                logger.error(f"User {user_id} not found for notification")
                return None
            
            # Get user preferences
            prefs = NotificationPreference.query.filter_by(user_id=user_id).first()
            if not prefs:
                # Create default preferences
                prefs = NotificationPreference(user_id=user_id)
                db.session.add(prefs)
                db.session.commit()
            
            # Check if notification type exists
            if notification_type not in NotificationService.NOTIFICATION_TYPES:
                logger.error(f"Invalid notification type: {notification_type}")
                return None
            
            type_config = NotificationService.NOTIFICATION_TYPES[notification_type]
            
            # Check in-app preference
            inapp_pref = type_config.get('inapp_pref')
            if inapp_pref and hasattr(prefs, inapp_pref):
                if not getattr(prefs, inapp_pref):
                    logger.info(f"In-app notification {notification_type} disabled for user {user_id}")
                    send_email = False  # Also don't send email if in-app is disabled
            
            # Create in-app notification if user wants them
            notification = None
            if inapp_pref is None or getattr(prefs, inapp_pref, True):
                notification = Notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    link_url=link_url,
                    priority=priority,
                    related_course_id=related_course_id,
                    related_assignment_id=related_assignment_id,
                    related_quiz_id=related_quiz_id
                )
                db.session.add(notification)
                db.session.commit()
                logger.info(f"Created notification {notification.id} for user {user_id}")
            
            # Send email if requested and user preference allows
            email_pref = type_config.get('email_pref')
            if send_email and email_pref and hasattr(prefs, email_pref):
                if getattr(prefs, email_pref):
                    NotificationService.send_notification_email(
                        user=user,
                        subject=type_config['email_subject'],
                        title=title,
                        message=message,
                        link_url=link_url,
                        notification=notification
                    )
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def send_notification_email(user, subject, title, message, link_url=None, notification=None):
        """Send email notification"""
        try:
            # Generate email HTML
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                              color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .message {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; 
                               border-left: 4px solid #667eea; }}
                    .button {{ display: inline-block; padding: 12px 30px; background: #667eea; 
                              color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; color: #777; font-size: 12px; margin-top: 30px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔔 {{ title }}</h1>
                    </div>
                    <div class="content">
                        <p>Hi {{ user_name }},</p>
                        <div class="message">
                            <p>{{ message }}</p>
                        </div>
                        {% if link_url %}
                        <a href="{{ link_url }}" class="button">View Details →</a>
                        {% endif %}
                        <div class="footer">
                            <p>You received this email because you are enrolled in our learning platform.</p>
                            <p>To manage your notification preferences, visit your profile settings.</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_body = render_template_string(
                html_template,
                title=title,
                user_name=user.username,
                message=message,
                link_url=link_url
            )
            
            # Send email
            send_email(
                subject=subject,
                recipients=[user.email],
                html_body=html_body
            )
            
            # Mark notification as emailed
            if notification:
                notification.emailed = True
                db.session.commit()
            
            logger.info(f"Sent email notification to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification email: {str(e)}")
            return False
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Mark a notification as read"""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                user_id=user_id
            ).first()
            
            if notification:
                notification.read = True
                notification.read_at = datetime.utcnow()
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            return False
    
    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        try:
            Notification.query.filter_by(
                user_id=user_id,
                read=False
            ).update({'read': True, 'read_at': datetime.utcnow()})
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {str(e)}")
            return False
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications"""
        try:
            return Notification.query.filter_by(
                user_id=user_id,
                read=False
            ).count()
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0
    
    @staticmethod
    def get_recent_notifications(user_id, limit=10):
        """Get recent notifications for a user"""
        try:
            return Notification.query.filter_by(
                user_id=user_id
            ).order_by(Notification.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent notifications: {str(e)}")
            return []
    
    @staticmethod
    def delete_notification(notification_id, user_id):
        """Delete a notification"""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                user_id=user_id
            ).first()
            
            if notification:
                db.session.delete(notification)
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}")
            return False
