"""
Pace Academy Course Cohorts Blueprint & Helpers
-----------------------------------------------
100% additive cohort layer sitting alongside existing Courses, Enrollments,
LiveSessions, ForumThreads, and LearnerAccommodations (zero edits to existing DB tables!).

Standalone tables (auto-created via db.create_all()):
- `course_cohorts`          : Named cohorts / client intakes inside a course
- `course_cohort_members`   : Maps enrolled student_id -> cohort_id per course
- `live_session_cohorts`    : Optional target cohort for a Virtual Classroom session
- `forum_thread_cohorts`    : Optional cohort privacy scope for a Course Q&A thread
"""

from datetime import datetime
from flask import Blueprint, abort, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from app import csrf, db
from app.decorators import teacher_required

cohorts_bp = Blueprint("cohorts", __name__, url_prefix="/cohorts")


class CourseCohort(db.Model):
    __tablename__ = "course_cohorts"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    organization_name = db.Column(db.String(120), nullable=True)
    start_date = db.Column(db.String(30), nullable=True)
    end_date = db.Column(db.String(30), nullable=True)
    created_by_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CourseCohortMember(db.Model):
    __tablename__ = "course_cohort_members"

    id = db.Column(db.Integer, primary_key=True)
    cohort_id = db.Column(db.Integer, db.ForeignKey("course_cohorts.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class LiveSessionCohortTarget(db.Model):
    __tablename__ = "live_session_cohorts"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    cohort_id = db.Column(db.Integer, db.ForeignKey("course_cohorts.id"), nullable=False, index=True)


class ForumThreadCohortScope(db.Model):
    __tablename__ = "forum_thread_cohorts"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    cohort_id = db.Column(db.Integer, db.ForeignKey("course_cohorts.id"), nullable=False, index=True)


_cohort_tables_ready = False


def ensure_cohort_tables():
    global _cohort_tables_ready
    if _cohort_tables_ready:
        return
    try:
        db.create_all()
        _cohort_tables_ready = True
    except Exception:
        db.session.rollback()


def get_course_cohorts(course_id):
    """Returns all CourseCohort records for a given course, ordered newest first."""
    try:
        ensure_cohort_tables()
        return CourseCohort.query.filter_by(course_id=course_id).order_by(CourseCohort.created_at.desc()).all()
    except Exception:
        db.session.rollback()
        return []


def get_cohort_by_id(cohort_id, course_id=None):
    if not cohort_id:
        return None
    try:
        ensure_cohort_tables()
        q = CourseCohort.query.filter_by(id=cohort_id)
        if course_id is not None:
            q = q.filter_by(course_id=course_id)
        return q.first()
    except Exception:
        db.session.rollback()
        return None


def get_cohort_student_ids(cohort_id):
    """Returns a set of student_ids belonging to the specified cohort."""
    if not cohort_id:
        return set()
    try:
        ensure_cohort_tables()
        rows = CourseCohortMember.query.filter_by(cohort_id=cohort_id).all()
        return {r.student_id for r in rows}
    except Exception:
        db.session.rollback()
        return set()


def get_student_cohort_for_course(student_id, course_id):
    """Returns the CourseCohort a student belongs to for a course, or None."""
    if not student_id or not course_id:
        return None
    try:
        ensure_cohort_tables()
        mem = CourseCohortMember.query.filter_by(student_id=student_id, course_id=course_id).first()
        if not mem:
            return None
        return CourseCohort.query.get(mem.cohort_id)
    except Exception:
        db.session.rollback()
        return None


def get_course_student_cohort_map(course_id):
    """Returns {student_id: CourseCohort} for all cohort members in a course."""
    try:
        ensure_cohort_tables()
        cohorts = {c.id: c for c in CourseCohort.query.filter_by(course_id=course_id).all()}
        if not cohorts:
            return {}
        members = CourseCohortMember.query.filter_by(course_id=course_id).all()
        return {m.student_id: cohorts[m.cohort_id] for m in members if m.cohort_id in cohorts}
    except Exception:
        db.session.rollback()
        return {}


def get_cohort_member_counts(course_id):
    """Returns {cohort_id: count} for all cohorts in a course."""
    try:
        ensure_cohort_tables()
        counts = {}
        for m in CourseCohortMember.query.filter_by(course_id=course_id).all():
            counts[m.cohort_id] = counts.get(m.cohort_id, 0) + 1
        return counts
    except Exception:
        db.session.rollback()
        return {}


def assign_student_to_cohort(course_id, student_id, cohort_id):
    """Assigns a student to a cohort within a course (or removes them if cohort_id is None/0)."""
    ensure_cohort_tables()
    existing = CourseCohortMember.query.filter_by(course_id=course_id, student_id=student_id).all()
    for row in existing:
        db.session.delete(row)

    if cohort_id:
        cohort = CourseCohort.query.filter_by(id=cohort_id, course_id=course_id).first()
        if cohort:
            db.session.add(CourseCohortMember(
                cohort_id=cohort.id,
                course_id=course_id,
                student_id=student_id,
            ))
    db.session.commit()


def set_live_session_cohort(session_id, cohort_id):
    """Links a LiveSession to an optional target cohort (None = entire course)."""
    try:
        ensure_cohort_tables()
        existing = LiveSessionCohortTarget.query.filter_by(session_id=session_id).first()
        if existing:
            db.session.delete(existing)
        if cohort_id:
            db.session.add(LiveSessionCohortTarget(session_id=session_id, cohort_id=cohort_id))
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_live_session_cohort_map(session_ids):
    """Returns {session_id: CourseCohort} for sessions that target a specific cohort."""
    if not session_ids:
        return {}
    try:
        ensure_cohort_tables()
        targets = LiveSessionCohortTarget.query.filter(LiveSessionCohortTarget.session_id.in_(session_ids)).all()
        if not targets:
            return {}
        c_ids = list({t.cohort_id for t in targets})
        cohorts = {c.id: c for c in CourseCohort.query.filter(CourseCohort.id.in_(c_ids)).all()}
        return {t.session_id: cohorts[t.cohort_id] for t in targets if t.cohort_id in cohorts}
    except Exception:
        db.session.rollback()
        return {}


def filter_live_sessions_for_student(sessions, student_id):
    """Filters a list of LiveSessions so cohort-targeted sessions only show to members of that cohort."""
    if not sessions:
        return []
    try:
        ensure_cohort_tables()
        s_ids = [s.id for s in sessions]
        targets = LiveSessionCohortTarget.query.filter(LiveSessionCohortTarget.session_id.in_(s_ids)).all()
        if not targets:
            return sessions
        target_by_session = {t.session_id: t.cohort_id for t in targets}
        student_cohort_ids = {
            m.cohort_id for m in CourseCohortMember.query.filter_by(student_id=student_id).all()
        }
        visible = []
        for s in sessions:
            req_cid = target_by_session.get(s.id)
            if req_cid is None or req_cid in student_cohort_ids:
                visible.append(s)
        return visible
    except Exception:
        db.session.rollback()
        return sessions


def set_forum_thread_cohort(thread_id, cohort_id):
    """Tags a ForumThread with a cohort_id for cohort-private Q&A."""
    if not thread_id or not cohort_id:
        return
    try:
        ensure_cohort_tables()
        existing = ForumThreadCohortScope.query.filter_by(thread_id=thread_id).first()
        if existing:
            existing.cohort_id = cohort_id
        else:
            db.session.add(ForumThreadCohortScope(thread_id=thread_id, cohort_id=cohort_id))
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_forum_thread_cohort_map(thread_ids):
    """Returns {thread_id: CourseCohort} for cohort-scoped forum threads."""
    if not thread_ids:
        return {}
    try:
        ensure_cohort_tables()
        scopes = ForumThreadCohortScope.query.filter(ForumThreadCohortScope.thread_id.in_(thread_ids)).all()
        if not scopes:
            return {}
        c_ids = list({sc.cohort_id for sc in scopes})
        cohorts = {c.id: c for c in CourseCohort.query.filter(CourseCohort.id.in_(c_ids)).all()}
        return {sc.thread_id: cohorts[sc.cohort_id] for sc in scopes if sc.cohort_id in cohorts}
    except Exception:
        db.session.rollback()
        return {}


def compute_anonymized_inclusive_summary(student_ids):
    """
    Computes POPIA-safe, anonymized aggregate counts of approved accessibility concessions
    and assistive support usage for a cohort or course (zero learner names or medical details).
    """
    s_ids = list(set(student_ids or []))
    summary = {
        "total_learners": len(s_ids),
        "with_support": 0,
        "extra_quiz_time": 0,
        "voice_dictation": 0,
        "assistive_display": 0,
        "captions_enabled": 0,
    }
    if not s_ids:
        return summary
    try:
        from app.routes.accessibility import LearnerAccommodation, _ensure_a11y_table
        _ensure_a11y_table()
        recs = LearnerAccommodation.query.filter(LearnerAccommodation.user_id.in_(s_ids)).all()
        for r in recs:
            has_extra = (r.quiz_time_multiplier is not None and float(r.quiz_time_multiplier) != 1.0)
            has_voice = bool(r.voice_dictation_enabled)
            has_disp = bool(
                r.dyslexia_font or r.high_contrast or r.read_aloud_enabled
                or (r.font_scale in ("large", "xlarge"))
            )
            has_cap = bool(r.captions_preferred)
            if has_extra:
                summary["extra_quiz_time"] += 1
            if has_voice:
                summary["voice_dictation"] += 1
            if has_disp:
                summary["assistive_display"] += 1
            if has_cap:
                summary["captions_enabled"] += 1
            if r.has_disability_support or has_extra or has_voice or has_disp or has_cap:
                summary["with_support"] += 1
    except Exception:
        db.session.rollback()
    return summary


# ===================== ROUTES =====================

@cohorts_bp.route("/course/<int:course_id>/create", methods=["POST"])
@teacher_required
def create_cohort(course_id):
    from app.models import Course
    ensure_cohort_tables()
    course = Course.query.get_or_404(course_id)
    if not current_user.is_teacher_for_course(course.id) and current_user.role != "admin":
        abort(403)

    name = (request.form.get("name") or "").strip()
    org = (request.form.get("organization_name") or "").strip() or None
    start_date = (request.form.get("start_date") or "").strip() or None
    end_date = (request.form.get("end_date") or "").strip() or None

    if not name:
        flash("Please enter a cohort name.", "warning")
        return redirect(url_for("teacher.enroll_students", identifier=course.slug_or_id))

    cohort = CourseCohort(
        course_id=course.id,
        name=name[:120],
        organization_name=org[:120] if org else None,
        start_date=start_date[:30] if start_date else None,
        end_date=end_date[:30] if end_date else None,
        created_by_id=current_user.id,
    )
    db.session.add(cohort)
    db.session.commit()
    flash(f'Cohort "{cohort.name}" created successfully!', "success")
    return redirect(url_for("teacher.enroll_students", identifier=course.slug_or_id))


@cohorts_bp.route("/<int:cohort_id>/delete", methods=["POST"])
@teacher_required
def delete_cohort(cohort_id):
    from app.models import Course
    ensure_cohort_tables()
    cohort = CourseCohort.query.get_or_404(cohort_id)
    course = Course.query.get_or_404(cohort.course_id)
    if not current_user.is_teacher_for_course(course.id) and current_user.role != "admin":
        abort(403)

    # Remove links safely without un-enrolling any students
    CourseCohortMember.query.filter_by(cohort_id=cohort.id).delete()
    LiveSessionCohortTarget.query.filter_by(cohort_id=cohort.id).delete()
    ForumThreadCohortScope.query.filter_by(cohort_id=cohort.id).delete()
    cname = cohort.name
    db.session.delete(cohort)
    db.session.commit()
    flash(f'Cohort "{cname}" deleted. Students remain enrolled in the course.', "info")
    return redirect(url_for("teacher.enroll_students", identifier=course.slug_or_id))


@cohorts_bp.route("/course/<int:course_id>/assign", methods=["POST"])
@csrf.exempt
@teacher_required
def assign_student_cohort_route(course_id):
    from app.models import Course
    ensure_cohort_tables()
    course = Course.query.get_or_404(course_id)
    if not current_user.is_teacher_for_course(course.id) and current_user.role != "admin":
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    if request.is_json:
        data = request.get_json(silent=True) or {}
        student_id = data.get("student_id")
        cohort_id = data.get("cohort_id") or None
        try:
            student_id = int(student_id)
            cohort_id = int(cohort_id) if cohort_id else None
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "Invalid student or cohort ID."}), 400
        assign_student_to_cohort(course.id, student_id, cohort_id)
        cohort = get_cohort_by_id(cohort_id, course.id) if cohort_id else None
        return jsonify({"ok": True, "cohort_id": cohort.id if cohort else None, "cohort_name": cohort.name if cohort else None})

    student_id = request.form.get("student_id", type=int)
    cohort_id = request.form.get("cohort_id", type=int)
    if student_id:
        assign_student_to_cohort(course.id, student_id, cohort_id)
        flash("Learner cohort updated.", "success")
    return redirect(url_for("teacher.enroll_students", identifier=course.slug_or_id))


@cohorts_bp.route("/api/course/<int:course_id>", methods=["GET"])
@login_required
def api_list_course_cohorts(course_id):
    from app.models import Course
    course = Course.query.get_or_404(course_id)
    if getattr(current_user, "role", None) not in ("teacher", "admin") or (
        current_user.role == "teacher" and not current_user.is_teacher_for_course(course.id)
    ):
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    cohorts = get_course_cohorts(course.id)
    counts = get_cohort_member_counts(course.id)
    return jsonify({
        "ok": True,
        "cohorts": [
            {
                "id": c.id,
                "name": c.name,
                "organization_name": c.organization_name or "",
                "start_date": c.start_date or "",
                "end_date": c.end_date or "",
                "member_count": counts.get(c.id, 0),
            }
            for c in cohorts
        ],
    })
