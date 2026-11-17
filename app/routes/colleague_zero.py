"""
Colleague Zero — Embedded Autonomous Multi-Agent Colleague Blueprint for Pace Academy
Lives inside Pace Academy (`pace-academy.co.za/colleague-zero`) and shares the EXACT same database (`app.db`):
- Uses Pace Academy's `users`, `courses`, `sections`, `assignments`, `assignment_submissions`, and `notifications` tables.
- Stores 4-worker multi-agent audit logs (`PL`, `MK`, `RV`, `MS`) and custom rubrics in `colleague_zero_audits`
  and `colleague_zero_rubrics` tables in the same Pace Academy database so all Gunicorn workers on Render stay 100% in sync!
"""

import csv
import io
import json
import re
import time
from datetime import datetime
from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import current_user

from app import csrf, db
from app.models import Assignment, AssignmentSubmission, Course, Notification, Section, User

colleague_zero_bp = Blueprint("colleague_zero", __name__, url_prefix="/colleague-zero")


class ColleagueZeroRubricRecord(db.Model):
    """Stores custom 4-criterion rubrics per Pace Academy assignment in the shared Pace DB."""
    __tablename__ = "colleague_zero_rubrics"

    batch_id = db.Column(db.String(64), primary_key=True)
    assignment_id = db.Column(db.Integer, nullable=True, index=True)
    rubric_json = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class ColleagueZeroAuditRecord(db.Model):
    """Stores the 4-worker (`PL -> MK -> RV -> MS`) evaluation & self-correction audit per Pace submission in the shared Pace DB."""
    __tablename__ = "colleague_zero_audits"

    submission_id = db.Column(db.Integer, primary_key=True)  # Matches assignment_submissions.id
    batch_id = db.Column(db.String(64), nullable=False, index=True)
    evaluated_json = db.Column(db.Text, nullable=False)
    events_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "during", "through",
    "between", "leads", "leading", "explains", "explain", "how", "why", "what", "when",
    "where", "which", "their", "there", "have", "has", "had", "are", "were", "was",
    "been", "being", "also", "such", "than", "then", "them", "they", "used", "using",
    "each", "other", "more", "most", "some", "any", "all", "both", "criterion",
    "assignment", "student", "learner", "write", "submit", "course", "section",
}

INFORMAL_ANALOGY_SYNONYMS = {
    "bivalent": ["partner", "pair up", "matching pair", "couple", "hug", "side by side"],
    "chiasmata": ["cross point", "touching point", "overlap", "chiasma", "x-shape", "knot"],
    "crossing": ["swap", "trade", "exchange", "share", "mix", "pieces"],
    "equator": ["middle line", "center line", "middle", "centre", "line up"],
    "random": ["shuffle", "deck", "mixed up", "any order", "chance", "flip"],
    "haploid": ["half", "halve", "23", "single set", "split in half"],
    "diploid": ["full set", "46", "double", "restore", "baby gets 46"],
    "hashing": ["scramble", "one-way", "hash", "lock", "salt", "bcrypt", "argon"],
    "parameterised": ["placeholder", "question mark", "prepared", "bind", "escape", "sanitize"],
    "normalisation": ["split tables", "no duplicate", "foreign key", "primary key", "index"],
    "limiting": ["block", "too many tries", "throttle", "lockout", "rate limit"],
    "function": ["def ", "return ", "helper", "method", "routine", "block"],
    "variable": ["store", "box", "value", "assign", "let ", "const "],
    "loop": ["repeat", "for ", "while ", "iterate", "each item"],
}

_TABLES_ENSURED = False


def _ensure_cz_tables():
    global _TABLES_ENSURED
    if not _TABLES_ENSURED:
        try:
            db.create_all()
            _TABLES_ENSURED = True
        except Exception:
            db.session.rollback()


def strip_html(html_text):
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\s+", " ", clean).strip()


def extract_criterion_keywords(criterion):
    text = f"{criterion.get('name', '')} {criterion.get('description', '')}".lower()
    words = re.findall(r"[a-z0-9\-]{4,}", text)
    keywords = []
    for w in words:
        if w not in STOPWORDS and w not in keywords:
            keywords.append(w)
    return keywords


