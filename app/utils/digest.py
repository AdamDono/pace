"""
Weekly digest email — sends a summary of the past 7 days to opted-in users.
Called by the APScheduler job in run.py every Monday at 08:00.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def send_weekly_digests(app):
    """
    Build and send the weekly activity digest to every user who has opted in.

    Args:
        app: The Flask application instance (needed for app context & mail).
    """
    with app.app_context():
        from app.models import (
            User, NotificationPreference, Enrollment,
            Assignment, AssignmentSubmission, QuizAttempt,
            Announcement, Section, db
        )
        from app.utils.email import send_email

        week_ago = datetime.utcnow() - timedelta(days=7)

        # Fetch all users who have weekly digest enabled
        opted_in = (
            NotificationPreference.query
            .filter_by(weekly_digest=True)
            .all()
        )

        sent_count = 0
        for pref in opted_in:
            user = User.query.get(pref.user_id)
            if not user or user.is_banned or user.is_suspended:
                continue

            try:
                digest_data = _build_digest(user, week_ago)
                # Skip sending if there is nothing interesting to report
                if not any([
                    digest_data['pending_assignments'],
                    digest_data['recent_grades'],
                    digest_data['recent_quiz_attempts'],
                    digest_data['new_announcements'],
                ]):
                    continue

                send_email(
                    subject='Your Weekly Pace Academy Digest',
                    recipient=user.email,
                    template='weekly_digest',
                    user=user,
                    digest=digest_data,
                    week_ago=week_ago,
                    current_date=datetime.utcnow(),
                )
                sent_count += 1
                logger.info(f"Weekly digest sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send weekly digest to {user.email}: {e}")

        logger.info(f"Weekly digest job complete — sent to {sent_count} users.")


def _build_digest(user, week_ago):
    """Gather a week's worth of activity data for a single user."""
    from app.models import (
        Enrollment, Assignment, AssignmentSubmission,
        QuizAttempt, Announcement, Section
    )

    enrolled_course_ids = [
        e.course_id
        for e in Enrollment.query.filter_by(student_id=user.id).all()
    ]

    # Pending assignments (not yet submitted)
    pending_assignments = []
    if enrolled_course_ids:
        all_assignments = (
            Assignment.query
            .join(Section, Assignment.section_id == Section.id)
            .filter(Section.course_id.in_(enrolled_course_ids))
            .all()
        )
        for assignment in all_assignments:
            submitted = AssignmentSubmission.query.filter_by(
                assignment_id=assignment.id,
                student_id=user.id
            ).first()
            if not submitted:
                pending_assignments.append({
                    'title': assignment.title,
                    'due_date': assignment.due_date,
                })

    # Recently graded submissions
    recent_grades = []
    graded = (
        AssignmentSubmission.query
        .filter(
            AssignmentSubmission.student_id == user.id,
            AssignmentSubmission.reviewed == True,
            AssignmentSubmission.submitted_at >= week_ago,
        )
        .order_by(AssignmentSubmission.submitted_at.desc())
        .limit(5)
        .all()
    )
    for sub in graded:
        recent_grades.append({
            'assignment_title': sub.assignment.title if sub.assignment else 'Assignment',
            'grade': sub.grade,
            'feedback': (sub.feedback or '')[:120],
        })

    # Recent quiz attempts
    recent_quiz_attempts = []
    attempts = (
        QuizAttempt.query
        .filter(
            QuizAttempt.student_id == user.id,
            QuizAttempt.attempted_at >= week_ago,
        )
        .order_by(QuizAttempt.attempted_at.desc())
        .limit(5)
        .all()
    )
    for attempt in attempts:
        recent_quiz_attempts.append({
            'quiz_title': attempt.quiz.title if attempt.quiz else 'Quiz',
            'score': attempt.score,
            'attempted_at': attempt.attempted_at,
        })

    # New announcements in enrolled courses
    new_announcements = []
    if enrolled_course_ids:
        announcements = (
            Announcement.query
            .filter(
                Announcement.course_id.in_(enrolled_course_ids),
                Announcement.created_at >= week_ago,
            )
            .order_by(Announcement.created_at.desc())
            .limit(5)
            .all()
        )
        for ann in announcements:
            new_announcements.append({
                'title': ann.title,
                'course_title': ann.course.title if ann.course else '',
                'created_at': ann.created_at,
            })

    return {
        'pending_assignments': pending_assignments,
        'recent_grades': recent_grades,
        'recent_quiz_attempts': recent_quiz_attempts,
        'new_announcements': new_announcements,
    }
