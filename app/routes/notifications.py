"""
Notification routes
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Notification, NotificationPreference, Announcement, Course, Enrollment, db
from app.utils.notifications import NotificationService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def list_notifications():
    """List all notifications for current user"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('notifications/list.html', notifications=notifications)

@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    """Get unread notification count (AJAX)"""
    count = NotificationService.get_unread_count(current_user.id)
    return jsonify({'count': count})

@notifications_bp.route('/recent')
@login_required
def recent_notifications():
    """Get recent notifications (AJAX for dropdown)"""
    limit = request.args.get('limit', 10, type=int)
    notifications = NotificationService.get_recent_notifications(current_user.id, limit)
    
    notifications_data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'link_url': n.link_url,
        'read': n.read,
        'priority': n.priority,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
        'notification_type': n.notification_type
    } for n in notifications]
    
    return jsonify({
        'notifications': notifications_data,
        'unread_count': NotificationService.get_unread_count(current_user.id)
    })

@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """Mark notification as read"""
    success = NotificationService.mark_as_read(notification_id, current_user.id)
    return jsonify({'success': success})

@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read"""
    success = NotificationService.mark_all_as_read(current_user.id)
    return jsonify({'success': success})

@notifications_bp.route('/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    success = NotificationService.delete_notification(notification_id, current_user.id)
    return jsonify({'success': success})

@notifications_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    """Manage notification preferences"""
    prefs = NotificationPreference.query.filter_by(user_id=current_user.id).first()
    
    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
    
    if request.method == 'POST':
        # Update preferences
        prefs.email_assignment_feedback = 'email_assignment_feedback' in request.form
        prefs.email_quiz_graded = 'email_quiz_graded' in request.form
        prefs.email_course_announcement = 'email_course_announcement' in request.form
        prefs.email_course_completion = 'email_course_completion' in request.form
        prefs.email_certificate_ready = 'email_certificate_ready' in request.form
        prefs.email_new_course_content = 'email_new_course_content' in request.form
        prefs.email_assignment_due_soon = 'email_assignment_due_soon' in request.form
        
        prefs.inapp_assignment_feedback = 'inapp_assignment_feedback' in request.form
        prefs.inapp_quiz_graded = 'inapp_quiz_graded' in request.form
        prefs.inapp_course_announcement = 'inapp_course_announcement' in request.form
        prefs.inapp_course_completion = 'inapp_course_completion' in request.form
        prefs.inapp_certificate_ready = 'inapp_certificate_ready' in request.form
        prefs.inapp_new_course_content = 'inapp_new_course_content' in request.form
        
        prefs.weekly_digest = 'weekly_digest' in request.form
        prefs.digest_day = request.form.get('digest_day', 'Monday')
        
        db.session.commit()
        flash('Notification preferences updated successfully!', 'success')
        return redirect(url_for('notifications.preferences'))
    
    return render_template('notifications/preferences.html', prefs=prefs)

# ===== ANNOUNCEMENT ROUTES (for teachers) =====

@notifications_bp.route('/announcements/create/<int:course_id>', methods=['GET', 'POST'])
@login_required
def create_announcement(course_id):
    """Create course announcement (teacher only)"""
    course = Course.query.get_or_404(course_id)
    
    # Verify teacher owns course
    if course.teacher_id != current_user.id:
        flash('You do not have permission to create announcements for this course.', 'error')
        return redirect(url_for('teacher.my_courses'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        send_email = 'send_email' in request.form
        pinned = 'pinned' in request.form
        
        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('notifications.create_announcement', course_id=course_id))
        
        # Create announcement
        announcement = Announcement(
            course_id=course_id,
            teacher_id=current_user.id,
            title=title,
            content=content,
            send_email=send_email,
            pinned=pinned
        )
        db.session.add(announcement)
        db.session.commit()
        
        # Send notifications to all enrolled students
        enrollments = Enrollment.query.filter_by(course_id=course_id).all()
        for enrollment in enrollments:
            NotificationService.create_notification(
                user_id=enrollment.student_id,
                notification_type='course_announcement',
                title=f'New announcement in {course.title}',
                message=f'{title}: {content[:100]}...' if len(content) > 100 else content,
                link_url=url_for('notifications.view_announcements', course_id=course_id),
                related_course_id=course_id,
                send_email=send_email
            )
        
        flash(f'Announcement created and sent to {len(enrollments)} students!', 'success')
        return redirect(url_for('teacher.manage_modules', course_id=course_id))
    
    return render_template('notifications/create_announcement.html', course=course)

@notifications_bp.route('/announcements/<int:course_id>')
@login_required
def view_announcements(course_id):
    """View course announcements"""
    course = Course.query.get_or_404(course_id)
    
    # Check if user is enrolled or is the teacher
    if current_user.role == 'student':
        enrollment = Enrollment.query.filter_by(
            student_id=current_user.id,
            course_id=course_id
        ).first()
        if not enrollment:
            flash('You are not enrolled in this course.', 'error')
            return redirect(url_for('student.dashboard'))
    elif current_user.role == 'teacher' and course.teacher_id != current_user.id:
        flash('You do not have access to this course.', 'error')
        return redirect(url_for('teacher.my_courses'))
    
    announcements = Announcement.query.filter_by(
        course_id=course_id
    ).order_by(Announcement.pinned.desc(), Announcement.created_at.desc()).all()
    
    return render_template('notifications/announcements.html', 
                         course=course, 
                         announcements=announcements)

@notifications_bp.route('/announcements/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_announcement(announcement_id):
    """Edit announcement (teacher only)"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    # Verify teacher owns the announcement
    if announcement.teacher_id != current_user.id:
        flash('You do not have permission to edit this announcement.', 'error')
        return redirect(url_for('teacher.my_courses'))
    
    if request.method == 'POST':
        announcement.title = request.form.get('title')
        announcement.content = request.form.get('content')
        announcement.pinned = 'pinned' in request.form
        announcement.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Announcement updated successfully!', 'success')
        return redirect(url_for('notifications.view_announcements', course_id=announcement.course_id))
    
    return render_template('notifications/edit_announcement.html', announcement=announcement)

@notifications_bp.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
def delete_announcement(announcement_id):
    """Delete announcement (teacher only)"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    # Verify teacher owns the announcement
    if announcement.teacher_id != current_user.id:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    course_id = announcement.course_id
    db.session.delete(announcement)
    db.session.commit()
    
    return jsonify({'success': True, 'redirect': url_for('notifications.view_announcements', course_id=course_id)})