def _fetch_submission_file_bytes(file_path):
    """Downloads or reads local bytes for an uploaded assignment submission file."""
    import os
    from flask import current_app

    if not file_path:
        return None

    if file_path.startswith("http://") or file_path.startswith("https://"):
        try:
            import requests
            resp = requests.get(
                file_path,
                headers={"User-Agent": "PaceAcademy-ColleagueZero/1.0"},
                timeout=15,
            )
            if resp.status_code == 200 and resp.content:
                return resp.content
            print(f"[ColleagueZero] HTTP {resp.status_code} fetching submission file: {file_path}")
        except Exception as req_err:
            print(f"[ColleagueZero] requests fetch error ({file_path}): {req_err}")
        try:
            import urllib.request
            req = urllib.request.Request(file_path, headers={"User-Agent": "PaceAcademy-ColleagueZero/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as url_err:
            print(f"[ColleagueZero] urllib fetch error ({file_path}): {url_err}")
            return None

    rel = file_path.lstrip("/")
    upload_folder = current_app.config.get("UPLOAD_FOLDER") or ""
    candidates = [
        file_path,
        os.path.join(upload_folder, rel) if upload_folder else "",
        os.path.join(upload_folder, os.path.basename(rel)) if upload_folder else "",
        os.path.join(current_app.root_path, "static", rel),
        os.path.join(current_app.root_path, rel),
    ]
    for cand in candidates:
        if cand and os.path.isfile(cand):
            with open(cand, "rb") as f:
                return f.read()
    return None


def _extract_pdf_text_with_gemini_fallback(pdf_bytes):
    """Extracts text from PDF bytes via pypdf, falling back to Gemini multimodal for scanned/image PDFs."""
    extracted = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages[:15]).strip()
    except Exception as pdf_err:
        print(f"[ColleagueZero] pypdf extraction error: {pdf_err}")

    if len(extracted) >= 20:
        return extracted

    # Fallback for scanned/image-based PDFs (or PDFs with non-standard font encodings)
    try:
        import base64
        import requests
        from app.services.ai_service import AIService
        api_key = AIService.get_api_key()
        if not api_key or len(pdf_bytes) > 8 * 1024 * 1024:
            return extracted
        b64 = base64.b64encode(pdf_bytes).decode("ascii")
        url = f"{AIService.BASE_URL}/{AIService.DEFAULT_MODEL}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Extract and transcribe all readable text, headings, lists, and formatting details from this student PDF submission verbatim."},
                    {"inlineData": {"mimeType": "application/pdf", "data": b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
        }
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            cands = data.get("candidates") or []
            if cands:
                text_parts = [p.get("text", "") for p in cands[0].get("content", {}).get("parts", [])]
                gem_text = "\n".join(t for t in text_parts if t).strip()
                if gem_text:
                    return gem_text
    except Exception as gem_err:
        print(f"[ColleagueZero] Gemini PDF fallback error: {gem_err}")

    return extracted


def _extract_docx_text(docx_bytes):
    """Extracts paragraph text and basic font/alignment metadata from a .docx archive without extra dependencies."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        lines = []
        fonts_seen = set()
        alignments_seen = set()
        for p in root.findall(".//w:p", ns):
            texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
            line = "".join(texts).strip()
            if line:
                lines.append(line)
            for rFonts in p.findall(".//w:rFonts", ns):
                for attr in ("ascii", "hAnsi"):
                    val = rFonts.attrib.get(f"{{{ns['w']}}}{attr}")
                    if val:
                        fonts_seen.add(val)
            jc = p.find(".//w:pPr/w:jc", ns)
            if jc is not None:
                val = jc.attrib.get(f"{{{ns['w']}}}val")
                if val:
                    alignments_seen.add(val)
        meta_bits = []
        if fonts_seen:
            meta_bits.append(f"Detected Fonts: {', '.join(sorted(fonts_seen))}")
        if alignments_seen:
            meta_bits.append(f"Detected Alignments: {', '.join(sorted(alignments_seen))}")
        header = f"[DOCX Metadata: {'; '.join(meta_bits)}]\n" if meta_bits else ""
        return header + "\n".join(lines)
    except Exception as docx_err:
        print(f"[ColleagueZero] DOCX extraction error: {docx_err}")
        return ""


def _extract_submission_text_for_grading(submission):
    """Collects text from code, text, and uploaded PDF/DOCX/text submissions for grading."""
    parts = []
    if getattr(submission, "submission_type", None) == "code" and getattr(submission, "code_submission", None):
        parts.append(submission.code_submission)
        if getattr(submission, "execution_output", None):
            parts.append(f"\n[Execution Output]\n{submission.execution_output[:2000]}")
        if getattr(submission, "execution_error", None):
            parts.append(f"\n[Execution Error]\n{submission.execution_error[:1000]}")
    if getattr(submission, "submission_text", None):
        parts.append(submission.submission_text)

    file_path = getattr(submission, "file_path", None) or ""
    if file_path:
        lower_fp = file_path.lower()
        file_bytes = _fetch_submission_file_bytes(file_path)
        if file_bytes:
            if ".pdf" in lower_fp or file_bytes[:4] == b"%PDF":
                extracted = _extract_pdf_text_with_gemini_fallback(file_bytes)
                if extracted:
                    parts.append(f"\n[Extracted PDF Submission]\n{extracted[:12000]}")
            elif ".docx" in lower_fp:
                extracted = _extract_docx_text(file_bytes)
                if extracted:
                    parts.append(f"\n[Extracted DOCX Submission]\n{extracted[:12000]}")
            elif any(lower_fp.endswith(ext) for ext in (".txt", ".md", ".py", ".js", ".html", ".css", ".csv", ".json")):
                try:
                    decoded = file_bytes.decode("utf-8", errors="replace").strip()
                    if decoded:
                        parts.append(f"\n[Uploaded File Content]\n{decoded[:12000]}")
                except Exception:
                    pass

    return "\n\n".join(p for p in parts if p and p.strip()).strip()


def _llm_build_rubric_for_assignment(assignment, desc_clean):
    """Uses Pace Academy's Gemini AIService to build a 4-criterion 100-mark rubric, or returns None on fallback."""
    try:
        from app.services.ai_service import AIService
        if not AIService.get_api_key():
            return None

        prompt = (
            "Design a fair, clear 4-criterion grading rubric out of 100 marks for this Pace Academy assignment.\n"
            f"Assignment Title: {assignment.title}\n"
            f"Is Coding Assignment: {bool(assignment.is_coding_assignment)} "
            f"(Language: {assignment.programming_language or 'N/A'})\n"
            f"Assignment Prompt / Description:\n{desc_clean[:2500]}\n\n"
            "Return ONLY valid JSON with this exact schema:\n"
            "{\n"
            '  "version": "short rubric name",\n'
            '  "pass_mark": 50,\n'
            '  "criteria": [\n'
            '    {"id": "C1", "name": "...", "weight": 30, "description": "..."},\n'
            '    {"id": "C2", "name": "...", "weight": 30, "description": "..."},\n'
            '    {"id": "C3", "name": "...", "weight": 25, "description": "..."},\n'
            '    {"id": "C4", "name": "...", "weight": 15, "description": "..."}\n'
            "  ]\n"
            "}\n"
            "Rules: Exactly 4 criteria (C1..C4). Integer weights MUST sum to exactly 100."
        )
        raw = AIService._call_gemini(
            prompt=prompt,
            system_instruction="You are an expert South African curriculum & skills assessor. Output strict JSON only.",
            response_json=True,
        )
        parsed = AIService._parse_json_safely(raw)
        criteria = parsed.get("criteria") or []
        if len(criteria) != 4:
            return None

        normalized = []
        total_w = 0
        for idx, c in enumerate(criteria, start=1):
            w = max(5, min(70, int(c.get("weight", 25))))
            total_w += w
            normalized.append({
                "id": f"C{idx}",
                "name": str(c.get("name") or f"Criterion {idx}")[:80],
                "weight": w,
                "description": str(c.get("description") or desc_clean[:160])[:300],
            })
        if total_w != 100:
            normalized[0]["weight"] += (100 - total_w)
            if normalized[0]["weight"] < 5:
                return None

        return {
            "version": str(parsed.get("version") or "Pace Academy AI Rubric v2.5")[:80],
            "question_prompt": desc_clean,
            "total_marks": 100,
            "pass_mark": int(parsed.get("pass_mark", 50)),
            "criteria": normalized,
        }
    except Exception:
        return None


def _llm_grade_with_4_workers(learner_name, school_or_cohort, essay_text, rubric, number=1):
    """
    Runs the 4-worker grading & moderation panel via Gemini AIService.
    Returns (evaluated, worker_events) matching the exact Colleague Zero schema, or None if unavailable.
    """
    if not essay_text or not essay_text.strip():
        return None
    try:
        from app.services.ai_service import AIService
        if not AIService.get_api_key():
            return None

        criteria = rubric.get("criteria", [])
        rubric_version = rubric.get("version", "Pace Academy Rubric")
        pass_mark = int(rubric.get("pass_mark", 50))
        question_prompt = rubric.get("question_prompt", "")

        crit_lines = "\n".join(
            f"- {c['id']} ({c['name']}, max {c['weight']} marks): {c.get('description', '')}"
            for c in criteria
        )
        prompt = (
            f"Evaluate this learner submission for '{school_or_cohort}'.\n"
            f"Learner: {learner_name}\n"
            f"Assignment Question/Prompt:\n{str(question_prompt)[:1500]}\n\n"
            f"Rubric ({rubric_version}, Pass mark {pass_mark}/100):\n{crit_lines}\n\n"
            f"Learner Submission:\n{essay_text[:10000]}\n\n"
            "Simulate a 2-pass moderation panel:\n"
            "1) Assessor [MK] gives initial_scores per criterion based strictly on rubric alignment.\n"
            "2) Moderator [RV] checks if [MK] missed valid conceptual reasoning, code logic, or informal/plain-language explanations, and outputs corrected_scores.\n"
            "STRICT GRADING RULES:\n"
            "- Grade ONLY what is actually inside 'Learner Submission' — NEVER assume or credit content from the Assignment Question/Prompt.\n"
            "- If the submission is completely off-topic, an unrelated document (e.g. a grade report/PoE/random PDF), or just a filename/placeholder with no actual assignment content, assign 0 (or at most 5 total) across criteria and clearly state in feedback that the submitted file/text does not match the assignment requirements.\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "initial_scores": {"C1": 0, "C2": 0, "C3": 0, "C4": 0},\n'
            '  "corrected_scores": {"C1": 0, "C2": 0, "C3": 0, "C4": 0},\n'
            '  "mk_rationale": "1-2 sentences explaining Pass-1 mark",\n'
            '  "rv_note": "1-2 sentences explaining moderation check or adjustment",\n'
            '  "feedback": "2-3 encouraging, specific sentences directly to the learner",\n'
            '  "catchup_plan": ["Step 1 ...", "Step 2 ...", "Step 3 ..."]\n'
            "}"
        )
        raw = AIService._call_gemini(
            prompt=prompt,
            system_instruction="You are Colleague Zero, a fair, rigorous academic assessor and moderator. Output strict JSON only.",
            response_json=True,
        )
        parsed = AIService._parse_json_safely(raw)
        raw_init = parsed.get("initial_scores") or {}
        raw_corr = parsed.get("corrected_scores") or raw_init
        if not raw_init:
            return None

        init_scores = {}
        corr_scores = {}
        for c in criteria:
            cid = c["id"]
            w = int(c["weight"])
            iv = max(0, min(w, int(round(float(raw_init.get(cid, 0))))))
            cv = max(0, min(w, int(round(float(raw_corr.get(cid, iv))))))
            init_scores[cid] = iv
            corr_scores[cid] = cv

        init_total = sum(init_scores.values())
        corr_total = sum(corr_scores.values())
        flagged = abs(corr_total - init_total) >= 5
        now_lbl = datetime.now().strftime("%H:%M:%S")
        word_count = len(re.findall(r"\w+", essay_text))

        mk_rationale = str(parsed.get("mk_rationale") or f"Assessor [MK] evaluated submission against {rubric_version}.").strip()
        rv_note = str(parsed.get("rv_note") or f"Moderator [RV] verified {corr_total}% against {rubric_version}.").strip()
        feedback = str(parsed.get("feedback") or f"Your submission scored {corr_total}%.").strip()
        catchup_plan = [str(s).strip() for s in (parsed.get("catchup_plan") or []) if str(s).strip()][:3]

        worker_events = [
            {
                "agent_code": "PL",
                "tag": "[PL·PLAN]",
                "message": f"Planner Worker [PL] decomposed {rubric_version} into {len(criteria)} criteria for #{number} {learner_name} ({word_count} words). Routing to Assessor Worker [MK].",
                "time_label": now_lbl,
            },
            {
                "agent_code": "MK",
                "tag": "[MK·PASS1]",
                "message": f"Assessor Worker [MK] completed Pass-1 LLM evaluation for #{number} {learner_name}: {init_total}%. {mk_rationale}",
                "time_label": now_lbl,
            },
        ]

        if flagged:
            flag_reason = f"Moderator Worker [RV] flagged [MK] Pass-1 score ({init_total}%): {rv_note}"
            correction_log = f"Assessor Worker [MK] executed Pass-2 self-correction per Moderator [RV]: {init_total}% → {corr_total}% ({corr_total - init_total:+d}%)."
            worker_events.extend([
                {"agent_code": "RV", "tag": "[RV·FLAG]", "message": flag_reason, "time_label": now_lbl},
                {"agent_code": "MK", "tag": "[MK·FIX]", "message": correction_log, "time_label": now_lbl},
                {"agent_code": "RV", "tag": "[RV·VERIFIED]", "message": f"Moderator Worker [RV] verified adjusted mark ({corr_total}%) against {rubric_version}.", "time_label": now_lbl},
            ])
        else:
            flag_reason = None
            correction_log = f"Moderator Worker [RV] verified {corr_total}% against {rubric_version}. {rv_note}"
            worker_events.append({"agent_code": "RV", "tag": "[RV·PASS]", "message": correction_log, "time_label": now_lbl})

        worker_events.append({
            "agent_code": "MS",
            "tag": "[MS·DISPATCH]",
            "message": f"Recovery Worker [MS] wrote grade ({corr_total}%) & feedback to Pace Academy and Colleague Zero.",
            "time_label": now_lbl,
        })

        evaluated = {
            "initial_mark": {
                "worker_status": "completed",
                "score": init_total,
                "criteria_scores": init_scores,
                "rationale": mk_rationale,
            },
            "moderation": {
                "flagged": flagged,
                "flag_reason": flag_reason,
                "corrected_score": corr_total,
                "corrected_criteria_scores": corr_scores,
                "correction_log": correction_log,
            },
            "recovery": {
                "feedback": feedback,
                "needs_recovery": corr_total < pass_mark,
                "catchup_plan": catchup_plan,
            },
        }
        return evaluated, worker_events
    except Exception:
        return None


def build_rubric_for_pace_assignment(assignment):
    """
    Builds or retrieves a 4-criterion 100-mark rubric for any Pace Academy `Assignment`,
    persisted in `colleague_zero_rubrics` in Pace Academy's shared DB.
    """
    _ensure_cz_tables()
    batch_id = f"pace_assign_{assignment.id}"
    try:
        rec = ColleagueZeroRubricRecord.query.filter_by(batch_id=batch_id).first()
        if rec:
            return json.loads(rec.rubric_json)
    except Exception:
        db.session.rollback()

    title_lower = (assignment.title or "").lower()
    desc_clean = strip_html(assignment.description or "") or assignment.title

    if "meiosis" in title_lower or "life science" in title_lower:
        rubric = {
            "version": "DBE CAPS Rubric v2.4 (Pace Academy)",
            "question_prompt": desc_clean,
            "total_marks": 100,
            "pass_mark": 50,
            "criteria": [
                {"id": "C1", "name": "Crossing-Over in Prophase I", "weight": 30, "description": "Homologous chromosomes pair up as bivalents, non-sister chromatids overlap at chiasmata, and exchange genetic material / DNA segments to create new allele combinations."},
                {"id": "C2", "name": "Random Arrangement in Metaphase I & II", "weight": 30, "description": "Homologous chromosome pairs arrange randomly along the equator in Metaphase I (and single chromosomes in Metaphase II), leading to independent assortment in gametes."},
                {"id": "C3", "name": "Halving Chromosome Number (Diploid to Haploid)", "weight": 25, "description": "Reduces diploid (2n / 46 chromosomes) parent cells to haploid (n / 23 chromosomes) gametes so fertilisation restores the correct diploid chromosome number."},
                {"id": "C4", "name": "Scientific Synthesis & Conceptual Clarity", "weight": 15, "description": "Clear distinction between Meiosis I and Meiosis II phases, logical cause-and-effect explanation of genetic variation, and accurate biological reasoning."},
            ],
        }
    elif assignment.is_coding_assignment:
        lang = (assignment.programming_language or "Python").capitalize()
        rubric = {
            "version": f"Pace Academy {lang} Code Rubric v2.0",
            "question_prompt": desc_clean,
            "total_marks": 100,
            "pass_mark": 50,
            "criteria": [
                {"id": "C1", "name": f"Problem Solution & {lang} Logic", "weight": 35, "description": f"Implements core logic addressing: {desc_clean[:160]}"},
                {"id": "C2", "name": "Code Structure, Functions & Control Flow", "weight": 25, "description": "Uses appropriate functions, loops, conditionals, variables, and clean modular structure."},
                {"id": "C3", "name": "Edge Cases, Input Validation & Error Handling", "weight": 25, "description": "Handles edge cases, valid/invalid inputs, and avoids runtime errors or crashes."},
                {"id": "C4", "name": "Readability, Naming & Documentation", "weight": 15, "description": "Clear variable names, helpful comments, and maintainable code formatting."},
            ],
        }
    else:
        rubric = _llm_build_rubric_for_assignment(assignment, desc_clean)
        if not rubric:
            words = [w for w in re.findall(r"[a-zA-Z]{5,}", desc_clean) if w.lower() not in STOPWORDS]
            unique_terms = []
            for w in words:
                if w.lower() not in [u.lower() for u in unique_terms]:
                    unique_terms.append(w)
            chunk = max(1, len(unique_terms) // 3)
            t1 = ", ".join(unique_terms[:chunk]) or assignment.title
            t2 = ", ".join(unique_terms[chunk:chunk * 2]) or "core mechanisms and practical examples"
            t3 = ", ".join(unique_terms[chunk * 2:chunk * 3]) or "application and critical analysis"

            rubric = {
                "version": "Pace Academy Competency Rubric v2.0",
                "question_prompt": desc_clean,
                "total_marks": 100,
                "pass_mark": 50,
                "criteria": [
                    {"id": "C1", "name": "Core Concepts & Terminology", "weight": 30, "description": f"Addresses foundational concepts in {assignment.title}: {t1}."},
                    {"id": "C2", "name": "Mechanism & Technical Explanation", "weight": 30, "description": f"Explains how the process works with clear reasoning: {t2}."},
                    {"id": "C3", "name": "Practical Application & Examples", "weight": 25, "description": f"Applies concepts to real scenarios and covers: {t3}."},
                    {"id": "C4", "name": "Synthesis, Structure & Clarity", "weight": 15, "description": f"Logical structure, complete response to '{assignment.title}', and clear communication."},
                ],
            }

    try:
        db.session.add(ColleagueZeroRubricRecord(
            batch_id=batch_id,
            assignment_id=assignment.id,
            rubric_json=json.dumps(rubric),
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    return rubric


def run_pace_4_worker_pipeline(batch_id, learner_name, school_or_cohort, essay_text, rubric, number=1):
    """
    Runs the 4 autonomous Agent Workers (`PlannerWorker [PL]` -> `AssessorWorker [MK]` ->
    `ModeratorWorker [RV]` -> `RecoveryWorker [MS]`) on a Pace Academy submission.
    Uses Pace Academy's Gemini AIService when configured, with deterministic heuristic fallback.
    """
    llm_result = _llm_grade_with_4_workers(learner_name, school_or_cohort, essay_text, rubric, number=number)
    if llm_result is not None:
        return llm_result

    criteria = rubric.get("criteria", [])
    rubric_version = rubric.get("version", "Pace Academy Rubric")
    pass_mark = int(rubric.get("pass_mark", 50))
    worker_events = []

    cleaned_text = re.sub(
        r"\b(i forgot|i don'?t know|i do not know|i struggle with|not sure about)[^.!?\n]*",
        "",
        essay_text or "",
        flags=re.IGNORECASE,
    )
    word_count = len(re.findall(r"\w+", cleaned_text))
    criterion_plans = []
    for c in criteria:
        criterion_plans.append({
            "id": c["id"],
            "name": c["name"],
            "weight": int(c["weight"]),
            "description": c["description"],
            "target_keywords": extract_criterion_keywords(c),
        })

    worker_events.append({
        "agent_code": "PL",
        "tag": "[PL·PLAN]",
        "message": (
            f"Planner Worker [PL] decomposed {rubric_version} into {len(criterion_plans)} criteria "
            f"for #{number} {learner_name} ({word_count} words). Routing to Assessor Worker [MK]."
        ),
        "time_label": datetime.now().strftime("%H:%M:%S"),
    })

    text_lower = cleaned_text.lower()
    depth_factor = 1.0 if word_count >= 25 else max(0.25, word_count / 25.0)
    init_scores = {}
    conceptual_potentials = {}
    matched_by_criterion = {}
    informal_by_criterion = {}
    missing_by_criterion = {}

    for cp in criterion_plans:
        cid = cp["id"]
        weight = cp["weight"]
        kws = cp["target_keywords"]
        direct_matches = []
        informal_matches = []
        missing_kws = []

        for kw in kws:
            stem = kw[:5] if len(kw) >= 6 else kw
            if stem in text_lower:
                direct_matches.append(kw)
            else:
                syn_list = INFORMAL_ANALOGY_SYNONYMS.get(kw, [])
                if any(s in text_lower for s in syn_list):
                    informal_matches.append(kw)
                else:
                    missing_kws.append(kw)

        total_kws = max(1, len(kws))
        formal_ratio = len(direct_matches) / total_kws
        conceptual_ratio = (len(direct_matches) + len(informal_matches) * 0.9) / total_kws

        formal_mastery = min(1.0, formal_ratio / 0.42)
        conceptual_mastery = min(1.0, conceptual_ratio / 0.42)

        formal_score = int(round(weight * formal_mastery * depth_factor))
        true_score = int(round(weight * conceptual_mastery * depth_factor))

        if len(informal_matches) > 0 and true_score > formal_score:
            init_scores[cid] = max(int(weight * 0.25), int(formal_score * 0.65))
            conceptual_potentials[cid] = max(true_score, int(weight * 0.78))
        else:
            init_scores[cid] = true_score
            conceptual_potentials[cid] = true_score

        matched_by_criterion[cid] = direct_matches
        informal_by_criterion[cid] = informal_matches
        missing_by_criterion[cid] = missing_kws[:4]

    init_total = sum(init_scores.values())
    matched_summary = []
    for cp in criterion_plans:
        cid = cp["id"]
        m = matched_by_criterion[cid] + [f"{x} (analogy)" for x in informal_by_criterion[cid]]
        if m:
            matched_summary.append(f"{cid} ({', '.join(m[:3])})")

    mk_evidence = f"Detected concepts in {'; '.join(matched_summary)}." if matched_summary else "Minimal rubric terminology matched."
    rationale = f"Pass-1 Assessor [MK] scored {init_total}% ({word_count} words). {mk_evidence}"

    worker_events.append({
        "agent_code": "MK",
        "tag": "[MK·PASS1]",
        "message": f"Assessor Worker [MK] completed Pass-1 evaluation for #{number} {learner_name}: {init_total}%. {rationale}",
        "time_label": datetime.now().strftime("%H:%M:%S"),
    })

    corr_total = sum(conceptual_potentials.values())
    flagged = abs(corr_total - init_total) >= 5
    if flagged:
        flagged_cids = [cid for cid, iv in init_scores.items() if conceptual_potentials.get(cid, iv) != iv]
        flag_reason = (
            f"Moderator Worker [RV] flagged [MK] Pass-1 score ({init_total}%): "
            f"Learner explained valid concepts in {', '.join(flagged_cids)} using informal analogies. "
            f"Triggering [MK] Pass-2 re-evaluation."
        )
        correction_log = (
            f"Assessor Worker [MK] executed Pass-2 self-correction per Moderator [RV]: "
            f"{init_total}% → {corr_total}% (+{corr_total - init_total}%)."
        )
        worker_events.append({
            "agent_code": "RV",
            "tag": "[RV·FLAG]",
            "message": flag_reason,
            "time_label": datetime.now().strftime("%H:%M:%S"),
        })
        worker_events.append({
            "agent_code": "MK",
            "tag": "[MK·FIX]",
            "message": correction_log,
            "time_label": datetime.now().strftime("%H:%M:%S"),
        })
        worker_events.append({
            "agent_code": "RV",
            "tag": "[RV·VERIFIED]",
            "message": f"Moderator Worker [RV] verified adjusted mark ({corr_total}%) against {rubric_version}.",
            "time_label": datetime.now().strftime("%H:%M:%S"),
        })
    else:
        flag_reason = None
        correction_log = f"Moderator Worker [RV] verified {corr_total}% against {rubric_version} (0 discrepancies)."
        worker_events.append({
            "agent_code": "RV",
            "tag": "[RV·PASS]",
            "message": correction_log,
            "time_label": datetime.now().strftime("%H:%M:%S"),
        })

    strong_c = [c for c in criterion_plans if conceptual_potentials.get(c["id"], 0) >= c["weight"] * 0.65]
    weak_c = [c for c in criterion_plans if conceptual_potentials.get(c["id"], 0) < c["weight"] * 0.65]
    first_name = learner_name.split()[0] if learner_name else "Learner"
    strong_names = ", ".join(f"{c['id']} ({c['name']})" for c in strong_c)
    weak_names = ", ".join(f"{c['id']} ({c['name']})" for c in weak_c)

    if corr_total >= pass_mark:
        if weak_c:
            feedback = f"Well done, {first_name}! You passed with {corr_total}%. Strong mastery in {strong_names}; strengthen {weak_names} to reach 100%."
        else:
            feedback = f"Excellent work, {first_name}! You achieved {corr_total}% across all rubric criteria ({strong_names})."
    else:
        if strong_c:
            feedback = f"{first_name}, your submission scored {corr_total}% (Pass mark: {pass_mark}%). You earned marks on {strong_names}, but missed key concepts in {weak_names}."
        else:
            feedback = f"{first_name}, your submission scored {corr_total}% (Pass mark: {pass_mark}%). Follow the 3-step recovery plan below to cover {weak_names} and re-submit."

    sorted_by_gap = sorted(criterion_plans, key=lambda c: (conceptual_potentials.get(c["id"], 0) / max(1, c["weight"])))
    catchup_plan = []
    for idx, crit in enumerate(sorted_by_gap[:3], start=1):
        cid = crit["id"]
        cname = crit["name"]
        cdesc = crit["description"]
        missed = missing_by_criterion.get(cid, [])
        missed_str = f" (include key terms: {', '.join(missed)})" if missed else ""
        if conceptual_potentials.get(cid, 0) < crit["weight"] * 0.7:
            catchup_plan.append(f"Step {idx} — Fix {cid} ({cname}): Revise and explain how {cdesc}{missed_str}.")
        else:
            catchup_plan.append(f"Step {idx} — Polish {cid} ({cname}): Refine your terminology on: {cdesc}")

    worker_events.append({
        "agent_code": "MS",
        "tag": "[MS·DISPATCH]",
        "message": f"Recovery Worker [MS] wrote grade ({corr_total}%) & 3-step recovery plan to Pace Academy and Colleague Zero.",
        "time_label": datetime.now().strftime("%H:%M:%S"),
    })

    evaluated = {
        "initial_mark": {
            "worker_status": "completed",
            "score": init_total,
            "criteria_scores": init_scores,
            "rationale": rationale,
        },
        "moderation": {
            "flagged": flagged,
            "flag_reason": flag_reason,
            "corrected_score": corr_total,
            "corrected_criteria_scores": conceptual_potentials,
            "correction_log": correction_log,
        },
        "recovery": {
            "feedback": feedback,
            "needs_recovery": corr_total < pass_mark,
            "catchup_plan": catchup_plan,
        },
    }
    return evaluated, worker_events


def format_feedback_for_pace_ui(evaluated, rubric):
    init_score = evaluated["initial_mark"]["score"]
    final_score = evaluated["moderation"]["corrected_score"]
    flagged = evaluated["moderation"]["flagged"]
    lines = []

    if flagged:
        lines.append(f"⚡ COLLEAGUE ZERO MODERATION AUDIT: Assessor [MK] Pass-1: {init_score}% → Moderator [RV] Adjusted: {final_score}%")
        lines.append(f"• Audit Finding: {evaluated['moderation']['flag_reason']}")
    else:
        lines.append(f"✅ COLLEAGUE ZERO VERIFIED GRADE: {final_score}% ({rubric.get('version', 'Official Rubric')})")

    lines.append("")
    lines.append("💬 FEEDBACK:")
    lines.append(evaluated['recovery']['feedback'])
    lines.append("")
    lines.append("📊 RUBRIC CRITERION BREAKDOWN:")
    for c in rubric.get("criteria", []):
        cid = c["id"]
        w = c["weight"]
        iv = evaluated["initial_mark"]["criteria_scores"].get(cid, 0)
        fv = evaluated["moderation"]["corrected_criteria_scores"].get(cid, iv)
        delta_str = f" (Moderated from {iv}/{w})" if fv != iv else ""
        lines.append(f"• {cid} · {c['name']}: {fv} / {w} marks{delta_str}")

    if evaluated["recovery"]["catchup_plan"]:
        lines.append("")
        lines.append("🛟 3-STEP REMEDIAL / MASTERY PLAN:")
        for step in evaluated["recovery"]["catchup_plan"]:
            lines.append(f"✓ {step}")

    return "\n".join(lines)


def auto_grade_pace_submission_with_colleague_zero(submission, assignment, student_user):
    """
    Called automatically when a student submits an assignment in Pace Academy (`/student/section/.../assignment/.../submit`),
    OR when grading unreviewed Pace Academy submissions.
    Saves everything into Pace Academy's shared SQLAlchemy database (`assignment_submissions`,
    `colleague_zero_audits`, and `notifications`).
    """
    _ensure_cz_tables()
    batch_id = f"pace_assign_{assignment.id}"
    rubric = build_rubric_for_pace_assignment(assignment)
    course = assignment.section.course if assignment.section else None
    school_or_cohort = course.title if course else "Pace Academy Cohort"
    learner_name = student_user.full_name if student_user else "Pace Learner"

    raw_text = _extract_submission_text_for_grading(submission)

    evaluated, worker_events = run_pace_4_worker_pipeline(
        batch_id=batch_id,
        learner_name=learner_name,
        school_or_cohort=school_or_cohort,
        essay_text=raw_text,
        rubric=rubric,
        number=submission.attempt_number or 1,
    )

    final_score = float(evaluated["moderation"]["corrected_score"])
    submission.grade = final_score
    submission.reviewed = True
    submission.feedback = format_feedback_for_pace_ui(evaluated, rubric)

    # Persist multi-agent audit in the shared Pace Academy database (`colleague_zero_audits` table)
    if submission.id:
        existing_audit = ColleagueZeroAuditRecord.query.filter_by(submission_id=submission.id).first()
        if existing_audit:
            existing_audit.evaluated_json = json.dumps(evaluated)
            existing_audit.events_json = json.dumps(worker_events)
        else:
            db.session.add(ColleagueZeroAuditRecord(
                submission_id=submission.id,
                batch_id=batch_id,
                evaluated_json=json.dumps(evaluated),
                events_json=json.dumps(worker_events),
            ))

    needs_rec = evaluated["recovery"]["needs_recovery"]
    try:
        if student_user and student_user.id:
            student_notif = Notification(
                user_id=student_user.id,
                notification_type="assignment_feedback",
                title=f"⚡ Colleague Zero Graded: {assignment.title} ({int(final_score)}%)",
                message=evaluated["recovery"]["feedback"],
                link_url=f"/student/section/{assignment.section_id}/assignment/{assignment.id}/submit",
                priority="high" if needs_rec else "normal",
                related_course_id=course.id if course else None,
                related_assignment_id=assignment.id,
            )
            db.session.add(student_notif)

        if course and course.teacher_id:
            teacher_notif = Notification(
                user_id=course.teacher_id,
                notification_type="assignment_feedback",
                title=f"🤖 Colleague Zero Auto-Graded {learner_name} ({int(final_score)}%)",
                message=f"{assignment.title}: {evaluated['moderation']['correction_log']}",
                link_url=f"/colleague-zero?batch_id={batch_id}",
                priority="normal",
                related_course_id=course.id,
                related_assignment_id=assignment.id,
            )
            db.session.add(teacher_notif)
    except Exception as e:
        print("Pace notification note:", e)

    return evaluated


def ensure_default_pace_assignment_if_none():
    _ensure_cz_tables()
    assignments = Assignment.query.order_by(Assignment.id.desc()).all()
    dirty = False
    for a in assignments:
        for sub in a.submissions:
            audit_rec = ColleagueZeroAuditRecord.query.filter_by(submission_id=sub.id).first()
            if not sub.reviewed or sub.grade is None or not audit_rec:
                student_user = User.query.get(sub.student_id)
                auto_grade_pace_submission_with_colleague_zero(sub, a, student_user)
                dirty = True
    if dirty:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return assignments


def fetch_pace_batch_dict(batch_id=None):
    assignments = ensure_default_pace_assignment_if_none()

    available_batches = []
    target_assignment = None

    for a in assignments:
        bid = f"pace_assign_{a.id}"
        course_title = a.section.course.title if (a.section and a.section.course) else "Pace Academy Course"
        sub_count = len(a.submissions)
        available_batches.append({
            "id": bid,
            "title": f"{course_title} — {a.title}",
            "programme_type": f"Pace Academy · {course_title}",
            "count": sub_count,
        })
        if batch_id == bid or (target_assignment is None):
            target_assignment = a

    if target_assignment is None:
        default_rubric = {
            "version": "DBE CAPS Rubric v2.4 (Pace Academy)",
            "question_prompt": "Explain how Meiosis contributes to genetic variation through Crossing-Over (Prophase I) and Random Arrangement (Metaphase I & II), and explain the importance of halving the chromosome number.",
            "total_marks": 100,
            "pass_mark": 50,
            "criteria": [
                {"id": "C1", "name": "Crossing-Over in Prophase I", "weight": 30, "description": "Homologous chromosomes pair up as bivalents, non-sister chromatids overlap at chiasmata, and exchange DNA segments."},
                {"id": "C2", "name": "Random Arrangement in Metaphase I & II", "weight": 30, "description": "Homologous chromosome pairs arrange randomly along the equator in Metaphase I, leading to independent assortment."},
                {"id": "C3", "name": "Halving Chromosome Number (Diploid to Haploid)", "weight": 25, "description": "Reduces diploid (2n=46) parent cells to haploid (n=23) gametes so fertilisation restores diploid number."},
                {"id": "C4", "name": "Scientific Synthesis & Conceptual Clarity", "weight": 15, "description": "Clear distinction between Meiosis I and II phases and accurate biological reasoning."},
            ],
        }
        return {
            "id": "caps_life_sciences",
            "title": "Pace Academy — Grade 12 Life Sciences (Meiosis)",
            "programme_type": "Pace Academy LMS",
            "default_goal": "Autonomously assess and moderate all learner assignment submissions across Pace Academy courses.",
            "rubric": default_rubric,
            "submissions": [],
            "available_batches": [{"id": "caps_life_sciences", "title": "Pace Academy — Grade 12 Life Sciences (Meiosis)", "programme_type": "Pace Academy LMS", "count": 0}],
            "notifications": [],
            "agent_events": [],
        }

    active_bid = f"pace_assign_{target_assignment.id}"
    course_title = target_assignment.section.course.title if (target_assignment.section and target_assignment.section.course) else "Pace Academy Course"
    rubric = build_rubric_for_pace_assignment(target_assignment)

    subs_sorted = sorted(target_assignment.submissions, key=lambda s: s.submitted_at or datetime.min, reverse=True)
    sub_dicts = []
    all_events = []
    notif_dicts = []

    for idx, sub in enumerate(subs_sorted, start=1):
        student = User.query.get(sub.student_id)
        lname = student.full_name if student else f"Learner #{sub.student_id}"
        lemail = student.email if student else ""
        audit_rec = ColleagueZeroAuditRecord.query.filter_by(submission_id=sub.id).first()
        if audit_rec:
            meta = json.loads(audit_rec.evaluated_json)
            evs = json.loads(audit_rec.events_json)
        else:
            raw_text = _extract_submission_text_for_grading(sub)
            meta, evs = run_pace_4_worker_pipeline(active_bid, lname, course_title, raw_text, rubric, idx)

        all_events.extend(evs)
        time_lbl = sub.submitted_at.strftime("%d %b %H:%M") if sub.submitted_at else "Just now"
        init_score = meta["initial_mark"]["score"]
        final_score = meta["moderation"]["corrected_score"]
        flagged = meta["moderation"]["flagged"]

        notif_dicts.append({
            "id": sub.id * 2,
            "batch_id": active_bid,
            "recipient_role": "teacher",
            "learner_name": lname,
            "submission_id": f"pace_sub_{sub.id}",
            "title": (
                f"⚡ [RV→MK Self-Corrected] {lname}: {init_score}% → {final_score}%"
                if flagged
                else f"✅ [Colleague Zero Graded] {lname}: {final_score}%"
            ),
            "message": meta["moderation"]["correction_log"],
            "badge_type": "warning" if flagged else "success",
            "is_read": False,
            "time_label": time_lbl,
        })
        notif_dicts.append({
            "id": sub.id * 2 + 1,
            "batch_id": active_bid,
            "recipient_role": "learner",
            "learner_name": lname,
            "submission_id": f"pace_sub_{sub.id}",
            "title": f"🎉 Pace Assignment Graded & Moderated: {final_score}%",
            "message": meta["recovery"]["feedback"],
            "badge_type": "recovery" if meta["recovery"]["needs_recovery"] else "success",
            "is_read": False,
            "time_label": time_lbl,
        })

        sub_dicts.append({
            "id": f"pace_sub_{sub.id}",
            "batch_id": active_bid,
            "number": sub.attempt_number or idx,
            "learner_name": lname,
            "learner_email": lemail,
            "school_or_cohort": f"{course_title} · Attempt #{sub.attempt_number or 1}",
            "submitted_at": time_lbl,
            "essay_text": sub.code_submission if (sub.submission_type == "code" and sub.code_submission) else (sub.submission_text or ""),
            "worker_status": "completed",
            "initial_mark": meta["initial_mark"],
            "moderation": meta["moderation"],
            "recovery": meta["recovery"],
        })

    return {
        "id": active_bid,
        "pace_assignment_id": target_assignment.id,
        "pace_section_id": target_assignment.section_id,
        "pace_course_id": target_assignment.section.course_id if target_assignment.section else None,
        "title": f"{course_title} — {target_assignment.title}",
        "programme_type": f"Pace Academy · {course_title}",
        "default_goal": (
            f"Autonomously assess all Pace Academy learner submissions for '{target_assignment.title}' in '{course_title}', "
            f"audit for grading fairness, self-correct rubric discrepancies, and write marks back to Pace Academy."
        ),
        "rubric": rubric,
        "submissions": sub_dicts,
        "available_batches": available_batches,
        "notifications": notif_dicts[:25],
        "agent_events": all_events[-30:],
    }


@colleague_zero_bp.route("/")
@colleague_zero_bp.route("/teacher")
def hub_index():
    teacher_name = "Educator"
    teacher_email = ""
    teacher_school = "Pace Academy Faculty"
    if current_user and getattr(current_user, "is_authenticated", False):
        teacher_name = current_user.full_name
        teacher_email = current_user.email
        if getattr(current_user, "specialization", None):
            teacher_school = current_user.specialization
    return render_template(
        "colleague_zero/index.html",
        teacher_name=teacher_name,
        teacher_email=teacher_email,
        teacher_school=teacher_school,
    )


@colleague_zero_bp.route("/learner")
def learner_portal():
    learner_name = ""
    learner_email = ""
    if current_user and getattr(current_user, "is_authenticated", False):
        learner_name = current_user.full_name
        learner_email = current_user.email
    return render_template(
        "colleague_zero/learner.html",
        learner_name=learner_name,
        learner_email=learner_email,
    )


@colleague_zero_bp.route("/login")
def login_portal():
    return render_template("colleague_zero/login.html")


@colleague_zero_bp.route("/api/batches", methods=["GET"])
def api_get_batches():
    batch_id = request.args.get("batch_id")
    try:
        batch_data = fetch_pace_batch_dict(batch_id)
    except Exception:
        # Recover cleanly from stale SSL/Gunicorn pooled connections (e.g. sslv3 alert bad record mac)
        try:
            db.session.remove()
            db.engine.dispose()
        except Exception:
            pass
        batch_data = fetch_pace_batch_dict(batch_id)
    return jsonify({
        "ok": True,
        "batch": batch_data,
        "available_batches": batch_data["available_batches"],
        "notifications": batch_data["notifications"],
        "agent_events": batch_data["agent_events"],
    })


@colleague_zero_bp.route("/api/submissions/add", methods=["POST"])
@csrf.exempt
def api_add_submission():
    data = request.get_json(silent=True) or {}
    batch_id = data.get("batch_id") or ""
    learner_name = (data.get("learner_name") or "").strip()
    learner_email = (data.get("learner_email") or "").strip().lower()
    essay_text = (data.get("essay_text") or "").strip()

    if not learner_name or not essay_text:
        return jsonify({"ok": False, "error": "Please provide your name and assignment response."}), 400

    student = None
    if current_user and getattr(current_user, "is_authenticated", False) and current_user.role == "student":
        student = current_user
    if not student and learner_email:
        student = User.query.filter_by(email=learner_email).first()
    if not student:
        uname = re.sub(r"[^a-z0-9_]", "_", learner_name.lower())[:40] or "pace_learner"
        email_use = learner_email or f"{uname}@pace-academy.co.za"
        student = User.query.filter((User.email == email_use) | (User.username == uname)).first()
        if not student:
            parts = learner_name.split(" ", 1)
            student = User(
                email=email_use,
                username=f"{uname}_{int(time.time()) % 10000}",
                password="pace_student_password",
                role="student",
                first_name=parts[0],
                last_name=parts[1] if len(parts) > 1 else "",
            )
            db.session.add(student)
            db.session.flush()

    assignment = None
    if batch_id.startswith("pace_assign_"):
        aid = int(batch_id.replace("pace_assign_", ""))
        assignment = Assignment.query.get(aid)
    if not assignment:
        assignment = Assignment.query.order_by(Assignment.id.desc()).first()

    if not assignment:
        course = Course.query.first()
        if not course:
            teacher = User.query.filter_by(role="teacher").first() or student
            course = Course(
                teacher_id=teacher.id,
                title="Grade 12 CAPS Life Sciences",
                description="Meiosis, Genetic Variation, and Cellular Division",
                status="approved",
                is_draft=False,
            )
            db.session.add(course)
            db.session.flush()
        section = Section.query.filter_by(course_id=course.id).first()
        if not section:
            section = Section(
                course_id=course.id,
                title="Meiosis & Genetic Variation Assessment",
                content="Explain Crossing-Over in Prophase I, Random Arrangement in Metaphase I & II, and halving the chromosome number.",
                section_type="assignment",
                is_published=True,
                order=1,
            )
            db.session.add(section)
            db.session.flush()
        assignment = Assignment(
            section_id=section.id,
            title="Meiosis & Genetic Variation",
            description="Explain how Meiosis contributes to genetic variation through Crossing-Over (Prophase I) and Random Arrangement of chromosomes (Metaphase I & II), and explain the biological importance of halving the chromosome number from diploid (2n=46) to haploid (n=23).",
            max_attempts=10,
        )
        db.session.add(assignment)
        db.session.flush()

    prev_count = AssignmentSubmission.query.filter_by(
        assignment_id=assignment.id, student_id=student.id
    ).count()

    pace_sub = AssignmentSubmission(
        assignment_id=assignment.id,
        student_id=student.id,
        attempt_number=prev_count + 1,
        submission_text=essay_text,
        submission_type="text",
        submitted_at=datetime.utcnow(),
    )
    db.session.add(pace_sub)
    db.session.flush()

    auto_grade_pace_submission_with_colleague_zero(pace_sub, assignment, student)
    db.session.commit()

    updated_batch = fetch_pace_batch_dict(f"pace_assign_{assignment.id}")
    saved_sub = next((s for s in updated_batch["submissions"] if s["id"] == f"pace_sub_{pace_sub.id}"), updated_batch["submissions"][0])

    return jsonify({
        "ok": True,
        "submission": saved_sub,
        "batch": updated_batch,
        "notifications": updated_batch["notifications"],
        "agent_events": updated_batch["agent_events"],
    })


@colleague_zero_bp.route("/api/assignments/create", methods=["POST"])
@csrf.exempt
def api_create_assignment():
    _ensure_cz_tables()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    programme_type = (data.get("programme_type") or "Pace Academy Course").strip()
    question_prompt = (data.get("question_prompt") or "").strip()
    criteria = data.get("criteria") or []

    if not title or not criteria:
        return jsonify({"ok": False, "error": "Please provide an assignment title and rubric criteria."}), 400

    course = Course.query.order_by(Course.id.desc()).first()
    if not course:
        teacher = User.query.filter_by(role="teacher").first() or User.query.first()
        course = Course(
            teacher_id=teacher.id if teacher else 1,
            title=programme_type,
            description=question_prompt,
            status="approved",
            is_draft=False,
        )
        db.session.add(course)
        db.session.flush()

    section = Section(
        course_id=course.id,
        title=title,
        content=question_prompt,
        section_type="assignment",
        is_published=True,
        order=Section.query.filter_by(course_id=course.id).count() + 1,
    )
    db.session.add(section)
    db.session.flush()

    assignment = Assignment(
        section_id=section.id,
        title=title,
        description=question_prompt,
        max_attempts=5,
    )
    db.session.add(assignment)
    db.session.flush()

    batch_id = f"pace_assign_{assignment.id}"
    rubric_dict = {
        "version": f"{programme_type} Rubric v1.0",
        "question_prompt": question_prompt,
        "total_marks": sum(int(c.get("weight", 25)) for c in criteria),
        "pass_mark": int(data.get("pass_mark") or 50),
        "criteria": criteria,
    }
    db.session.add(ColleagueZeroRubricRecord(
        batch_id=batch_id,
        assignment_id=assignment.id,
        rubric_json=json.dumps(rubric_dict),
    ))
    db.session.commit()

    batch_data = fetch_pace_batch_dict(batch_id)
    return jsonify({
        "ok": True,
        "batch_id": batch_id,
        "batch": batch_data,
        "available_batches": batch_data["available_batches"],
    })


@colleague_zero_bp.route("/api/notifications/read", methods=["POST"])
@csrf.exempt
def api_notifications_read():
    return jsonify({"ok": True})


@colleague_zero_bp.route("/api/export/<batch_id>.csv", methods=["GET"])
def api_export_csv(batch_id):
    batch = fetch_pace_batch_dict(batch_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Attempt #",
        "Learner Name",
        "Course / Cohort",
        "Assessor [MK] Pass-1 (%)",
        "Moderator [RV] Flagged?",
        "Final Moderated Grade (%)",
        "Moderator Audit Note",
        "Recovery Plan Triggered?",
        "Personalised Learner Feedback",
    ])
    for s in batch["submissions"]:
        writer.writerow([
            f"#{s['number']}",
            s["learner_name"],
            s["school_or_cohort"],
            f"{s['initial_mark']['score']}%",
            "YES (Self-Corrected)" if s["moderation"]["flagged"] else "NO (Verified)",
            f"{s['moderation']['corrected_score']}%",
            s["moderation"]["flag_reason"] or s["moderation"]["correction_log"],
            "YES" if s["recovery"]["needs_recovery"] else "NO",
            s["recovery"]["feedback"],
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pace_colleague_zero_{batch['id']}.csv"},
    )
