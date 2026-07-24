"""
Moodle Course Importer — Flask Blueprint
Route: /teacher/import-course
"""

import os
import uuid
import logging
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.decorators import teacher_required

logger = logging.getLogger(__name__)

importer_bp = Blueprint("importer", __name__, url_prefix="/teacher/import-course")

ALLOWED_EXT = {".mbz"}
MAX_MBZ_SIZE = 100 * 1024 * 1024   # 100 MB


def _allowed(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXT


# ------------------------------------------------------------------
# Upload form
# ------------------------------------------------------------------

@importer_bp.route("/", methods=["GET"])
@login_required
@teacher_required
def import_form():
    return render_template("teacher/import_course.html")


# ------------------------------------------------------------------
# AJAX preview — parse without writing to DB
# ------------------------------------------------------------------

@importer_bp.route("/preview", methods=["POST"])
@login_required
@teacher_required
def preview():
    f = request.files.get("mbz_file")
    if not f or not f.filename:
        return jsonify({"error": "No file uploaded"}), 400
    if not _allowed(f.filename):
        return jsonify({"error": "Only .mbz files are accepted"}), 400
    if f.content_length > MAX_MBZ_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_MBZ_SIZE // (1024*1024)} MB"}), 400

    tmp_path = _save_tmp(f)
    try:
        from app.utils.moodle_parser import MoodleImporter
        importer = MoodleImporter(current_user, current_app.config["UPLOAD_FOLDER"])
        preview_data = importer.preview_mbz(tmp_path)
        return jsonify(preview_data)
    except Exception as e:
        logger.error(f"Preview error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        _remove_tmp(tmp_path)


# ------------------------------------------------------------------
# Full import — write to DB
# ------------------------------------------------------------------

@importer_bp.route("/run", methods=["POST"])
@login_required
@teacher_required
def run_import():
    f = request.files.get("mbz_file")
    if not f or not f.filename:
        flash("No file uploaded.", "danger")
        return redirect(url_for("importer.import_form"))
    if not _allowed(f.filename):
        flash("Only .mbz files are accepted.", "danger")
        return redirect(url_for("importer.import_form"))
    if f.content_length > MAX_MBZ_SIZE:
        flash(f"File too large. Maximum size is {MAX_MBZ_SIZE // (1024*1024)} MB", "danger")
        return redirect(url_for("importer.import_form"))

    tmp_path = _save_tmp(f)
    try:
        from app.utils.moodle_parser import MoodleImporter
        importer = MoodleImporter(current_user, current_app.config["UPLOAD_FOLDER"])
        course, report = importer.import_mbz(tmp_path)

        flash(
            f"✅ '{report['course_title']}' imported as a draft! "
            f"{report['modules_created']} modules, "
            f"{report['sections_created']} sections, "
            f"{report['quizzes_created']} quizzes, "
            f"{report['assignments_created']} assignments.",
            "success",
        )

        if report["skipped_activities"] or report["warnings"]:
            skip_msg = "; ".join(
                (report["skipped_activities"] + report["warnings"])[:5]
            )
            flash(f"⚠️ Some items were skipped: {skip_msg}", "warning")

        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"redirect": url_for("teacher.course_builder", course_id=course.id)})

        return redirect(url_for("teacher.manage_modules", course_id=course.id))

    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"error": str(e)}), 500
        flash(f"Import failed: {str(e)}", "danger")
        return redirect(url_for("importer.import_form"))
    finally:
        _remove_tmp(tmp_path)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _save_tmp(file_obj):
    tmp_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    filename = secure_filename(file_obj.filename)
    path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_{filename}")
    file_obj.save(path)
    return path


def _remove_tmp(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
