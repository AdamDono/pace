"""
Pace Academy Accessibility & Learner Accommodations Blueprint
-----------------------------------------------------------
Provides:
1. Standalone `learner_accommodations` table (zero changes to existing `users`, `quizzes`, or `assignments` tables).
2. Self-service display preferences for every learner (Font Size, Dyslexia Mode, High Contrast, Reduce Motion, Read Aloud, Captions).
3. Private, POPIA-compliant official assessment concessions managed by Educators/Admins
   (Disability support categories, Quiz Extra Time: +25%/+50%/+100%/Untimed, Voice Dictation, SETA/QCTO notes).
"""

import json
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import csrf, db

accessibility_bp = Blueprint("accessibility", __name__, url_prefix="/accessibility")


class LearnerAccommodation(db.Model):
    """Stores per-learner accessibility display settings and private educator-managed concessions."""
    __tablename__ = "learner_accommodations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # Self-service display & assistive preferences (available to every learner)
    font_scale = db.Column(db.String(20), nullable=False, default="normal")  # normal | large | xlarge
    dyslexia_font = db.Column(db.Boolean, nullable=False, default=False)
    high_contrast = db.Column(db.Boolean, nullable=False, default=False)
    reduce_motion = db.Column(db.Boolean, nullable=False, default=False)
    read_aloud_enabled = db.Column(db.Boolean, nullable=False, default=False)
    captions_preferred = db.Column(db.Boolean, nullable=False, default=False)

    # Educator / Admin managed official concessions (POPIA-private)
    has_disability_support = db.Column(db.Boolean, nullable=False, default=False)
    support_categories_json = db.Column(db.Text, nullable=True, default="[]")
    quiz_time_multiplier = db.Column(db.Float, nullable=False, default=1.0)  # 1.0, 1.25, 1.5, 2.0, or 0.0 (untimed)
    voice_dictation_enabled = db.Column(db.Boolean, nullable=False, default=False)
    concession_notes = db.Column(db.Text, nullable=True, default="")

    updated_by_id = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


DEFAULT_A11Y = {
    "font_scale": "normal",
    "dyslexia_font": False,
    "high_contrast": False,
    "reduce_motion": False,
    "read_aloud_enabled": False,
    "captions_preferred": False,
    "has_disability_support": False,
    "support_categories": [],
    "quiz_time_multiplier": 1.0,
    "quiz_time_label": "Standard (1×)",
    "voice_dictation_enabled": False,
    "concession_notes": "",
}

ALLOWED_FONT_SCALES = {"normal", "large", "xlarge"}
ALLOWED_CATEGORIES = {
    "visual_blind",
    "low_vision",
    "hearing",
    "dyslexia_learning",
    "physical_mobility",
    "other",
}
ALLOWED_MULTIPLIERS = {1.0, 1.25, 1.5, 2.0, 0.0}

_table_ready = False


def _ensure_a11y_table():
    global _table_ready
    if _table_ready:
        return
    try:
        db.create_all()
        _table_ready = True
    except Exception:
        db.session.rollback()


def _format_multiplier_label(mult):
    if mult == 0.0:
        return "Untimed"
    if mult == 1.25:
        return "+25% Extra Time"
    if mult == 1.5:
        return "+50% Extra Time"
    if mult == 2.0:
        return "+100% Extra Time"
    return "Standard (1×)"


def serialize_accommodation(rec):
    if not rec:
        return dict(DEFAULT_A11Y)
    try:
        cats = json.loads(rec.support_categories_json or "[]")
        if not isinstance(cats, list):
            cats = []
    except Exception:
        cats = []
    mult = float(rec.quiz_time_multiplier) if rec.quiz_time_multiplier is not None else 1.0
    if mult not in ALLOWED_MULTIPLIERS:
        mult = 1.0
    return {
        "font_scale": rec.font_scale if rec.font_scale in ALLOWED_FONT_SCALES else "normal",
        "dyslexia_font": bool(rec.dyslexia_font),
        "high_contrast": bool(rec.high_contrast),
        "reduce_motion": bool(rec.reduce_motion),
        "read_aloud_enabled": bool(rec.read_aloud_enabled),
        "captions_preferred": bool(rec.captions_preferred),
        "has_disability_support": bool(rec.has_disability_support),
        "support_categories": cats,
        "quiz_time_multiplier": mult,
        "quiz_time_label": _format_multiplier_label(mult),
        "voice_dictation_enabled": bool(rec.voice_dictation_enabled),
        "concession_notes": rec.concession_notes or "",
    }


