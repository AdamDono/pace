import json
import logging
import os
import re
import base64
import hashlib
import io
import wave
import requests
from html import unescape
from html.parser import HTMLParser
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs, unquote
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

MODEL_3D_EXTENSIONS = ('.glb', '.gltf', '.obj', '.fbx', '.stl')
LESSON_TEXT_LIMIT = 2500
MAX_HOTSPOTS_PER_MODEL = 12


def _clean_text(value: Optional[str]) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not value:
        return ''
    text = re.sub(r'<[^>]+>', ' ', str(value))
    return re.sub(r'\s+', ' ', unescape(text)).strip()


def _name_from_url(url: Optional[str]) -> str:
    """Turn '/static/uploads/human_heart-v2.glb' into 'Human Heart V2'."""
    if not url:
        return ''
    base = os.path.basename(urlparse(url).path or url)
    stem = os.path.splitext(unquote(base))[0]
    stem = re.sub(r'[_\-]+', ' ', stem).strip()
    return stem.title() if stem else ''


def _parse_hotspots(raw: Any) -> List[Dict[str, str]]:
    """Normalise hotspot data (JSON string or list) to [{title, description}]."""
    if not raw:
        return []
    data = raw
    if isinstance(raw, str):
        for candidate in (raw, unquote(raw)):
            try:
                data = json.loads(candidate)
                break
            except (ValueError, TypeError):
                data = None
    if not isinstance(data, list):
        return []
    pins = []
    for h in data:
        if not isinstance(h, dict):
            continue
        title = _clean_text(h.get('title') or h.get('label') or h.get('name'))
        desc = _clean_text(h.get('description') or h.get('desc') or h.get('popup_content'))
        if title or desc:
            pins.append({'title': title, 'description': desc})
    return pins


class _LessonHTMLScanner(HTMLParser):
    """Pulls readable text and any embedded 3D models out of lesson HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_chunks: List[str] = []
        self.models: List[Dict[str, Any]] = []
        self._skip_depth = 0

    def _last_caption(self) -> str:
        # The hotspot editor places a short centred caption right before the embed
        for chunk in reversed(self.text_chunks[-3:]):
            if 0 < len(chunk) <= 120:
                return chunk
        return ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self._skip_depth += 1
            return

        # 1. Quill iframe embeds: /static/3d-viewer-embed.html?model=...#hotspots=...
        if tag == 'iframe' and '3d-viewer-embed' in (attrs.get('src') or ''):
            parsed = urlparse(attrs['src'])
            query = parse_qs(parsed.query)
            frag = parse_qs(parsed.fragment)
            model_url = (query.get('model') or [''])[0]
            raw_hs = (frag.get('hotspots') or query.get('hotspots') or [''])[0]
            self.models.append({
                'name': self._last_caption() or _name_from_url(model_url) or '3D model',
                'file': _name_from_url(model_url),
                'hotspots': _parse_hotspots(raw_hs),
            })
            return

        # 2. Legacy inline viewer blocks: <div data-ql-3d="1" data-src=... data-hotspots=...>
        if attrs.get('data-ql-3d') == '1':
            model_url = attrs.get('data-src') or ''
            self.models.append({
                'name': attrs.get('data-caption') or self._last_caption() or _name_from_url(model_url) or '3D model',
                'file': _name_from_url(model_url),
                'hotspots': _parse_hotspots(attrs.get('data-hotspots')),
            })

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        chunk = re.sub(r'\s+', ' ', data).strip()
        if chunk:
            self.text_chunks.append(chunk)


def extract_lesson_context(section) -> Dict[str, Any]:
    """
    Build what Bookworm should know about the lesson currently on screen:
    clean readable text + every 3D model (name and pins) in that lesson.
    """
    result = {'text': '', 'models': []}
    if section is None:
        return result

    scanner = _LessonHTMLScanner()
    try:
        scanner.feed(section.content or '')
        scanner.close()
    except Exception as e:  # malformed HTML should never break the tutor
        logger.warning(f"Lesson HTML scan failed for section {getattr(section, 'id', '?')}: {e}")

    result['text'] = ' '.join(scanner.text_chunks)[:LESSON_TEXT_LIMIT]
    models = list(scanner.models)

    # 3. Section-level 3D model (uploaded media file + pins saved in the database)
    media_file = getattr(section, 'media_file', None) or ''
    db_hotspots = list(getattr(section, 'hotspots', None) or [])
    if db_hotspots or media_file.lower().endswith(MODEL_3D_EXTENSIONS):
        pins = []
        for h in sorted(db_hotspots, key=lambda x: (x.order or 0, x.id)):
            title = _clean_text(h.title)
            desc = _clean_text(h.description) or _clean_text(h.popup_content)
            if title or desc:
                pins.append({'title': title, 'description': desc})
        models.insert(0, {
            'name': _name_from_url(media_file) or section.title or '3D model',
            'file': _name_from_url(media_file),
            'hotspots': pins,
        })

    result['models'] = models
    return result

class AITutorService:
    """
    AI Study Companion ('Bookworm') for Pace Academy.
    - Helps students understand lessons and resolve doubts.
    - References 3D model hotspots and interactive diagrams currently on screen when present.
    - Never gives away direct quiz answers without explanation.
    """

    SYSTEM_PROMPT = """You are "Bookworm" (affectionately called "Wormy"), the friendly, clever, and supportive AI learning companion at Pace Academy in South Africa.

