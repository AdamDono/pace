"""
Pace Academy SETA / QCTO Compliance & Course Analytics PDF Generator
--------------------------------------------------------------------
Builds an executive, audit-ready PDF mirroring the Course Analytics dashboard:
- Branded Header Banner & Course Accreditation Metadata
- 4 KPI Overview Cards (Total Students, Completion Rate, Active 7d, Avg Session Time)
- Vector Donut Chart: Student Progress Distribution (Completed / In Progress / Started / Not Started)
- Vector Horizontal Bar Chart: Syllabus Dropoff Analysis (Completion % per Section)
- Quiz Performance Summary Table
- Full SETA / QCTO Learner Compliance & Attendance Logbook Table (SA ID, Hours, Scores, Status)
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _safe(val, fallback="N/A"):
    if val is None:
        return escape(str(fallback))
    s = str(val).strip()
    return escape(s if s else str(fallback))


def _build_donut_chart(completed, in_progress, started, not_started):
    """Draws a crisp vector donut chart matching the Course Analytics Progress Distribution chart."""
    d = Drawing(240, 195)
    # Card background
    d.add(Rect(0, 0, 240, 195, rx=8, ry=8, fillColor=colors.white, strokeColor=colors.HexColor("#E5E7EB"), strokeWidth=0.8))
    d.add(String(12, 178, "Student Progress Distribution", fontName="Helvetica-Bold", fontSize=9.5, fillColor=colors.HexColor("#111827")))
    d.add(String(12, 166, "Syllabus completion breakdown across learners", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#6B7280")))

    total = completed + in_progress + started + not_started
    if total == 0:
        d.add(Circle(120, 102, 42, fillColor=colors.HexColor("#F3F4F6"), strokeColor=colors.HexColor("#D1D5DB"), strokeWidth=1))
        d.add(Circle(120, 102, 24, fillColor=colors.white, strokeColor=colors.white))
        d.add(String(120, 99, "No Data", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor("#9CA3AF"), textAnchor="middle"))
    else:
        pie = Pie()
        pie.x = 76
        pie.y = 60
        pie.width = 88
        pie.height = 88
        pie.data = [completed, in_progress, started, not_started]
        pie.labels = None
        pie.slices.strokeWidth = 1.2
        pie.slices.strokeColor = colors.white
        palette = [
            colors.HexColor("#10B981"),  # Emerald - Completed
            colors.HexColor("#3B82F6"),  # Blue - In Progress
            colors.HexColor("#F59E0B"),  # Amber - Started
            colors.HexColor("#EF4444"),  # Red - Not Started
        ]
        for idx, col in enumerate(palette):
            pie.slices[idx].fillColor = col
        d.add(pie)
        # Inner cutout circle to create doughnut look
        d.add(Circle(120, 104, 27, fillColor=colors.white, strokeColor=colors.white))
        d.add(String(120, 106, str(total), fontName="Helvetica-Bold", fontSize=12, fillColor=colors.HexColor("#111827"), textAnchor="middle"))
        d.add(String(120, 95, "Learners", fontName="Helvetica", fontSize=6.5, fillColor=colors.HexColor("#6B7280"), textAnchor="middle"))

    # 2x2 Legend at bottom
    legend_items = [
        ("#10B981", f"Completed (100%): {completed}", 14, 34),
        ("#3B82F6", f"In Progress (50-99%): {in_progress}", 124, 34),
        ("#F59E0B", f"Started (1-49%): {started}", 14, 16),
        ("#EF4444", f"Not Started (0%): {not_started}", 124, 16),
    ]
    for hex_c, lbl, lx, ly in legend_items:
        d.add(Rect(lx, ly, 7, 7, rx=1.5, ry=1.5, fillColor=colors.HexColor(hex_c), strokeColor=None))
        d.add(String(lx + 11, ly + 1, lbl, fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#374151")))

    return d


def _build_dropoff_bar_chart(section_analytics):
    """Draws a crisp vector horizontal bar chart matching the Syllabus Dropoff Analysis chart."""
    d = Drawing(270, 195)
    d.add(Rect(0, 0, 270, 195, rx=8, ry=8, fillColor=colors.white, strokeColor=colors.HexColor("#E5E7EB"), strokeWidth=0.8))
    d.add(String(12, 178, "Syllabus Dropoff Analysis", fontName="Helvetica-Bold", fontSize=9.5, fillColor=colors.HexColor("#111827")))
    d.add(String(12, 166, "Completion rate (%) per lesson section", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#6B7280")))

    items = (section_analytics or [])[:10]
    if not items:
        d.add(String(135, 95, "No sections found in this course", fontName="Helvetica", fontSize=8, fillColor=colors.HexColor("#9CA3AF"), textAnchor="middle"))
        return d

    # Reverse order so first section appears at the top of the horizontal bar chart
    items_rev = list(reversed(items))
    labels = []
    values = []
    for item in items_rev:
        title = item["title"] or "Section"
        short = (title[:19] + "...") if len(title) > 22 else title
        labels.append(short)
        values.append(float(item.get("completion_rate", 0)))

    chart = HorizontalBarChart()
    chart.x = 104
    chart.y = 22
    chart.width = 148
    chart.height = 132
    chart.data = [values]
    chart.bars[0].fillColor = colors.HexColor("#6366F1")
    chart.bars[0].strokeColor = colors.HexColor("#6366F1")
    chart.bars[0].strokeWidth = 0
    chart.barSpacing = 1
    chart.groupSpacing = 4

    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 25
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 6.5
    chart.valueAxis.labels.fillColor = colors.HexColor("#6B7280")
    chart.valueAxis.strokeColor = colors.HexColor("#E5E7EB")
    chart.valueAxis.gridStrokeColor = colors.HexColor("#F3F4F6")
    chart.valueAxis.visibleGrid = True

    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.fillColor = colors.HexColor("#374151")
    chart.categoryAxis.labels.dx = -4
    chart.categoryAxis.strokeColor = colors.HexColor("#E5E7EB")

    d.add(chart)
    return d


def generate_course_compliance_pdf(
    course,
    total_enrollments,
    completed_enrollments,
    completion_rate,
    engagement_metrics,
    section_analytics,
    quiz_analytics,
    learner_rows,
    cohort=None,
    inclusive_summary=None,
):
    """Generates the full SETA / QCTO Compliance & Course Analytics PDF and returns raw PDF bytes."""
    buf = io.BytesIO()
    generated_str = datetime.utcnow().strftime("%d %b %Y at %H:%M UTC")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"SETA Compliance Report - {course.title}",
        author="Pace Academy",
    )

    styles = getSampleStyleSheet()
    banner_title = ParagraphStyle(
        "BannerTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.white,
        spaceAfter=3,
    )
    banner_sub = ParagraphStyle(
        "BannerSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#E0E7FF"),
    )
    sec_heading = ParagraphStyle(
        "SecHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.3,
        leading=9.5,
        textColor=colors.HexColor("#1F2937"),
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111827"),
    )
    hdr_style = ParagraphStyle(
        "TblHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.3,
        leading=9.5,
        textColor=colors.white,
    )
    kpi_lbl = ParagraphStyle(
        "KpiLbl",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
    )
    kpi_val = ParagraphStyle(
        "KpiVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#111827"),
    )
    kpi_sub = ParagraphStyle(
        "KpiSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#4B5563"),
    )

    story = []

    # 1. Branded Indigo Header Banner
    accred_id = getattr(course, "partner_accreditation_number", None) or getattr(course, "accreditation_name", None) or "N/A"
    partner_name = getattr(course, "partner_name", None) or "Pace Academy"
    instructor_name = (
        (getattr(course.teacher, "full_name", None) or getattr(course.teacher, "username", None))
        if getattr(course, "teacher", None) else "Pace Academy Educator"
    )
    cohort_line = ""
    if cohort is not None:
        org_bit = f" ({_safe(cohort.organization_name)})" if getattr(cohort, "organization_name", None) else ""
        cohort_line = f"<br/><b>Cohort / Intake:</b> {_safe(cohort.name)}{org_bit}"
    banner_table = Table(
        [[
            Paragraph("PACE ACADEMY — SETA / QCTO COMPLIANCE &amp; COURSE ANALYTICS", banner_title),
        ], [
            Paragraph(
                f"<b>Course:</b> {_safe(course.title)} &nbsp;|&nbsp; "
                f"<b>Provider:</b> {_safe(partner_name)} &nbsp;|&nbsp; "
                f"<b>Accreditation:</b> {_safe(accred_id)}<br/>"
                f"<b>Lead Instructor:</b> {_safe(instructor_name)} &nbsp;|&nbsp; "
                f"<b>Generated:</b> {generated_str}"
                f"{cohort_line}",
                banner_sub,
            )
        ]],
        colWidths=[182 * mm],
    )
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4F46E5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 11),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 7))

    # 2. 4 KPI Overview Cards (matching the web dashboard)
    active_7d = engagement_metrics.get("active_students_7days", 0)
    eng_rate = engagement_metrics.get("engagement_rate", 0.0)
    avg_sess = engagement_metrics.get("avg_session_minutes", 0.0)

    def _kpi_cell(label, val, sub, accent_hex):
        inner = Table(
            [[Paragraph(label, kpi_lbl)], [Paragraph(val, kpi_val)], [Paragraph(sub, kpi_sub)]],
            colWidths=[41 * mm],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#E5E7EB")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(accent_hex)),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, 1), 1),
        ]))
        return inner

    kpi_row = Table(
        [[
            _kpi_cell("Total Students", str(total_enrollments), "Enrolled learners", "#3B82F6"),
            _kpi_cell("Completion Rate", f"{completion_rate}%", f"{completed_enrollments} completed", "#10B981"),
            _kpi_cell("Active (7 Days)", str(active_7d), f"{eng_rate}% engagement", "#8B5CF6"),
            _kpi_cell("Avg Session Time", f"{avg_sess}", "minutes per session", "#F59E0B"),
        ]],
        colWidths=[45.5 * mm, 45.5 * mm, 45.5 * mm, 45.5 * mm],
    )
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(kpi_row)
    story.append(Spacer(1, 8))

    # 3. Side-by-Side Vector Charts (Progress Distribution Donut + Syllabus Dropoff Bar Chart)
    c_done = sum(1 for r in learner_rows if r["progress_pct"] >= 100)
    c_mid = sum(1 for r in learner_rows if 50 <= r["progress_pct"] < 100)
    c_start = sum(1 for r in learner_rows if 0 < r["progress_pct"] < 50)
    c_none = sum(1 for r in learner_rows if r["progress_pct"] <= 0)

    donut_drawing = _build_donut_chart(c_done, c_mid, c_start, c_none)
    bar_drawing = _build_dropoff_bar_chart(section_analytics)

    charts_tbl = Table(
        [[donut_drawing, bar_drawing]],
        colWidths=[86 * mm, 96 * mm],
    )
    charts_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(charts_tbl)
    story.append(Spacer(1, 7))

    # 3b. POPIA-Safe Anonymized Inclusive Learning Support Summary
    if inclusive_summary is not None:
        tot_inc = inclusive_summary.get("total_learners", total_enrollments)
        with_sup = inclusive_summary.get("with_support", 0)
        extra_t = inclusive_summary.get("extra_quiz_time", 0)
        voice_d = inclusive_summary.get("voice_dictation", 0)
        disp_a = inclusive_summary.get("assistive_display", 0)
        cap_a = inclusive_summary.get("captions_enabled", 0)
        inc_title_style = ParagraphStyle(
            "IncTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1E3A8A"),
        )
        inc_body_style = ParagraphStyle(
            "IncBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=10,
            textColor=colors.HexColor("#1E40AF"),
        )
        scope_label = f"cohort ({_safe(cohort.name)})" if cohort is not None else "course"
        inc_tbl = Table(
            [[
                Paragraph(
                    f"INCLUSIVE LEARNING SUPPORT SUMMARY (POPIA-ANONYMIZED) — {with_sup} of {tot_inc} learners in this {scope_label} have active accessibility support/concessions",
                    inc_title_style,
                )
            ], [
                Paragraph(
                    f"<b>Quiz Extra Time Concessions:</b> {extra_t} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Voice-to-Text Dictation:</b> {voice_d} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Assistive Display / Read Aloud:</b> {disp_a} &nbsp;&nbsp;|&nbsp;&nbsp; "
                    f"<b>Captions / Transcripts:</b> {cap_a}<br/>"
                    f"<font color='#475569' size='6.7'><i>Aggregate counts only for B-BBEE PwD &amp; SETA/QCTO compliance auditing — zero individual learner identities or medical details disclosed.</i></font>",
                    inc_body_style,
                )
            ]],
            colWidths=[182 * mm],
        )
        inc_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#BFDBFE")),
            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#2563EB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, 1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ]))
        story.append(inc_tbl)
        story.append(Spacer(1, 7))

    # 4. Quiz Performance Summary (if course has quizzes)
    if quiz_analytics:
        story.append(Paragraph("1. Quiz Performance Summary", sec_heading))
        q_data = [[
            Paragraph("Quiz Title", hdr_style),
            Paragraph("Attempts", hdr_style),
            Paragraph("Average Score", hdr_style),
            Paragraph("Highest", hdr_style),
            Paragraph("Lowest", hdr_style),
        ]]
        for q in quiz_analytics:
            q_data.append([
                Paragraph(_safe(q["title"]), cell_bold),
                Paragraph(str(q["attempts"]), cell_style),
                Paragraph(f"{q['avg_score']}%", cell_style),
                Paragraph(f"{q['max_score']}%", cell_style),
                Paragraph(f"{q['min_score']}%", cell_style),
            ])
        q_tbl = Table(q_data, colWidths=[82 * mm, 22 * mm, 28 * mm, 25 * mm, 25 * mm], repeatRows=1)
        q_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(q_tbl)
        story.append(Spacer(1, 8))

    # 5. SETA / QCTO Learner Compliance & Attendance Logbook Table
    sec_num = "2" if quiz_analytics else "1"
    story.append(Paragraph(f"{sec_num}. SETA / QCTO Learner Compliance &amp; Attendance Logbook", sec_heading))

    l_data = [[
        Paragraph("Learner &amp; Email", hdr_style),
        Paragraph("SA ID / Passport", hdr_style),
        Paragraph("Enrolled / Status", hdr_style),
        Paragraph("Progress", hdr_style),
        Paragraph("Logbook Time", hdr_style),
        Paragraph("Avg Quiz", hdr_style),
        Paragraph("Tasks", hdr_style),
        Paragraph("Last Active", hdr_style),
    ]]

    if not learner_rows:
        l_data.append([Paragraph("No learners enrolled in this course yet.", cell_style)] + [Paragraph("", cell_style)] * 7)
    else:
        for row in learner_rows:
            name_html = f"<b>{_safe(row['student_name'])}</b><br/><font color='#6B7280' size='6.5'>{_safe(row['email'])}</font>"
            status_color = "#059669" if row["status"] == "Completed" else ("#DC2626" if row["status"] == "Blocked" else "#2563EB")
            status_html = f"{_safe(row['enrolled_date'])}<br/><font color='{status_color}'><b>{_safe(row['status'])}</b></font>"
            prog_html = f"<b>{row['progress_pct']}%</b><br/><font color='#6B7280' size='6.5'>{row['completed_sections']}/{row['total_sections']} lessons</font>"
            time_html = f"{row['total_hours']}h<br/><font color='#6B7280' size='6.5'>({row['total_mins']}m)</font>"
            quiz_str = f"{row['avg_quiz_score']}%" if row["avg_quiz_score"] != "N/A" else "N/A"
            assign_str = f"{row['assignments_submitted']}/{row['total_assignments']}"
            l_data.append([
                Paragraph(name_html, cell_style),
                Paragraph(_safe(row["id_number"]), cell_style),
                Paragraph(status_html, cell_style),
                Paragraph(prog_html, cell_style),
                Paragraph(time_html, cell_style),
                Paragraph(quiz_str, cell_style),
                Paragraph(assign_str, cell_style),
                Paragraph(_safe(row["last_active"]), cell_style),
            ])

    l_tbl = Table(
        l_data,
        colWidths=[42 * mm, 24 * mm, 23 * mm, 20 * mm, 19 * mm, 15 * mm, 14 * mm, 25 * mm],
        repeatRows=1,
    )
    l_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(l_tbl)

    def _draw_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(
            14 * mm,
            9 * mm,
            f"Generated on {generated_str}  •  Official Pace Academy SETA / QCTO Compliance Report",
        )
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buf.getvalue()