def get_user_accessibility_dict(user_id):
    """Safely fetches a user's accessibility settings & concessions; always returns valid defaults."""
    if not user_id:
        return dict(DEFAULT_A11Y)
    try:
        _ensure_a11y_table()
        rec = LearnerAccommodation.query.filter_by(user_id=user_id).first()
        return serialize_accommodation(rec)
    except Exception:
        db.session.rollback()
        return dict(DEFAULT_A11Y)


def _get_or_create_record(user_id):
    _ensure_a11y_table()
    rec = LearnerAccommodation.query.filter_by(user_id=user_id).first()
    if not rec:
        rec = LearnerAccommodation(user_id=user_id)
        db.session.add(rec)
    return rec


@accessibility_bp.route("/api/me", methods=["GET"])
@login_required
def api_get_my_accessibility():
    return jsonify({"ok": True, "settings": get_user_accessibility_dict(current_user.id)})


@accessibility_bp.route("/api/me", methods=["POST"])
@csrf.exempt
@login_required
def api_update_my_accessibility():
    """Learners can update their own display/assistive preferences (cannot self-grant official exam extra time)."""
    data = request.get_json(silent=True) or {}
    try:
        rec = _get_or_create_record(current_user.id)
        if "font_scale" in data and data["font_scale"] in ALLOWED_FONT_SCALES:
            rec.font_scale = data["font_scale"]
        if "dyslexia_font" in data:
            rec.dyslexia_font = bool(data["dyslexia_font"])
        if "high_contrast" in data:
            rec.high_contrast = bool(data["high_contrast"])
        if "reduce_motion" in data:
            rec.reduce_motion = bool(data["reduce_motion"])
        if "read_aloud_enabled" in data:
            rec.read_aloud_enabled = bool(data["read_aloud_enabled"])
        if "captions_preferred" in data:
            rec.captions_preferred = bool(data["captions_preferred"])
        rec.updated_by_id = current_user.id
        rec.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "settings": serialize_accommodation(rec)})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500


@accessibility_bp.route("/api/student/<int:student_id>", methods=["GET"])
@login_required
def api_get_student_accommodations(student_id):
    if getattr(current_user, "role", None) not in ("teacher", "admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 403
    return jsonify({"ok": True, "settings": get_user_accessibility_dict(student_id)})


@accessibility_bp.route("/api/student/<int:student_id>", methods=["POST"])
@csrf.exempt
@login_required
def api_update_student_accommodations(student_id):
    """Teachers and Admins manage private disability accommodations and exam concessions for a learner."""
    if getattr(current_user, "role", None) not in ("teacher", "admin"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    try:
        rec = _get_or_create_record(student_id)

        if "has_disability_support" in data:
            rec.has_disability_support = bool(data["has_disability_support"])

        if "support_categories" in data and isinstance(data["support_categories"], list):
            clean_cats = [c for c in data["support_categories"] if c in ALLOWED_CATEGORIES]
            rec.support_categories_json = json.dumps(clean_cats)
            if clean_cats and "has_disability_support" not in data:
                rec.has_disability_support = True

        if "quiz_time_multiplier" in data:
            try:
                mult = float(data["quiz_time_multiplier"])
            except (ValueError, TypeError):
                mult = 1.0
            rec.quiz_time_multiplier = mult if mult in ALLOWED_MULTIPLIERS else 1.0

        if "voice_dictation_enabled" in data:
            rec.voice_dictation_enabled = bool(data["voice_dictation_enabled"])

        if "concession_notes" in data:
            rec.concession_notes = str(data["concession_notes"] or "")[:2000]

        # Optional display presets an educator can pre-configure for the learner
        if "font_scale" in data and data["font_scale"] in ALLOWED_FONT_SCALES:
            rec.font_scale = data["font_scale"]
        if "dyslexia_font" in data:
            rec.dyslexia_font = bool(data["dyslexia_font"])
        if "high_contrast" in data:
            rec.high_contrast = bool(data["high_contrast"])
        if "reduce_motion" in data:
            rec.reduce_motion = bool(data["reduce_motion"])
        if "read_aloud_enabled" in data:
            rec.read_aloud_enabled = bool(data["read_aloud_enabled"])
        if "captions_preferred" in data:
            rec.captions_preferred = bool(data["captions_preferred"])

        rec.updated_by_id = current_user.id
        rec.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "settings": serialize_accommodation(rec)})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500