BEHAVIOR GUIDELINES:
1. DIRECT RELEVANCE FIRST:
   - Answer the student's immediate question directly and clearly first. Never ignore what they asked.
   - If they ask about navigation, where they are, or where content is located, give a direct, friendly answer.
   - Do NOT lecture them about topics or curriculum they didn't ask about.

2. CONVERSATIONAL & CONCISE (NO WALLS OF TEXT):
   - Keep replies short, natural, and friendly (1 to 2 short paragraphs max).
   - Talk like a supportive mentor or study buddy—NOT a rigid textbook or automated checklist.

3. EXPLANATION-FIRST (NO HOMEWORK CHEATING):
   - When a student asks for the direct answer to a quiz or homework question, do NOT just give away the final letter or answer (e.g. don't say "The answer is B").
   - Instead, give a helpful clue, break down what the question is asking, or prompt their thinking so they understand the concept.

4. NO FORCED ANALOGIES:
   - Use analogies ONLY when explaining a difficult or abstract academic concept, or when the student specifically asks for one.
   - Never force an analogy into basic questions or casual chat.

5. FOCUS ON LESSON CONTENT (NO CAREER SPEECHES):
   - Stick to helping the student understand their current subject and lesson. Do NOT give unsolicited career or APS speeches (the platform has a dedicated Career Guidance section on the sidebar).

6. NO SURPRISE POP-QUIZZES:
   - Do NOT interrogate the student with an unasked test question at the end of every message. Only ask a practice question when solving a problem together or if the student asks to test themselves.

7. 3D MODELS & VISUALS:
   - The context lists "3D Models in this lesson" with each model's name and its labelled pins. That list is the ONLY thing you know about the models — you cannot see their shape or colour.
   - When the student asks about the 3D model, refer to it by name and point to specific pins by number and title (e.g. "Click Pin 2, the Left Ventricle...").
   - Never invent parts, pins or features that are not listed. If a model has no labelled pins, say you can only see its name.
   - If the list says "none", there is no 3D model in this lesson: say so honestly and offer to help with the lesson content instead. Do not bring up 3D models otherwise.

8. TONE:
   - Warm, concise, authentic South African warmth (e.g., "Sharp!", "You've got this!"). Clean markdown formatting.

9. REAL ACADEMIC & SYLLABUS ACCESS:
   - You have full, real-time access to the student's actual course syllabus, upcoming assignments, quiz marks, submission grades, and their school report card (all provided in the [ACADEMIC & COURSE DATA] context below).
   - NEVER say "I don't have access to your syllabus, gradebook, or assignments" or "Ask your teacher for assignment names". You DO have access to their real Pace course outline, assignments, and grades!
   - When the student asks about assignments ("name them", "what tasks do I have?", "what's next?"), answer with their actual assignment titles, due dates, scores, and status directly, accurately, and encouragement.
   - You can cross-reference their high school report card marks and dream career when giving advice on why mastering this lesson or assignment matters!
"""

    @classmethod
    def generate_socratic_guidance(
        cls,
        user_message: str,
        course_title: Optional[str] = None,
        section_title: Optional[str] = None,
        section_content: Optional[str] = None,
        hotspots: Optional[List[Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        student_name: Optional[str] = None,
        models_3d: Optional[List[Dict[str, Any]]] = None,
        academic_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a guided Socratic response from Bookworm.
        `models_3d` is the server-extracted list from extract_lesson_context();
        `hotspots` is a legacy fallback for loose client-supplied pins.
        `academic_context` provides real-time syllabus, assignments, grades, and report card data.
        """
        # Build contextual prompt
        context_parts = []
        if student_name:
            context_parts.append(f"Student Name: {student_name}")
        if course_title:
            context_parts.append(f"Current Course: {course_title}")
        if section_title:
            context_parts.append(f"Current Lesson / Activity: {section_title}")

        if academic_context:
            acad_lines = []
            syllabus = academic_context.get('syllabus') or []
            if syllabus:
                acad_lines.append("Course Syllabus Outline:")
                for s_item in syllabus[:20]:
                    cur_flag = " [CURRENT LESSON ON SCREEN]" if s_item.get('is_current') else ""
                    acad_lines.append(f"  - {s_item.get('title')}{cur_flag}")

            assignments = academic_context.get('assignments') or []
            if assignments:
                acad_lines.append("Course Assignments & Graded Tasks:")
                for idx, a in enumerate(assignments[:15], 1):
                    if a.get('is_submitted'):
                        if a.get('grade') is not None:
                            status = f"SUBMITTED (Grade: {a['grade']}%)"
                        else:
                            status = "SUBMITTED (Awaiting teacher review)"
                    else:
                        status = f"PENDING / NOT SUBMITTED (Due: {a.get('due_date', 'No set deadline')})"
                    feedback_str = f" | Teacher Feedback: '{a['feedback']}'" if a.get('feedback') else ""
                    lesson_str = f" [in lesson: {a.get('lesson')}]" if a.get('lesson') else ""
                    acad_lines.append(f"  {idx}. \"{a.get('title')}\" - {status}{lesson_str}{feedback_str}")
            else:
                acad_lines.append("Course Assignments: None currently assigned for this course.")

            quizzes = academic_context.get('quizzes') or []
            if quizzes:
                acad_lines.append("Course Quizzes & Scores:")
                for q in quizzes[:10]:
                    score_str = f"Score: {q['score']}%" if q.get('score') is not None else "Not attempted yet"
                    acad_lines.append(f"  - \"{q.get('title')}\": {score_str}")

            report_card = academic_context.get('report_card')
            if report_card:
                acad_lines.append(f"Official High School Report Card (Grade {report_card.get('grade')}, Term {report_card.get('term')}, School: {report_card.get('school')}):")
                acad_lines.append(f"  - Dream Career Target: {report_card.get('target_career')}")
                acad_lines.append(f"  - Verified APS Score: {report_card.get('aps')}")
                subs = report_card.get('subjects') or []
                if subs:
                    sub_str = ", ".join([f"{s.get('subject')}: {s.get('mark')}% (L{s.get('level')})" for s in subs[:8]])
                    acad_lines.append(f"  - Verified Term Marks: {sub_str}")

            if acad_lines:
                context_parts.append("[ACADEMIC & COURSE DATA (REAL DATABASE RECORDS)]\n" + "\n".join(acad_lines))

        # Fall back to loose client hotspots only if the server found no models
        if not models_3d and hotspots:
            pins = _parse_hotspots(hotspots)
            if pins:
                models_3d = [{'name': '3D model on screen', 'file': '', 'hotspots': pins}]

        if models_3d:
            model_lines = []
            for m_idx, model in enumerate(models_3d[:3], 1):
                header = f"Model {m_idx}: {model.get('name') or '3D model'}"
                if model.get('file') and model.get('file') != model.get('name'):
                    header += f" (file: {model['file']})"
                model_lines.append(header)
                pins = model.get('hotspots') or []
                if pins:
                    for p_idx, pin in enumerate(pins[:MAX_HOTSPOTS_PER_MODEL], 1):
                        desc = f" - {pin['description']}" if pin.get('description') else ''
                        model_lines.append(f"  Pin {p_idx}: {pin.get('title') or 'Untitled'}{desc}")
                else:
                    model_lines.append("  (No labelled pins on this model)")
            context_parts.append(
                "3D Models in this lesson (you cannot see the shape, only these labels - "
                "never invent parts or pins that are not listed):\n" + "\n".join(model_lines)
            )
        else:
            context_parts.append("3D Models in this lesson: none")

        if section_content:
            # Callers should pass clean text; strip any leftover HTML defensively
            clean_content = _clean_text(section_content)[:LESSON_TEXT_LIMIT]
            context_parts.append(f"Lesson Excerpt:\n{clean_content}")

        context_str = "\n".join(context_parts)

        # Build prompt history
        history_str = ""
        if history:
            for turn in history[-6:]:  # Keep last 3 turns
                role = "Student" if turn.get("role") in ["user", "student"] else "Bookworm"
                history_str += f"{role}: {turn.get('content', '')}\n"

        prompt = f"""[CONTEXT INFORMATION]
{context_str}

[PREVIOUS CONVERSATION]
{history_str}

[STUDENT'S NEW MESSAGE]
{user_message}

Bookworm's Response:"""

        try:
            # Call Gemini
            raw_response = AIService._call_gemini(
                prompt=prompt,
                system_instruction=cls.SYSTEM_PROMPT,
                model="gemini-3.1-flash-lite"
            )
            return {
                "success": True,
                "response": raw_response.strip(),
                "mascot_state": cls._determine_mascot_state(user_message, raw_response)
            }
        except Exception as e:
            logger.error(f"Error in Bookworm tutor: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Oops! My antennas got a bit tangled in the data stream. Give me one second and ask again!",
                "mascot_state": "thinking"
            }

    @classmethod
    def get_career_pathway(
        cls,
        course_title: str,
        section_title: Optional[str] = None,
        grade_level: str = "Grade 12"
    ) -> Dict[str, Any]:
        """
        Connects the current topic directly to SA University APS entry and youth career pathways.
        """
        prompt = f"""You are the Career & Employment Guidance module of Pace Academy.
The student is studying:
- Course: {course_title}
- Lesson: {section_title or 'Core Module'}
- Level: {grade_level} (CAPS Curriculum, South Africa)

Generate an exciting, high-impact career pathway breakdown in valid JSON format with these exact keys:
{{
    "career_title": "Primary Career Role (e.g. Bioinformatician / Molecular Geneticist)",
    "industry_sector": "Sector (e.g. Healthcare & Biotechnology)",
    "average_salary_range": "Estimated SA entry-to-mid salary (e.g. R350,000 - R680,000 / year)",
    "aps_requirements": "Recommended APS score range (e.g. APS 35 - 38 at Wits / UCT / UP)",
    "key_subjects_needed": ["Life Sciences (Level 5+)", "Mathematics (Level 5+)", "Physical Sciences"],
    "why_this_lesson_matters": "2 punchy sentences explaining how what they are studying right now is used daily in this job.",
    "future_outlook": "Brief 1-sentence note on employment demand in South Africa."
}}
Ensure the output is clean JSON only.
"""
        try:
            raw = AIService._call_gemini(
                prompt=prompt,
                model="gemini-3.1-flash-lite",
                response_json=True
            )
            parsed = AIService._parse_json_safely(raw)
            return {"success": True, "data": parsed}
        except Exception as e:
            logger.error(f"Error generating career pathway: {e}")
            return {
                "success": True,
                "data": {
                    "career_title": "Biomedical & Biotechnology Specialist",
                    "industry_sector": "Healthcare & Life Sciences",
                    "average_salary_range": "R320,000 - R600,000 / year",
                    "aps_requirements": "APS 34 - 38 (Wits, UCT, Stellenbosch)",
                    "key_subjects_needed": ["Life Sciences", "Mathematics", "Physical Sciences"],
                    "why_this_lesson_matters": "Understanding cellular mechanisms is the core foundation for genetic medicine, disease diagnostics, and agricultural biotech in South Africa.",
                    "future_outlook": "High national demand due to expansion in local pharmaceutical production and genetics research."
                }
            }

    @staticmethod
    def _determine_mascot_state(user_msg: str, response: str) -> str:
        """Determines the visual expression of the mascot based on conversation cues."""
        text = (user_msg + " " + response).lower()
        if any(w in text for w in ["correct", "congratulations", "spot on", "great job", "aha", "sharp", "you did it", "perfect"]):
            return "celebrating"
        if any(w in text for w in ["why", "how", "what if", "think about", "notice", "imagine", "observe"]):
            return "explaining"
        if any(w in text for w in ["stuck", "confused", "help", "don't know", "lost", "hard"]):
            return "encouraging"
        return "idle"

    _AUDIO_CACHE: Dict[str, str] = {}

    @classmethod
    def generate_neural_speech(cls, text: str, voice: str = "Puck") -> Dict[str, Any]:
        """
        Generates realistic human neural voice audio using Google Gemini TTS models.
        Returns a base64 encoded audio/wav data URI for direct browser playback.
        """
        import hashlib
        import base64
        import io
        import wave
        import requests

        clean_text = _clean_text(text)
        if not clean_text:
            return {"success": False, "error": "Text is empty."}

        # Truncate to first 1-2 punchy sentences for snappy latency and low token usage
        import re
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        speech_snippet = " ".join(sentences[:2]) if sentences else clean_text
        if len(speech_snippet) > 200:
            speech_snippet = speech_snippet[:200].rsplit(' ', 1)[0] + '...'
        clean_text = speech_snippet

        cache_key = hashlib.md5(f"{clean_text}_{voice}".encode('utf-8')).hexdigest()
        if cache_key in cls._AUDIO_CACHE:
            return {"success": True, "audio_url": cls._AUDIO_CACHE[cache_key]}

        api_key = AIService.get_api_key()
        if not api_key:
            return {"success": False, "error": "Gemini API key not configured."}

        # Use only valid Gemini 2.5 Flash TTS model; avoid non-existent models
        current_model = "gemini-2.5-flash-preview-tts"

        payload = {
            "contents": [
                {
                    "parts": [{"text": clean_text}]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice
                        }
                    }
                }
            }
        }

        try:
            import certifi
            ssl_verify = certifi.where()
        except ImportError:
            ssl_verify = True

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
        try:
            res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=3.5, verify=ssl_verify)
            if res.status_code == 200:
                data = res.json()
                pcm_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                pcm_bytes = base64.b64decode(pcm_b64)

                # Wrap in standard 24kHz mono WAV container
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    wav_file.writeframes(pcm_bytes)

                wav_b64 = base64.b64encode(wav_io.getvalue()).decode('utf-8')
                audio_url = f"data:audio/wav;base64,{wav_b64}"

                # Cache recent responses
                if len(cls._AUDIO_CACHE) > 100:
                    cls._AUDIO_CACHE.pop(next(iter(cls._AUDIO_CACHE)))
                cls._AUDIO_CACHE[cache_key] = audio_url

                return {"success": True, "audio_url": audio_url}
            else:
                last_error = f"{res.status_code}: {res.text[:120]}"
        except Exception as e:
            last_error = str(e)

        logger.warning(f"Neural speech generation failed: {last_error}")
        return {"success": False, "error": last_error}

    @classmethod
    def transcribe_audio(cls, audio_bytes: bytes, mime_type: str = "audio/webm") -> Dict[str, Any]:
        """
        Transcribe raw audio bytes using Gemini 3.1 Flash Lite into text.
        Works across all browser recorded formats (audio/webm, audio/wav, audio/mp4, audio/ogg).
        """
        api_key = AIService.get_api_key()
        if not api_key:
            return {"success": False, "error": "Gemini API key not configured."}

        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest"
        ]

        payload = {
            "contents": [{
                "parts": [
                    {"text": "Transcribe the student's spoken audio into plain text. Return ONLY the transcribed text, nothing else."},
                    {"inlineData": {"mimeType": mime_type, "data": audio_b64}}
                ]
            }]
        }

        try:
            import certifi
            ssl_verify = certifi.where()
        except ImportError:
            ssl_verify = True

        last_error = None
        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=8, verify=ssl_verify)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            transcribed = parts[0].get("text", "").strip()
                            return {"success": True, "text": transcribed}
                    return {"success": True, "text": ""}
                else:
                    last_error = f"{current_model}: {res.status_code} - {res.text[:120]}"
            except Exception as e:
                last_error = f"{current_model}: {e}"

        logger.warning(f"Audio transcription failed: {last_error}")
        return {"success": False, "error": last_error}

    @classmethod
    def calculate_aps(cls, subjects: List[Dict[str, Any]]) -> int:
        """
        Calculates official South African university Admission Point Score (APS).
        Rules: Best 6 subjects excluding Life Orientation (LO).
        Adds 1 bonus point if Life Orientation is Level 5+ (60%+).
        """
        lo_bonus = 0
        regular_subject_points = []

        for item in subjects:
            name = (item.get('subject') or '').strip().lower()
            mark = float(item.get('mark', 0))

            if mark >= 80:
                level = 7
            elif mark >= 70:
                level = 6
            elif mark >= 60:
                level = 5
            elif mark >= 50:
                level = 4
            elif mark >= 40:
                level = 3
            elif mark >= 30:
                level = 2
            else:
                level = 1

            if 'life orientation' in name or name == 'lo':
                if mark >= 60:
                    lo_bonus = 1
            else:
                regular_subject_points.append(level)

        # Sort descending and take top 6
        regular_subject_points.sort(reverse=True)
        top_6 = regular_subject_points[:6]
        return sum(top_6) + lo_bonus

    @classmethod
    def parse_report_card(cls, file_bytes: bytes, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Uses Gemini Vision to scan an official school report card image/PDF.
        Extracts verified Grade, Term, School, and Subjects with marks.
        """
        api_key = AIService.get_api_key()
        if not api_key:
            return {"success": False, "error": "Gemini API key not configured."}

        image_b64 = base64.b64encode(file_bytes).decode('utf-8')

        prompt = (
            "You are a strict South African high school academic records parser.\n"
            "Analyze this uploaded official school report card.\n"
            "Extract:\n"
            "1. School Name (if visible, else null)\n"
            "2. Grade (integer: 8, 9, 10, 11, or 12. Default to 11 if unclear)\n"
            "3. Term (integer: 1, 2, 3, or 4)\n"
            "4. Academic Year (integer: e.g. 2025 or 2026)\n"
            "5. Array of official subjects with their exact numerical mark (percentage 0-100) and CAPS Level (1 to 7).\n"
            "CAPS Level Scale: 80-100=7, 70-79=6, 60-69=5, 50-59=4, 40-49=3, 30-39=2, 0-29=1.\n"
            "Return ONLY a raw JSON object with this exact structure, with no markdown code fences:\n"
            "{\n"
            '  "school_name": "...",\n'
            '  "grade": 11,\n'
            '  "term": 2,\n'
            '  "academic_year": 2026,\n'
            '  "subjects": [\n'
            '    {"subject": "Mathematics", "mark": 54, "level": 4},\n'
            '    {"subject": "Physical Sciences", "mark": 46, "level": 3}\n'
            "  ]\n"
            "}"
        )

        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest"
        ]

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": mime_type, "data": image_b64}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1
            }
        }

        try:
            import certifi
            ssl_verify = certifi.where()
        except ImportError:
            ssl_verify = True

        last_error = None
        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=12, verify=ssl_verify)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            # Clean any markdown code blocks
                            clean_json_str = re.sub(r'^```json\s*', '', raw_text)
                            clean_json_str = re.sub(r'^```\s*', '', clean_json_str)
                            clean_json_str = re.sub(r'```$', '', clean_json_str).strip()

                            parsed = json.loads(clean_json_str)
                            subjects = parsed.get("subjects", [])
                            # Ensure levels and marks are valid numbers
                            clean_subjects = []
                            for s in subjects:
                                try:
                                    mark = float(s.get("mark", 0))
                                    level = int(s.get("level", 1))
                                    clean_subjects.append({
                                        "subject": str(s.get("subject", "")).strip(),
                                        "mark": round(mark),
                                        "level": level
                                    })
                                except Exception:
                                    continue

                            parsed["subjects"] = clean_subjects
                            parsed["aps_score"] = cls.calculate_aps(clean_subjects)
                            return {"success": True, "data": parsed}
                else:
                    last_error = f"{current_model}: {res.status_code} - {res.text[:120]}"
            except Exception as e:
                last_error = f"{current_model}: {e}"

        logger.warning(f"Report card parsing failed: {last_error}")
        return {"success": False, "error": last_error}

    @classmethod
    def generate_study_timetable(
        cls,
        subjects: List[Dict[str, Any]],
        target_career: str,
        grade: int = 11,
        term: int = 2
    ) -> Dict[str, Any]:
        """
        Generates an adaptive weekly study timetable heavily prioritized around struggle subjects.
        """
        api_key = AIService.get_api_key()
        if not api_key:
            return {"success": False, "error": "Gemini API key not configured."}

        subjects_summary = "\n".join([f"- {s.get('subject')}: {s.get('mark')}% (Level {s.get('level')})" for s in subjects])

        prompt = (
            f"You are an expert South African high school academic coach.\n"
            f"Student Profile:\n"
            f"- Grade: {grade}, Term: {term}\n"
            f"- Dream Career Target: {target_career}\n"
            f"- Current Official School Marks:\n{subjects_summary}\n\n"
            f"Generate an adaptive, realistic weekly study timetable (Monday to Sunday) designed to pull up their struggle subjects "
            f"so they qualify for {target_career} at a South African university.\n"
            f"Rules:\n"
            f"1. Priority 1 (Crucial Focus): Subjects with marks < 55% or required for {target_career} must get the most prime slots (60-75 min).\n"
            f"2. Priority 2 (Moderate): 55-69% get 2 slots per week.\n"
            f"3. Priority 3 (Maintenance): 70%+ get 1 maintenance slot.\n"
            f"4. Include specific South African CAPS high-yield topics for Grade {grade} Term {term} (e.g. Euclidean Geometry, Newton's Laws, Organic Chemistry, Functions).\n"
            f"5. Weekday slots typically between 16:30 and 20:30 with breaks; Saturday morning slots; Sunday light review/rest.\n\n"
            f"Return ONLY a raw JSON object with this exact structure, with no markdown fences:\n"
            "{\n"
            '  "summary": "Focus strategy explanation in 2 sentences.",\n'
            '  "target_aps": 36,\n'
            '  "struggle_subjects": ["Physical Sciences", "Mathematics"],\n'
            '  "days": {\n'
            '    "Monday": [\n'
            '      {"slot_id": "mon-1", "time": "16:30 - 17:45", "subject": "Mathematics", "type": "critical_focus", "topic": "Functions & Inverses", "goal": "Solve 5 past paper questions"},\n'
            '      {"slot_id": "mon-2", "time": "18:30 - 19:30", "subject": "English", "type": "maintenance", "topic": "Poetry Analysis", "goal": "Summarize 1 poem"}\n'
            "    ],\n"
            '    "Tuesday": [...],\n'
            '    "Wednesday": [...],\n'
            '    "Thursday": [...],\n'
            '    "Friday": [...],\n'
            '    "Saturday": [...],\n'
            '    "Sunday": [...]\n'
            "  }\n"
            "}"
        )

        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest"
        ]

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }

        try:
            import certifi
            ssl_verify = certifi.where()
        except ImportError:
            ssl_verify = True

        last_error = None
        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10, verify=ssl_verify)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            clean_json_str = re.sub(r'^```json\s*', '', raw_text)
                            clean_json_str = re.sub(r'^```\s*', '', clean_json_str)
                            clean_json_str = re.sub(r'```$', '', clean_json_str).strip()

                            parsed = json.loads(clean_json_str)
                            return {"success": True, "timetable": parsed}
                else:
                    last_error = f"{current_model}: {res.status_code} - {res.text[:120]}"
            except Exception as e:
                last_error = f"{current_model}: {e}"

        logger.warning(f"Timetable generation failed: {last_error}")
        return {"success": False, "error": last_error}

    @classmethod
    def analyze_career_requirements(
        cls,
        target_career: str,
        subjects: List[Dict[str, Any]],
        available_courses: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Dynamically evaluates university & vocational pathways in South Africa for ANY typed career.
        Identifies whether the student has Pure Mathematics vs Mathematical Literacy, evaluates
        admission feasibility, provides alternative pathways, and aligns Pace courses if relevant.
        """
        available_courses = available_courses or []

        # 1. Detect math type from student's subjects
        math_type = "none"
        math_subject_name = "Mathematics"
        math_mark = 0
        math_level = 1

        for s in subjects:
            s_name = s.get('subject', '').strip()
            s_lower = s_name.lower()
            if 'lit' in s_lower and ('math' in s_lower or 'wiskunde' in s_lower):
                math_type = "lit"
                math_subject_name = s_name
                math_mark = s.get('mark', 0)
                math_level = s.get('level', 1)
                break
            elif 'math' in s_lower or 'wiskunde' in s_lower:
                math_type = "pure"
                math_subject_name = s_name
                math_mark = s.get('mark', 0)
                math_level = s.get('level', 1)

        # Build courses summary for Gemini to match only if aligned
        courses_summary = "\n".join([
            f"- Course ID {c.get('id')}: \"{c.get('title')}\" (Category: {c.get('category')}, Pricing: {c.get('pricing_type', '')} R{c.get('price', 0)})"
            for c in available_courses
        ])

        subjects_summary = "\n".join([f"- {s.get('subject')}: {s.get('mark')}% (Level {s.get('level')})" for s in subjects])

        api_key = AIService.get_api_key()
        if not api_key:
            return cls._fallback_career_analysis(target_career, math_type, math_mark, math_subject_name, available_courses)

        prompt = (
            f"You are an expert South African Higher Education and Careers Advisor specializing in Matric, APS (Admission Point Score), and university criteria (Wits, UCT, UP, UJ, Stellenbosch, TUT, CPUT, TVETs).\n\n"
            f"Candidate Profile:\n"
            f"- Target Career: {target_career}\n"
            f"- Mathematics Subject: {math_subject_name} ({math_type.upper()}) with {math_mark}% (Level {math_level})\n"
            f"- Full School Subjects:\n{subjects_summary}\n\n"
            f"Available Pace Academy Courses (ONLY recommend if they legitimately teach skills for this career):\n"
            f"{courses_summary}\n\n"
            f"Analyze this target career and return ONLY a valid raw JSON object (no markdown, no backticks):\n"
            "{\n"
            '  "career_title": "' + target_career + '",\n'
            '  "typical_aps_required": 32,\n'
            '  "requires_pure_maths": true,\n'
            '  "maths_lit_accepted_at_university": false,\n'
            '  "maths_status": "incompatible | meets_requirement | needs_improvement | accepted_lit",\n'
            '  "maths_guidance": "Concise 1-2 sentence honest breakdown of how the student\'s math affects this career.",\n'
            '  "alternative_pathways": [\n'
            '    "Diploma / Technical pathway at TUT/CPUT if university degree requires Pure Maths",\n'
            '    "Accredited certification or bridging option"\n'
            '  ],\n'
            '  "recommended_institutions": ["Wits University", "University of Johannesburg", "Tshwane University of Technology"],\n'
            '  "key_prerequisite_subjects": ["Mathematics (Level 5+)", "Physical Sciences (Level 5+)"],\n'
            '  "aligned_pace_courses": [\n'
            '    {\n'
            '      "course_id": 15,\n'
            '      "title": "Course Title",\n'
            '      "why_aligned": "Explains how this course builds skills for this career"\n'
            '    }\n'
            '  ]\n'
            "}\n"
            "CRITICAL RULES:\n"
            "1. If the student has Mathematical Literacy, and the career (e.g. Software Engineer, Doctor, Mechanical Engineer, Data Scientist) typically demands Pure Maths for university degrees, state clearly that university degree entry requires Pure Maths, but provide the realistic Diploma (e.g. Diploma in IT / Software Dev) or TVET or certification route where Maths Lit is accepted!\n"
            "2. If the career (e.g. Lawyer, Graphic Designer, Digital Marketer, BCom Management, Nursing, Teacher, Public Relations) accepts Mathematical Literacy, set maths_lit_accepted_at_university = true and highlight that Maths Lit is accepted!\n"
            "3. In aligned_pace_courses, ONLY include a course from the provided list if it genuinely aligns with the career. If none align (e.g. Pilot, Surgeon, Dentist), return an empty array []!"
        )

        models_to_try = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest"
        ]

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2}
        }

        try:
            import certifi
            ssl_verify = certifi.where()
        except ImportError:
            ssl_verify = True

        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            try:
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10, verify=ssl_verify)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            clean_json_str = re.sub(r'^```json\s*', '', raw_text)
                            clean_json_str = re.sub(r'^```\s*', '', clean_json_str)
                            clean_json_str = re.sub(r'```$', '', clean_json_str).strip()
                            parsed = json.loads(clean_json_str)
                            return {"success": True, "analysis": parsed}
            except Exception as e:
                logger.warning(f"Career analysis failed with {current_model}: {e}")

        return {"success": True, "analysis": cls._fallback_career_analysis(target_career, math_type, math_mark, math_subject_name, available_courses)}

    @classmethod
    def _fallback_career_analysis(
        cls,
        target_career: str,
        math_type: str,
        math_mark: int,
        math_subject_name: str,
        available_courses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Rule-based fallback for South African career prerequisites."""
        c_lower = target_career.lower()
        requires_pure = any(k in c_lower for k in [
            'engineer', 'doctor', 'medicine', 'actuar', 'computer science',
            'software', 'data sci', 'physic', 'chemis', 'accountant', 'ca(sa)'
        ])

        # Careers where Maths Lit is well-accepted
        maths_lit_friendly = any(k in c_lower for k in [
            'law', 'llb', 'design', 'graphic', 'art', 'market', 'human resource', 'hr',
            'teach', 'education', 'nurs', 'journalis', 'public relation', 'pr',
            'hospitality', 'tourism', 'project management', 'business manage'
        ])

        if maths_lit_friendly:
            requires_pure = False

        typical_aps = 34
        if any(k in c_lower for k in ['doctor', 'medicine', 'actuar']):
            typical_aps = 40
        elif any(k in c_lower for k in ['engineer', 'software', 'data']):
            typical_aps = 36
        elif any(k in c_lower for k in ['law', 'account']):
            typical_aps = 34
        elif any(k in c_lower for k in ['design', 'market', 'teach', 'nurs']):
            typical_aps = 28
        else:
            typical_aps = 30

        if math_type == 'lit' and requires_pure:
            maths_status = "incompatible"
            maths_guidance = f"Traditional university BSc/BEng degrees for {target_career} require Pure Mathematics (60%+). However, Technical Diplomas (e.g. Diploma in IT) and accredited vocational bootcamps accept Mathematical Literacy."
            alternatives = [
                f"Diploma pathway at Universities of Technology (TUT, CPUT, DUT, VUT) where Maths Lit is accepted",
                f"Job-ready accredited certification on Pace Academy without university Pure Maths barriers",
                f"Matric upgrade / bridging course if intending to enter traditional university degree"
            ]
        elif math_type == 'lit' and not requires_pure:
            maths_status = "accepted_lit"
            maths_guidance = f"Mathematical Literacy is fully accepted for {target_career} across leading South African universities and colleges."
            alternatives = [
                "Bachelor's Degree entry at public universities",
                "Diploma / National Certificate vocational pathways"
            ]
        else:
            if math_mark >= 65:
                maths_status = "meets_requirement"
                maths_guidance = f"Your Pure Mathematics mark ({math_mark}%) meets standard prerequisites for {target_career}."
            else:
                maths_status = "needs_improvement"
                maths_guidance = f"Pure Mathematics is required. Aim to boost your mark from {math_mark}% to at least 65% for competitive entry."
            alternatives = ["Direct Bachelor Degree entry across South African universities"]

        # Find aligned Pace courses
        aligned_courses = []
        for c in available_courses:
            title_lower = c.get('title', '').lower()
            cat_lower = c.get('category', '').lower()
            aligned = False
            why = ""

            if any(k in c_lower for k in ['software', 'web', 'developer', 'program', 'tech', 'it', 'coder', 'computer']):
                if any(k in title_lower or k in cat_lower for k in ['web', 'html', 'css', 'programming', 'computing', 'seta']):
                    aligned = True
                    why = "Directly teaches coding and foundational tech skills needed for this career."
            elif any(k in c_lower for k in ['data', 'analyst', 'statistic']):
                if any(k in title_lower for k in ['computing', 'programming']):
                    aligned = True
                    why = "Teaches computing foundations for data management."
            elif any(k in c_lower for k in ['doctor', 'nurse', 'health', 'biomed', 'life sci', 'medic']):
                if 'life science' in title_lower:
                    aligned = True
                    why = "High school Life Sciences CAPS mastery essential for health sciences."

            if aligned:
                aligned_courses.append({
                    "course_id": c.get('id'),
                    "title": c.get('title'),
                    "category": c.get('category'),
                    "price": c.get('price'),
                    "pricing_type": c.get('pricing_type'),
                    "why_aligned": why
                })

        return {
            "career_title": target_career,
            "typical_aps_required": typical_aps,
            "requires_pure_maths": requires_pure,
            "maths_lit_accepted_at_university": not requires_pure,
            "maths_status": maths_status,
            "maths_guidance": maths_guidance,
            "alternative_pathways": alternatives,
            "recommended_institutions": ["University of Pretoria", "University of Johannesburg", "Tshwane University of Technology", "Wits University"],
            "key_prerequisite_subjects": ["Mathematics or Maths Lit", "English (HL/FAL)"],
            "aligned_pace_courses": aligned_courses
        }


