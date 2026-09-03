import os
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, func
from app import db
from app.models import Course, Section, Enrollment, User, ForumThread, ForumReply, ForumUpvote, Notification
from app.utils.email import send_email

logger = logging.getLogger(__name__)

forum_bp = Blueprint('forum', __name__)

def check_course_access(course):
    """Verify that current_user has access to participate in course forum"""
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    if current_user.role == 'teacher' and current_user.is_teacher_for_course(course.id):
        return True
    # Student check: must be enrolled and not blocked
    enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if enrollment and not enrollment.is_blocked:
        return True
    return False


@forum_bp.route('/course/<int:course_id>/forum', methods=['GET'])
@login_required
def course_forum(course_id):
    """Main forum list endpoint supporting search, filter, and lesson tagging"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        abort(403)

    filter_mode = request.args.get('filter', 'all')  # 'all', 'unanswered', 'instructor', 'popular', 'this_lesson'
    section_id = request.args.get('section_id', type=int)
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = ForumThread.query.filter_by(course_id=course_id)

    # Search keyword filter
    if search_query:
        query = query.filter(
            or_(
                ForumThread.title.ilike(f'%{search_query}%'),
                ForumThread.content.ilike(f'%{search_query}%')
            )
        )

    # Specific lesson filter
    if section_id:
        query = query.filter(ForumThread.section_id == section_id)
    elif filter_mode == 'this_lesson' and section_id:
        query = query.filter(ForumThread.section_id == section_id)

    # Filter tabs
    if filter_mode == 'unanswered':
        # Threads with 0 replies
        query = query.outerjoin(ForumReply).group_by(ForumThread.id).having(func.count(ForumReply.id) == 0)
    elif filter_mode == 'instructor':
        # Threads with instructor replies
        query = query.join(ForumReply).filter(ForumReply.is_instructor_reply == True).group_by(ForumThread.id)
    elif filter_mode == 'popular':
        # Sorted by upvotes
        query = query.outerjoin(ForumUpvote, (ForumUpvote.thread_id == ForumThread.id) & (ForumUpvote.reply_id == None)) \
                     .group_by(ForumThread.id) \
                     .order_by(desc(ForumThread.is_pinned), desc(func.count(ForumUpvote.id)), desc(ForumThread.created_at))
    else:
        # Default order: Pinned first, then latest
        query = query.order_by(desc(ForumThread.is_pinned), desc(ForumThread.created_at))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    threads = pagination.items

    active_section = Section.query.get(section_id) if section_id else None
    sections = Section.query.filter_by(course_id=course_id).order_by(Section.order).all()

    # If requested via HTMX or AJAX, return the list partial
    if request.headers.get('HX-Request') or request.args.get('partial'):
        return render_template(
            'forum/_thread_list.html',
            course=course,
            threads=threads,
            pagination=pagination,
            filter_mode=filter_mode,
            section_id=section_id,
            active_section=active_section,
            search_query=search_query
        )

    return render_template(
        'forum/forum_view.html',
        course=course,
        threads=threads,
        pagination=pagination,
        filter_mode=filter_mode,
        section_id=section_id,
        active_section=active_section,
        sections=sections,
        search_query=search_query
    )


@forum_bp.route('/course/<int:course_id>/forum/thread', methods=['POST'])
@login_required
def create_thread(course_id):
    """Create a new question or discussion thread in a course"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        abort(403)

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    section_id = request.form.get('section_id', type=int)

    if not title or not content:
        flash('Please provide both a title and description for your question.', 'danger')
        return redirect(request.referrer or url_for('forum.course_forum', course_id=course_id))

    # Verify section belongs to this course if specified
    if section_id:
        sec = Section.query.filter_by(id=section_id, course_id=course_id).first()
        if not sec:
            section_id = None

    thread = ForumThread(
        course_id=course_id,
        section_id=section_id,
        user_id=current_user.id,
        title=title,
        content=content
    )
    db.session.add(thread)
    db.session.commit()

    # Notify instructor about student's new question
    if current_user.role == 'student' and course.teacher_id:
        try:
            notif = Notification(
                user_id=course.teacher_id,
                notification_type='forum_new_question',
                title=f"New Q&A Question in {course.title}",
                message=f"{current_user.full_name or current_user.username} asked: '{title}'",
                link_url=url_for('forum.view_thread', course_id=course_id, thread_id=thread.id),
                related_course_id=course_id
            )
            db.session.add(notif)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to create instructor notification: {e}")

    flash('Your question has been posted to the course community!', 'success')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread.id))


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>', methods=['GET'])
@login_required
def view_thread(course_id, thread_id):
    """View discussion thread details, nested replies, and accepted solutions"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        abort(403)

    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()

    # Increment view count
    thread.views_count = (thread.views_count or 0) + 1
    db.session.commit()

    # Get top-level replies (parent_reply_id is None)
    top_level_replies = thread.replies.filter_by(parent_reply_id=None).order_by(
        desc(ForumReply.is_accepted_solution),
        desc(ForumReply.is_instructor_reply),
        ForumReply.created_at.asc()
    ).all()

    # If requested via HTMX or AJAX
    if request.headers.get('HX-Request') or request.args.get('partial'):
        return render_template(
            'forum/_thread_view.html',
            course=course,
            thread=thread,
            replies=top_level_replies
        )

    return render_template(
        'forum/thread_detail.html',
        course=course,
        thread=thread,
        replies=top_level_replies
    )


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>/reply', methods=['POST'])
@login_required
def add_reply(course_id, thread_id):
    """Add a reply or nested comment to a thread"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        abort(403)

    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()

    if thread.is_locked and current_user.role not in ('teacher', 'admin'):
        flash('This discussion thread has been locked by an instructor.', 'warning')
        return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread_id))

    content = request.form.get('content', '').strip()
    parent_reply_id = request.form.get('parent_reply_id', type=int)

    if not content:
        flash('Reply content cannot be empty.', 'danger')
        return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread_id))

    is_instructor = (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id))

    reply = ForumReply(
        thread_id=thread_id,
        user_id=current_user.id,
        parent_reply_id=parent_reply_id,
        content=content,
        is_instructor_reply=is_instructor
    )
    db.session.add(reply)
    db.session.commit()

    # 1. In-App Notification to Thread Author (if not replying to own thread)
    if thread.user_id != current_user.id:
        try:
            replier_name = current_user.first_name or current_user.full_name or current_user.username
            notif = Notification(
                user_id=thread.user_id,
                notification_type='forum_reply',
                title=f"New Reply from {replier_name}",
                message=f"{replier_name} replied to your question: '{thread.title}'",
                link_url=url_for('forum.view_thread', course_id=course_id, thread_id=thread.id),
                related_course_id=course_id
            )
            db.session.add(notif)
            db.session.commit()

            # Send Email Alert to Thread Author
            author = thread.author
            if author and author.email:
                discussion_url = url_for('forum.view_thread', course_id=course_id, thread_id=thread.id, _external=True)
                send_email(
                    subject=f"💬 New Reply on Your Question in {course.title} - Pace Academy",
                    recipient=author.email,
                    template='forum_reply',
                    recipient_name=author.first_name or author.username,
                    replier_name=replier_name,
                    is_instructor=is_instructor,
                    course=course,
                    thread=thread,
                    reply_snippet=content[:200] + ('...' if len(content) > 200 else ''),
                    discussion_url=discussion_url
                )
        except Exception as e:
            logger.error(f"Failed to dispatch forum reply notification: {e}")

    # 2. In-App Notification to Parent Reply Author (if nested reply)
    if parent_reply_id:
        parent_reply = ForumReply.query.get(parent_reply_id)
        if parent_reply and parent_reply.user_id not in (current_user.id, thread.user_id):
            try:
                notif_parent = Notification(
                    user_id=parent_reply.user_id,
                    notification_type='forum_nested_reply',
                    title=f"New Comment on Your Reply",
                    message=f"{current_user.full_name or current_user.username} commented on your reply in '{thread.title}'",
                    link_url=url_for('forum.view_thread', course_id=course_id, thread_id=thread.id),
                    related_course_id=course_id
                )
                db.session.add(notif_parent)
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to dispatch parent reply notification: {e}")

    flash('Your reply has been posted!', 'success')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread_id))


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>/upvote', methods=['POST'])
@login_required
def toggle_thread_upvote(course_id, thread_id):
    """Toggle upvote on a thread via AJAX"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()
    existing = ForumUpvote.query.filter_by(user_id=current_user.id, thread_id=thread_id, reply_id=None).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        upvoted = False
    else:
        new_upvote = ForumUpvote(user_id=current_user.id, thread_id=thread_id, reply_id=None)
        db.session.add(new_upvote)
        db.session.commit()
        upvoted = True

    return jsonify({
        'success': True,
        'upvoted': upvoted,
        'upvotes_count': thread.upvotes_count
    })


@forum_bp.route('/course/<int:course_id>/forum/reply/<int:reply_id>/upvote', methods=['POST'])
@login_required
def toggle_reply_upvote(course_id, reply_id):
    """Toggle upvote on a reply via AJAX"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    reply = ForumReply.query.get_or_404(reply_id)
    existing = ForumUpvote.query.filter_by(user_id=current_user.id, reply_id=reply_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        upvoted = False
    else:
        new_upvote = ForumUpvote(user_id=current_user.id, reply_id=reply_id)
        db.session.add(new_upvote)
        db.session.commit()
        upvoted = True

    return jsonify({
        'success': True,
        'upvoted': upvoted,
        'upvotes_count': reply.upvotes_count
    })


@forum_bp.route('/course/<int:course_id>/forum/reply/<int:reply_id>/accept', methods=['POST'])
@login_required
def toggle_accept_solution(course_id, reply_id):
    """Mark or unmark a reply as the accepted solution"""
    course = Course.query.get_or_404(course_id)
    if not check_course_access(course):
        abort(403)

    reply = ForumReply.query.get_or_404(reply_id)
    thread = reply.thread

    # Only thread author or instructor/admin can mark accepted solution
    is_teacher_admin = (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id))
    if thread.user_id != current_user.id and not is_teacher_admin:
        abort(403)

    # Toggle accepted state
    if reply.is_accepted_solution:
        reply.is_accepted_solution = False
        thread.is_resolved = False
    else:
        # Clear any other accepted solution on this thread
        for r in thread.replies:
            r.is_accepted_solution = False
        reply.is_accepted_solution = True
        thread.is_resolved = True

    db.session.commit()
    flash('Accepted solution status updated!', 'success')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread.id))


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>/pin', methods=['POST'])
@login_required
def toggle_pin_thread(course_id, thread_id):
    """Instructor/Admin moderation: Pin or unpin thread"""
    course = Course.query.get_or_404(course_id)
    if not (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id)):
        abort(403)

    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()
    thread.is_pinned = not thread.is_pinned
    db.session.commit()

    flash(f"Thread has been {'pinned to the top' if thread.is_pinned else 'unpinned'}.", 'info')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread.id))


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>/lock', methods=['POST'])
@login_required
def toggle_lock_thread(course_id, thread_id):
    """Instructor/Admin moderation: Lock or unlock thread comments"""
    course = Course.query.get_or_404(course_id)
    if not (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id)):
        abort(403)

    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()
    thread.is_locked = not thread.is_locked
    db.session.commit()

    flash(f"Thread has been {'locked' if thread.is_locked else 'unlocked for new replies'}.", 'info')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread.id))


