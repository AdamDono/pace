"""
Portfolio of Evidence (PoE) All-in-One PDF Generator for Pace Academy.
Combines:
1. Cover & Learner Accreditation Summary
2. Master Assessment Summary Table (Assignments & Quizzes with Date Given, Date Completed, Marks)
3. Full Evidence for every Assignment (submitted text/code, feedback, and merged uploaded PDFs/images)
4. Full Evidence for every Quiz (scores, dates, and question-by-question answers)
"""

import html
import io
import os
import re
import urllib.request
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _esc(val):
    if val is None:
        return ""
    return html.escape(str(val)).replace("\n", "<br/>")


def _strip_html(val):
    if not val:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(val))
    return re.sub(r"\s+", " ", clean).strip()


def _fmt_dt(dt):
    if not dt:
        return "—"
    try:
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(dt)


def _fetch_uploaded_bytes(file_path, upload_folder):
    """Fetches uploaded file bytes from local disk or remote Cloudinary/HTTP URL."""
    if not file_path:
        return None
    fp = file_path.strip()
    if fp.startswith("http://") or fp.startswith("https://"):
        try:
            req = urllib.request.Request(fp, headers={"User-Agent": "PaceAcademy-PoE/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception:
            return None
    else:
        local_path = os.path.join(upload_folder, os.path.basename(fp))
        if not os.path.exists(local_path):
            local_path = os.path.join(upload_folder, fp.lstrip("/"))
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception:
                return None
    return None


def _build_pdf_part(story):
    """Renders a list of ReportLab flowables into a PDF BytesIO buffer."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Portfolio of Evidence (PoE)",
    )
    doc.build(story)
    buf.seek(0)
    return buf


def generate_student_poe_pdf(course, student, enrollment, assignment_data, quiz_data, stats, upload_folder):
    """
    Builds a single, complete Portfolio of Evidence (PoE) PDF containing all assignments,
    uploaded PDF attachments, and quizzes for `student` in `course`.
    Returns a `BytesIO` buffer ready to send via `send_file`.
    """
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#0d2a4a")
    blue = colors.HexColor("#2563eb")
    slate = colors.HexColor("#475569")
    light_bg = colors.HexColor("#f8fafc")
    border_col = colors.HexColor("#cbd5e1")
    emerald = colors.HexColor("#059669")

    title_style = ParagraphStyle(
        "PoeTitle", parent=styles["Heading1"], fontSize=20, leading=24, textColor=navy, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "PoeSubtitle", parent=styles["Normal"], fontSize=10, leading=14, textColor=blue, spaceAfter=12
    )
    h2_style = ParagraphStyle(
        "PoeH2", parent=styles["Heading2"], fontSize=13, leading=17, textColor=navy, spaceBefore=10, spaceAfter=6
    )
    h3_style = ParagraphStyle(
        "PoeH3", parent=styles["Heading3"], fontSize=11, leading=14, textColor=blue, spaceBefore=8, spaceAfter=4
    )
    body_style = ParagraphStyle(
        "PoeBody", parent=styles["Normal"], fontSize=9.5, leading=13.5, textColor=colors.HexColor("#1e293b")
    )
    small_style = ParagraphStyle(
        "PoeSmall", parent=styles["Normal"], fontSize=8.5, leading=11.5, textColor=slate
    )
    code_style = ParagraphStyle(
        "PoeCode", parent=styles["Code"], fontName="Courier", fontSize=8, leading=11,
        backColor=colors.HexColor("#f1f5f9"), borderPadding=6, textColor=colors.HexColor("#0f172a")
    )

    writer = PdfWriter()

    def append_story(story_items):
        if not story_items:
            return
        part_buf = _build_pdf_part(story_items)
        reader = PdfReader(part_buf)
        for page in reader.pages:
            writer.add_page(page)

    # ------------------------------------------------------------------
    # PART 1: COVER & MASTER SUMMARY PAGE
    # ------------------------------------------------------------------
    cover_story = []
    provider = course.partner_name or "Pace Academy"
    accred = course.partner_accreditation_number or course.accreditation_name or "Accredited Skills Programme"

    cover_story.append(Paragraph(f"PORTFOLIO OF EVIDENCE (PoE)", title_style))
    cover_story.append(Paragraph(f"{_esc(provider)} · {_esc(accred)}", subtitle_style))

    # Learner & Course Metadata Table
    student_name = student.full_name if hasattr(student, "full_name") else student.email
    meta_rows = [
        [Paragraph("<b>Learner Name</b>", small_style), Paragraph(_esc(student_name), body_style),
         Paragraph("<b>Course / Qualification</b>", small_style), Paragraph(_esc(course.title), body_style)],
        [Paragraph("<b>Email Address</b>", small_style), Paragraph(_esc(student.email), body_style),
         Paragraph("<b>ID / Passport No.</b>", small_style), Paragraph(_esc(getattr(student, "id_number", None) or "Not Provided"), body_style)],
        [Paragraph("<b>Date Enrolled</b>", small_style), Paragraph(_fmt_dt(getattr(enrollment, "enrolled_at", None)), body_style),
         Paragraph("<b>Date Completed</b>", small_style), Paragraph(_fmt_dt(getattr(enrollment, "completed_at", None)) if getattr(enrollment, "completed", False) else "In Progress", body_style)],
        [Paragraph("<b>Assignment Avg</b>", small_style), Paragraph(f"{stats.get('assignment_avg') or 0}%", body_style),
         Paragraph("<b>Overall Grade</b>", small_style), Paragraph(f"<b>{stats.get('overall_grade') or 0}%</b>", body_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[32 * mm, 55 * mm, 35 * mm, 52 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_bg),
        ("BOX", (0, 0), (-1, -1), 0.75, border_col),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, border_col),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    cover_story.append(meta_table)
    cover_story.append(Spacer(1, 10))

    # Master Assessment Summary Table
    cover_story.append(Paragraph("1. Assessment Summary (Assignments & Quizzes)", h2_style))
    summary_rows = [[
        Paragraph("<b>Assessment Name</b>", small_style),
        Paragraph("<b>Type</b>", small_style),
        Paragraph("<b>Date Given</b>", small_style),
        Paragraph("<b>Date Completed</b>", small_style),
        Paragraph("<b>Marks</b>", small_style),
    ]]

    for item in assignment_data:
        a = item["assignment"]
        sub = item["submission"]
        date_given = _fmt_dt(a.section.created_at if getattr(a, "section", None) else None)
        date_done = _fmt_dt(sub.submitted_at) if sub else "Not Submitted"
        if item["best_grade"] is not None:
            mark_str = f"{round(item['best_grade'], 1)}%"
        elif sub:
            mark_str = "Pending"
        else:
            mark_str = "0% (Missing)"
        summary_rows.append([
            Paragraph(_esc(a.title), small_style),
            Paragraph("Assignment", small_style),
            Paragraph(date_given, small_style),
            Paragraph(date_done, small_style),
            Paragraph(f"<b>{mark_str}</b>", small_style),
        ])

    for q_item in quiz_data:
        q = q_item["quiz"]
        attempts = q_item["attempts"]
        latest_q = attempts[0] if attempts else None
        date_given = _fmt_dt(q.section.created_at if getattr(q, "section", None) else None)
        date_done = _fmt_dt(latest_q.completed_at or latest_q.attempted_at) if latest_q else "Not Attempted"
        mark_str = f"{round(q_item['best_score'], 1)}%" if q_item["best_score"] is not None else "0% (Missing)"
        summary_rows.append([
            Paragraph(_esc(q.title), small_style),
            Paragraph("Quiz", small_style),
            Paragraph(date_given, small_style),
            Paragraph(date_done, small_style),
            Paragraph(f"<b>{mark_str}</b>", small_style),
        ])

    if len(summary_rows) == 1:
        summary_rows.append([Paragraph("No assessments found in this course.", small_style), "", "", "", ""])

    sum_table = Table(summary_rows, colWidths=[56 * mm, 24 * mm, 33 * mm, 35 * mm, 26 * mm], repeatRows=1)
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.75, border_col),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, border_col),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    cover_story.append(sum_table)
    cover_story.append(Spacer(1, 10))
    cover_story.append(Paragraph(f"Generated on {datetime.utcnow().strftime('%d %b %Y at %H:%M UTC')} · Official Pace Academy PoE Record", small_style))
    append_story(cover_story)

    # ------------------------------------------------------------------
    # PART 2: DETAILED ASSIGNMENT EVIDENCE (+ MERGED UPLOADED PDFs)
    # ------------------------------------------------------------------
    for idx, item in enumerate(assignment_data, start=1):
        a = item["assignment"]
        subs = item.get("submissions") or ([] if not item.get("submission") else [item["submission"]])
        sub = subs[0] if subs else None
        if not sub:
            continue  # Only include completed/submitted assignments in detailed evidence pages

        a_story = []
        a_story.append(Paragraph(f"Assignment Evidence #{idx}: {_esc(a.title)}", h2_style))
        date_given = _fmt_dt(a.section.created_at if getattr(a, "section", None) else None)
        date_done = _fmt_dt(sub.submitted_at)
        grade_disp = f"{round(sub.grade, 1)}%" if sub.grade is not None else "Pending Review"

        info_rows = [
            [Paragraph("<b>Date Given</b>", small_style), Paragraph(date_given, small_style),
             Paragraph("<b>Date Completed</b>", small_style), Paragraph(date_done, small_style)],
            [Paragraph("<b>Attempt</b>", small_style), Paragraph(f"#{sub.attempt_number or 1}", small_style),
             Paragraph("<b>Marks Gotten</b>", small_style), Paragraph(f"<b>{grade_disp}</b>", small_style)],
        ]
        info_t = Table(info_rows, colWidths=[30 * mm, 57 * mm, 32 * mm, 55 * mm])
        info_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light_bg),
            ("BOX", (0, 0), (-1, -1), 0.6, border_col),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, border_col),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        a_story.append(info_t)
        a_story.append(Spacer(1, 6))

        if a.description:
            a_story.append(Paragraph("<b>Instructions / Brief:</b>", h3_style))
            a_story.append(Paragraph(_esc(_strip_html(a.description)[:1200]), small_style))

        a_story.append(Paragraph("<b>Learner Submission:</b>", h3_style))
        if sub.submission_type == "code" and sub.code_submission:
            a_story.append(Paragraph(_esc(sub.code_submission[:4000]), code_style))
        elif sub.submission_text:
            a_story.append(Paragraph(_esc(sub.submission_text[:5000]), body_style))
        else:
            a_story.append(Paragraph("<i>File attachment submitted (see attached pages below).</i>", small_style))

        if sub.feedback:
            a_story.append(Paragraph("<b>Assessor / Colleague Zero Feedback:</b>", h3_style))
            a_story.append(Paragraph(_esc(sub.feedback[:3000]), body_style))

        # Handle uploaded file (PDF or Image)
        uploaded_pdf_bytes = None
        if sub.file_path:
            fname = sub.file_path.split("/")[-1].split("?")[0]
            a_story.append(Spacer(1, 4))
            a_story.append(Paragraph(f"<b>Attached File:</b> {_esc(fname)}", small_style))
            raw_bytes = _fetch_uploaded_bytes(sub.file_path, upload_folder)
            if raw_bytes:
                lower_fp = sub.file_path.lower().split("?")[0]
                if lower_fp.endswith(".pdf"):
                    uploaded_pdf_bytes = raw_bytes
                elif lower_fp.endswith((".png", ".jpg", ".jpeg", ".gif")):
                    try:
                        img_buf = io.BytesIO(raw_bytes)
                        rl_img = RLImage(img_buf, width=155 * mm, height=110 * mm, kind="proportional")
                        a_story.append(Spacer(1, 6))
                        a_story.append(rl_img)
                    except Exception:
                        pass

        append_story(a_story)

        # Merge every page of the uploaded PDF directly into this PoE PDF!
        if uploaded_pdf_bytes:
            try:
                up_reader = PdfReader(io.BytesIO(uploaded_pdf_bytes))
                for page in up_reader.pages:
                    writer.add_page(page)
            except Exception as merge_err:
                err_story = [Paragraph(f"<i>Note: Could not merge attached PDF ({_esc(merge_err)}).</i>", small_style)]
                append_story(err_story)

    # ------------------------------------------------------------------
    # PART 3: DETAILED QUIZ EVIDENCE (QUESTIONS & LEARNER ANSWERS)
    # ------------------------------------------------------------------
    for q_idx, q_item in enumerate(quiz_data, start=1):
        q = q_item["quiz"]
        attempts = q_item["attempts"]
        if not attempts:
            continue
        best_attempt = max(attempts, key=lambda att: att.score)
        q_story = []
        q_story.append(Paragraph(f"Quiz Evidence #{q_idx}: {_esc(q.title)}", h2_style))
        date_given = _fmt_dt(q.section.created_at if getattr(q, "section", None) else None)
        date_done = _fmt_dt(best_attempt.completed_at or best_attempt.attempted_at)
        passed = best_attempt.score >= (q.passing_score or 60.0)
        status_txt = "PASSED / COMPETENT" if passed else "BELOW PASS MARK"

        q_info = Table([
            [Paragraph("<b>Date Given</b>", small_style), Paragraph(date_given, small_style),
             Paragraph("<b>Date Completed</b>", small_style), Paragraph(date_done, small_style)],
            [Paragraph("<b>Best Mark</b>", small_style), Paragraph(f"<b>{round(best_attempt.score, 1)}%</b>", small_style),
             Paragraph("<b>Result</b>", small_style), Paragraph(f"<b>{status_txt}</b>", small_style)],
        ], colWidths=[30 * mm, 57 * mm, 32 * mm, 55 * mm])
        q_info.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light_bg),
            ("BOX", (0, 0), (-1, -1), 0.6, border_col),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, border_col),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        q_story.append(q_info)
        q_story.append(Spacer(1, 6))

        if best_attempt.answers:
            ans_rows = [[
                Paragraph("<b>Question</b>", small_style),
                Paragraph("<b>Learner Answer</b>", small_style),
                Paragraph("<b>Correct</b>", small_style),
                Paragraph("<b>Result</b>", small_style),
            ]]
            for ans in best_attempt.answers:
                ques = ans.question
                q_txt = _strip_html(ques.question_text) if ques else f"Question #{ans.question_id}"
                corr_ans = ques.correct_answer if ques else "—"
                is_right = (ans.selected_answer or "").strip().lower() == (corr_ans or "").strip().lower()
                ans_rows.append([
                    Paragraph(_esc(q_txt[:220]), small_style),
                    Paragraph(_esc(ans.selected_answer or "—"), small_style),
                    Paragraph(_esc(corr_ans), small_style),
                    Paragraph("✓ Correct" if is_right else "✗ Incorrect", small_style),
                ])
            ans_t = Table(ans_rows, colWidths=[94 * mm, 26 * mm, 24 * mm, 30 * mm], repeatRows=1)
            ans_t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.6, border_col),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, border_col),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]))
            q_story.append(ans_t)

        append_story(q_story)

    final_buf = io.BytesIO()
    writer.write(final_buf)
    final_buf.seek(0)
    return final_buf
