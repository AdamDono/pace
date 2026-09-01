"""
Inactivity & Learning Progress Nudge System.
Detects enrolled learners who haven't engaged in 7+ days and sends personalized
re-engagement emails highlighting their exact progress and next lesson.
"""

import logging
from datetime import datetime, timedelta
from flask import current_app, url_for
from app import db
from app.models import Enrollment, EnrollmentSection, Course, User, Section
from app.utils.email import send_email

logger = logging.getLogger(__name__)

def get_inactive_enrollments(days_inactive=7):
    """
    Query and return all active enrollments where the learner has been inactive
    for at least `days_inactive` days, and has not received a nudge in the last 7 days.
    """
    now = datetime.utcnow()
    cutoff_date = now - timedelta(days=days_inactive)
    rate_limit_cutoff = now - timedelta(days=7)

    # Active enrollments in approved courses with unbanned students
    active_enrollments = Enrollment.query.join(User).join(Course) \
        .filter(Enrollment.completed == False) \
        .filter(Enrollment.is_blocked == False) \
        .filter(Course.status == 'approved') \
        .filter(User.is_suspended == False) \
        .filter(User.is_banned == False) \
        .all()

    inactive_candidates = []

    for enrollment in active_enrollments:
        student = enrollment.student
        course = enrollment.course
        if not student or not course:
            continue

        # Check rate-limit (don't nudge more than once every 7 days per enrollment)
        if enrollment.last_nudge_sent_at and enrollment.last_nudge_sent_at > rate_limit_cutoff:
            continue

        # Determine last activity timestamp across sections, enrollment date, and user login
        es_list = EnrollmentSection.query.filter_by(enrollment_id=enrollment.id).all()
        section_accessed_dates = [es.last_accessed for es in es_list if es.last_accessed]
        most_recent_section_access = max(section_accessed_dates) if section_accessed_dates else None

        last_activity = max(filter(None, [
            most_recent_section_access,
            enrollment.enrolled_at,
            student.last_login
        ]), default=None)

        if not last_activity or last_activity > cutoff_date:
            # Active recently, skip
            continue

        # Calculate days since last activity
        delta_days = (now - last_activity).days

        # Calculate progress
        all_sections = Section.query.filter_by(course_id=course.id).order_by(Section.order).all()
        total_sections = len(all_sections)
        if total_sections == 0:
            continue

        es_by_sec = {es.section_id: es for es in es_list}
        completed_sections = sum(1 for es in es_list if es.completed)
        progress = round((completed_sections / total_sections) * 100)

        # Find the next incomplete section
        next_section = None
        for sec in all_sections:
            es = es_by_sec.get(sec.id)
            if not (es and es.completed):
                next_section = sec
                break

        if not next_section and all_sections:
            next_section = all_sections[0]

        # Calculate remaining duration in minutes
        remaining_duration = sum(s.duration or 15 for s in all_sections if not (es_by_sec.get(s.id) and es_by_sec.get(s.id).completed))
        if remaining_duration <= 0:
            remaining_duration = 15

        inactive_candidates.append({
            'enrollment': enrollment,
            'student': student,
            'course': course,
            'days_inactive': delta_days,
            'progress': progress,
            'completed_sections': completed_sections,
            'total_sections': total_sections,
            'next_section': next_section,
            'remaining_duration': remaining_duration,
            'last_activity': last_activity
        })

    return inactive_candidates


def send_inactivity_nudges(app=None, days_inactive=7, dry_run=False):
    """
    Scans for inactive learners and dispatches personalized progress emails.
    """
    ctx_app = app or current_app
    with ctx_app.app_context():
        candidates = get_inactive_enrollments(days_inactive=days_inactive)
        sent_count = 0

        logger.info(f"Starting Inactivity Nudge Job: Found {len(candidates)} candidate(s) inactive >= {days_inactive} days.")

        for item in candidates:
            student = item['student']
            course = item['course']
            enrollment = item['enrollment']
            next_section = item['next_section']
            days = item['days_inactive']
            progress = item['progress']

            # Choose tailored subject line based on inactivity duration
            student_name = student.first_name or student.full_name or student.username
            if days < 14:
                subject = f"Hey {student_name}, your next lesson in {course.title} is waiting! 📚"
            elif days < 28:
                subject = f"You're {progress}% to your certificate in {course.title}! 🎓"
            else:
                subject = f"Let's get back on track with {course.title}! 🚀"

            # 1-Click direct URL to next section
            try:
                resume_url = url_for(
                    'student.course_detail',
                    course_id=course.id,
                    section_id=next_section.id if next_section else None,
                    _external=True
                )
            except Exception:
                resume_url = f"https://pace-academy.co.za/course/{course.id}"

            if not dry_run:
                try:
                    send_email(
                        subject=subject,
                        recipient=student.email,
                        template='progress_nudge',
                        student=student,
                        student_name=student_name,
                        course=course,
                        progress=progress,
                        completed_sections=item['completed_sections'],
                        total_sections=item['total_sections'],
                        next_section=next_section,
                        remaining_duration=item['remaining_duration'],
                        days_inactive=days,
                        resume_url=resume_url
                    )

                    enrollment.last_nudge_sent_at = datetime.utcnow()
                    db.session.commit()
                    sent_count += 1
                    logger.info(f"Progress nudge email sent to {student.email} for course '{course.title}' ({days} days inactive).")
                except Exception as e:
                    logger.error(f"Failed to send progress nudge to {student.email}: {e}")
            else:
                sent_count += 1
                logger.info(f"[DRY RUN] Would send progress nudge to {student.email} for '{course.title}' ({days} days inactive, {progress}% done).")

        logger.info(f"Inactivity Nudge Job Complete: {sent_count} nudge(s) processed (dry_run={dry_run}).")
        return {
            'total_candidates': len(candidates),
            'nudges_sent': sent_count,
            'dry_run': dry_run
        }