@forum_bp.route('/course/<int:course_id>/forum/thread/<int:thread_id>/delete', methods=['POST'])
@login_required
def delete_thread(course_id, thread_id):
    """Delete thread (Author or Instructor/Admin)"""
    course = Course.query.get_or_404(course_id)
    thread = ForumThread.query.filter_by(id=thread_id, course_id=course_id).first_or_404()

    is_teacher_admin = (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id))
    if thread.user_id != current_user.id and not is_teacher_admin:
        abort(403)

    db.session.delete(thread)
    db.session.commit()
    flash('Discussion thread deleted successfully.', 'info')
    return redirect(url_for('forum.course_forum', course_id=course_id))


@forum_bp.route('/course/<int:course_id>/forum/reply/<int:reply_id>/delete', methods=['POST'])
@login_required
def delete_reply(course_id, reply_id):
    """Delete reply (Author or Instructor/Admin)"""
    course = Course.query.get_or_404(course_id)
    reply = ForumReply.query.get_or_404(reply_id)
    thread = reply.thread

    is_teacher_admin = (current_user.role in ('teacher', 'admin') and current_user.is_teacher_for_course(course.id))
    if reply.user_id != current_user.id and not is_teacher_admin:
        abort(403)

    db.session.delete(reply)
    db.session.commit()
    flash('Reply deleted successfully.', 'info')
    return redirect(url_for('forum.view_thread', course_id=course_id, thread_id=thread.id))
