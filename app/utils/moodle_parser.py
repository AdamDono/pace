"""
Moodle .mbz Course Importer — Parser & DB Builder
===================================================
Parses a Moodle backup archive (.mbz = gzipped tar) and creates
native Pace Academy Course/Module/Section/Quiz/Assignment objects.

Usage (called from importer blueprint):
    from app.utils.moodle_parser import MoodleImporter
    result = MoodleImporter(current_user, upload_dir).import_mbz(file_path)
"""

import os
import re
import shutil
import tarfile
import tempfile
import uuid
import logging
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(el, tag, default=""):
    """Safe text extraction from an XML element child."""
    child = el.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _clean_html(html):
    """
    Minimal HTML cleanup:
    - Strip @@PLUGINFILE@@ prefixes (handled separately via file mapping)
    - Remove Moodle-specific data attributes we can't render
    """
    if not html:
        return ""
    # @@PLUGINFILE@@ is replaced later after files are copied
    html = re.sub(r'\$@NULL@\$', '', html)
    return html.strip()


def _timestamp_to_dt(ts_str):
    """Convert a Unix timestamp string to a datetime, or None."""
    try:
        ts = int(ts_str)
        if ts > 0:
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# File resolver
# ---------------------------------------------------------------------------

class FileResolver:
    """
    Moodle stores uploaded files with SHA1-hashed names inside files/.
    files.xml maps hash → original filename + path.
    We copy relevant files to the Pace Academy uploads dir and
    return a mapping of @@PLUGINFILE@@ references → new URLs.
    """

    def __init__(self, extract_dir, upload_dir):
        self.extract_dir = extract_dir
        self.upload_dir = upload_dir
        self._map = {}          # contenthash → dest_relative_path
        self._parsed = False

    def _parse(self):
        if self._parsed:
            return
        self._parsed = True
        files_xml = os.path.join(self.extract_dir, "files.xml")
        if not os.path.exists(files_xml):
            return
        tree = ET.parse(files_xml)
        root = tree.getroot()
        dest_dir = os.path.join(self.upload_dir, "imported")
        os.makedirs(dest_dir, exist_ok=True)

        for file_el in root.findall(".//file"):
            contenthash = _text(file_el, "contenthash")
            filename    = _text(file_el, "filename")
            filepath    = _text(file_el, "filepath", "/")
            component   = _text(file_el, "component")
            filearea    = _text(file_el, "filearea")

            if not contenthash or filename in (".", ""):
                continue

            # Source: files/<first2chars>/<hash>
            src = os.path.join(
                self.extract_dir, "files",
                contenthash[:2], contenthash
            )
            if not os.path.exists(src):
                continue

            # Destination: uploaded/imported/<uuid>_<filename>
            unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
            dest = os.path.join(dest_dir, unique_name)
            try:
                shutil.copy2(src, dest)
                rel = f"imported/{unique_name}"
                self._map[contenthash] = rel
                # Also map by original filepath+filename (for @@PLUGINFILE@@ replacement)
                self._map[contenthash] = rel
                # Also map by original filepath+filename and filename alone
                key = (filepath.rstrip("/") + "/" + filename).lstrip("/")
                self._map[key] = rel
                self._map[filename] = rel
            except Exception as e:
                logger.warning(f"Could not copy file {filename}: {e}")

    def resolve_html(self, html):
        """Replace @@PLUGINFILE@@/path/to/file.ext references and YouTube links in HTML."""
        self._parse()
        if not html:
            return html

        def replacer(m):
            raw_path = m.group(1).lstrip("/")
            filename_only = raw_path.split("/")[-1]
            rel = self._map.get(raw_path) or self._map.get(filename_only)
            
            if not rel:
                for k, v in self._map.items():
                    if k.endswith(filename_only):
                        rel = v
                        break
            
            if rel:
                file_url = f"/static/uploads/{rel}"
                if filename_only.lower().endswith(".h5p"):
                    return f'''
                    <div class="my-6 p-6 bg-amber-50/90 border border-amber-200 rounded-3xl shadow-sm">
                        <div class="flex items-center space-x-3 mb-2">
                            <span class="text-3xl">🧩</span>
                            <div>
                                <h4 class="font-bold text-gray-900 text-base">Interactive H5P Content ({filename_only})</h4>
                                <p class="text-xs text-amber-900/80">Imported Moodle Interactive Activity</p>
                            </div>
                        </div>
                        <p class="text-xs text-gray-600 mb-4 leading-relaxed">This interactive exercise was migrated from Moodle. You can download the full H5P package below or view interactive modules on Lumi.</p>
                        <a href="{file_url}" download class="inline-flex items-center text-xs font-bold bg-amber-600 text-white px-5 py-2.5 rounded-xl shadow-md hover:bg-amber-700 transition-all">
                            <span>Download {filename_only} Package</span>
                        </a>
                    </div>
                    '''
                elif any(filename_only.lower().endswith(ext) for ext in ['.mp4', '.webm', '.mov', '.m4v']):
                    return f'''
                    <div class="my-6 w-full rounded-3xl overflow-hidden shadow-lg border border-gray-100 bg-black">
                        <video controls class="w-full max-h-[500px] rounded-3xl">
                            <source src="{file_url}">
                            Your browser does not support HTML5 video playback.
                        </video>
                    </div>
                    '''
                return file_url

            # Fallback if file reference was not found in files.xml
            if filename_only.lower().endswith(".h5p"):
                return f'''
                <div class="my-6 p-6 bg-amber-50/90 border border-amber-200 rounded-3xl shadow-sm">
                    <div class="flex items-center space-x-3 mb-2">
                        <span class="text-3xl">🧩</span>
                        <div>
                            <h4 class="font-bold text-gray-900 text-base">Interactive H5P Activity</h4>
                            <p class="text-xs text-amber-900/80">File reference: {filename_only}</p>
                        </div>
                    </div>
                    <p class="text-xs text-gray-600 leading-relaxed">Interactive exercise imported from Moodle backup.</p>
                </div>
                '''
            return m.group(0)

        html = re.sub(r'@@PLUGINFILE@@(/[^"\'> ]*)', replacer, html)

        # Convert raw YouTube links in text to embedded YouTube video players
        def youtube_replacer(m):
            yt_url = m.group(0)
            return _embed_video_html(yt_url)

        html = re.sub(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+', youtube_replacer, html)
        
        return html


# ---------------------------------------------------------------------------
# Main importer
# ---------------------------------------------------------------------------

class MoodleImporter:
    """
    Orchestrates the full import from .mbz file → Pace Academy DB objects.
    """

    # Moodle activity types we know how to handle
    SUPPORTED_TYPES = {"page", "resource", "url", "assign", "quiz", "label", "folder"}

    def __init__(self, teacher_user, upload_dir):
        self.teacher = teacher_user
        self.upload_dir = upload_dir
        self.report = {
            "course_title": "",
            "modules_created": 0,
            "sections_created": 0,
            "quizzes_created": 0,
            "quiz_questions_imported": 0,
            "assignments_created": 0,
            "files_copied": 0,
            "skipped_activities": [],
            "warnings": [],
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def import_mbz(self, mbz_path):
        """
        Main entry point. Returns (course, report_dict) or raises on fatal error.
        """
        extract_dir = tempfile.mkdtemp(prefix="moodle_import_")
        try:
            self._extract(mbz_path, extract_dir)
            course = self._build(extract_dir)
            return course, self.report
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)

    def preview_mbz(self, mbz_path):
        """
        Dry-run: parse the .mbz and return a preview dict without touching the DB.
        """
        extract_dir = tempfile.mkdtemp(prefix="moodle_preview_")
        try:
            self._extract(mbz_path, extract_dir)
            return self._parse_preview(extract_dir)
        finally:
            shutil.rmtree(extract_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract(self, mbz_path, dest):
        if not tarfile.is_tarfile(mbz_path):
            raise ValueError("File is not a valid .mbz (tar) archive.")
        with tarfile.open(mbz_path, "r:gz") as tar:
            # Security: filter out absolute paths / path traversal
            members = [m for m in tar.getmembers()
                       if not m.name.startswith("/") and ".." not in m.name]
            tar.extractall(dest, members=members)

    # ------------------------------------------------------------------
    # Preview (no DB writes)
    # ------------------------------------------------------------------

    def _parse_preview(self, extract_dir):
        course_meta = self._parse_course_meta(extract_dir)
        sections    = self._parse_section_list(extract_dir)
        activities  = self._collect_activities(extract_dir)

        preview_sections = []
        for sec in sections:
            acts = [a for a in activities if a["section_id"] == sec["id"]]
            preview_sections.append({
                "name": sec["name"] or f"Section {sec['number']}",
                "activities": [{"type": a["type"], "name": a["name"]} for a in acts],
            })

        return {
            "course_title":   course_meta.get("fullname", "Untitled"),
            "course_summary": course_meta.get("summary", ""),
            "section_count":  len(sections),
            "activity_count": len(activities),
            "sections":       preview_sections,
        }

    # ------------------------------------------------------------------
    # Build (DB writes)
    # ------------------------------------------------------------------

    def _build(self, extract_dir):
        from app import db
        from app.models import Course, Module, Section, Assignment, Quiz, QuizQuestion

        course_meta  = self._parse_course_meta(extract_dir)
        sections_raw = self._parse_section_list(extract_dir)
        activities   = self._collect_activities(extract_dir)
        file_res     = FileResolver(extract_dir, self.upload_dir)

        title = (course_meta.get("fullname") or "Imported Course")[:100]
        self.report["course_title"] = title

        # --- Create Course ---
        course = Course(
            teacher_id=self.teacher.id,
            title=title,
            description=_clean_html(course_meta.get("summary") or "Imported from Moodle"),
            status="draft",
            is_draft=True,
            category=course_meta.get("category"),
            language=course_meta.get("lang", "english"),
            created_at=datetime.utcnow(),
        )
        db.session.add(course)
        db.session.flush()   # get course.id

        # --- Create Modules from Moodle sections ---
        sec_order = 0
        for sec_raw in sections_raw:
            sec_name = (sec_raw.get("name") or f"Section {sec_raw['number']}").strip()
            if not sec_name or sec_name.lower() in ("", "general"):
                # Moodle section 0 is "General" — still include it
                sec_name = "General" if sec_raw["number"] == 0 else sec_name

            module = Module(
                course_id=course.id,
                title=sec_name[:100],
                description=_clean_html(sec_raw.get("summary") or ""),
                order=sec_order,
            )
            db.session.add(module)
            db.session.flush()
            self.report["modules_created"] += 1
            sec_order += 1

            # --- Activities belonging to this section ---
            sec_activities = [a for a in activities if a["section_id"] == sec_raw["id"]]
            act_order = 0

            for act in sec_activities:
                atype = act.get("type", "")

                if atype == "label":
                    # Append label HTML to the module description
                    if act.get("content"):
                        module.description = (module.description or "") + "\n" + _clean_html(act["content"])
                    continue

                if atype in ("page", "resource", "url", "folder"):
                    self._create_text_section(
                        db, course, module, act, file_res, act_order
                    )
                    act_order += 1

                elif atype == "assign":
                    self._create_assignment_section(
                        db, course, module, act, file_res, act_order
                    )
                    act_order += 1

                elif atype == "quiz":
                    self._create_quiz_section(
                        db, course, module, act, extract_dir, file_res, act_order
                    )
                    act_order += 1

                else:
                    self.report["skipped_activities"].append(
                        f"'{act.get('name', atype)}' ({atype}) — not supported"
                    )

        db.session.commit()
        return course

    # ------------------------------------------------------------------
    # Section creators
    # ------------------------------------------------------------------

def _embed_video_html(url, title="Video"):
    """Convert YouTube, Vimeo, or direct MP4/video URLs into responsive embedded player HTML."""
    if not url:
        return ""
    
    url_clean = url.strip()
    
    # YouTube (youtu.be/ID or youtube.com/watch?v=ID or youtube.com/embed/ID)
    if "youtube.com" in url_clean or "youtu.be" in url_clean:
        video_id = None
        if "youtu.be/" in url_clean:
            video_id = url_clean.split("youtu.be/")[1].split("?")[0].split("&")[0]
        elif "v=" in url_clean:
            video_id = url_clean.split("v=")[1].split("&")[0]
        elif "embed/" in url_clean:
            video_id = url_clean.split("embed/")[1].split("?")[0]
            
        if video_id:
            embed_url = f"https://www.youtube.com/embed/{video_id}"
            return f'<div class="my-4 aspect-video w-full rounded-2xl overflow-hidden shadow-lg border border-gray-100 bg-black"><iframe src="{embed_url}" class="w-full h-full" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe></div>'
            
    # Vimeo
    if "vimeo.com" in url_clean:
        parts = url_clean.rstrip("/").split("/")
        if parts[-1].isdigit():
            video_id = parts[-1]
            embed_url = f"https://player.vimeo.com/video/{video_id}"
            return f'<div class="my-4 aspect-video w-full rounded-2xl overflow-hidden shadow-lg border border-gray-100 bg-black"><iframe src="{embed_url}" class="w-full h-full" allowfullscreen></iframe></div>'

    # Direct Video File (.mp4, .webm, .mov, .m4v, .ogg)
    if any(url_clean.lower().endswith(ext) for ext in ['.mp4', '.webm', '.mov', '.m4v', '.ogg']) or '/static/uploads/' in url_clean:
        return f'<div class="my-4 w-full rounded-2xl overflow-hidden shadow-lg border border-gray-100 bg-black"><video controls class="w-full max-h-[520px] rounded-2xl"><source src="{url_clean}">Your browser does not support HTML5 video playback.</video></div>'
        
    return f'<p class="my-3"><a href="{url_clean}" target="_blank" rel="noopener" class="inline-flex items-center text-blue-600 hover:text-blue-800 font-bold underline"><span>🎥 {title}</span> <span class="ml-1">↗</span></a></p>'


    def _create_text_section(self, db, course, module, act, file_res, order):
        from app.models import Section
        raw_content = act.get("content") or ""
        ext_url = act.get("url") or ""
        content = file_res.resolve_html(raw_content or ext_url)
        
        video_url = None
        media_type = "text"

        # Check if external URL or resolved file is a video
        if ext_url:
            if any(k in ext_url.lower() for k in ['youtube.com', 'youtu.be', 'vimeo.com', '.mp4', '.webm', '.mov', '.m4v']):
                video_url = ext_url
                media_type = "video"
                video_embed = _embed_video_html(ext_url, act.get("name", "Video"))
                if ext_url not in content:
                    content = video_embed + (f"<br>{content}" if content else "")
        
        # Scan content for video files/iframes/embeds
        if not video_url and content:
            if '<iframe' in content or '<video' in content or '.mp4' in content:
                media_type = "video"
                v_match = re.search(r'src=["\'](https?://[^"\']+|\/static\/uploads\/[^"\']+)["\']', content)
                if v_match:
                    video_url = v_match.group(1)

        if not content:
            content = f"<p><em>{act.get('name', 'Resource')}</em></p>"

        atype = act.get("type", "")
        if atype == "url":
            sect_type = "url"
        elif atype == "resource":
            sect_type = "resource"
        else:
            sect_type = "lesson"

        section = Section(
            course_id=course.id,
            module_id=module.id,
            title=(act.get("name") or "Untitled")[:150],
            content=content,
            video_url=video_url,
            section_type=sect_type,
            media_type=media_type,
            order=order,
            is_published=False,
        )
        db.session.add(section)
        self.report["sections_created"] += 1

    def _create_assignment_section(self, db, course, module, act, file_res, order):
        from app.models import Section, Assignment
        section = Section(
            course_id=course.id,
            module_id=module.id,
            title=(act.get("name") or "Assignment")[:150],
            content=file_res.resolve_html(act.get("content") or ""),
            section_type="assignment",
            media_type="text",
            order=order,
            is_published=False,
        )
        db.session.add(section)
        db.session.flush()
        self.report["sections_created"] += 1

        assignment = Assignment(
            section_id=section.id,
            title=(act.get("name") or "Assignment")[:100],
            description=file_res.resolve_html(act.get("content") or ""),
            due_date=_timestamp_to_dt(act.get("duedate")),
            allow_file_upload=True,
        )
        db.session.add(assignment)
        self.report["assignments_created"] += 1

    def _create_quiz_section(self, db, course, module, act, extract_dir, file_res, order):
        from app.models import Section, Quiz, QuizQuestion

        section = Section(
            course_id=course.id,
            module_id=module.id,
            title=(act.get("name") or "Quiz")[:150],
            content=file_res.resolve_html(act.get("content") or ""),
            section_type="quiz",
            media_type="text",
            order=order,
            is_published=False,
        )
        db.session.add(section)
        db.session.flush()
        self.report["sections_created"] += 1

        quiz = Quiz(
            section_id=section.id,
            title=(act.get("name") or "Quiz")[:100],
            time_limit=int(act["timelimit"]) // 60 if act.get("timelimit") else None,
            passing_score=float(act.get("gradepass") or 60.0),
            randomize_questions=act.get("shufflequestions") == "1",
            show_correct_answers=True,
        )
        db.session.add(quiz)
        db.session.flush()
        self.report["quizzes_created"] += 1

        # Parse questions from quiz XML
        questions = self._parse_quiz_questions(extract_dir, act["activity_id"])
        imported_q = 0
        for q in questions:
            if q["qtype"] != "multichoice":
                self.report["warnings"].append(
                    f"Quiz '{act.get('name')}': skipped '{q['name']}' ({q['qtype']}) — only MCQ supported"
                )
                continue

            options = q.get("options", [])
            if len(options) < 2:
                continue

            # Map options to A/B/C/D
            correct_letter = None
            opt_map = {}
            letters = ["a", "b", "c", "d"]
            for i, opt in enumerate(options[:4]):
                letter = letters[i]
                opt_map[letter] = opt["text"]
                if opt.get("correct"):
                    correct_letter = letter

            if not correct_letter:
                self.report["warnings"].append(
                    f"Quiz '{act.get('name')}': skipped '{q['name']}' — no correct answer identified"
                )
                continue

            qq = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q["text"][:200],
                option_a=opt_map.get("a", "")[:100],
                option_b=opt_map.get("b", "")[:100],
                option_c=opt_map.get("c", "")[:100] if "c" in opt_map else None,
                option_d=opt_map.get("d", "")[:100] if "d" in opt_map else None,
                correct_answer=correct_letter.upper(),
            )
            db.session.add(qq)
            imported_q += 1

        self.report["quiz_questions_imported"] += imported_q

    # ------------------------------------------------------------------
    # XML parsers
    # ------------------------------------------------------------------

    def _parse_course_meta(self, extract_dir):
        xml_path = os.path.join(extract_dir, "course", "course.xml")
        if not os.path.exists(xml_path):
            return {}
        tree = ET.parse(xml_path)
        root = tree.getroot()
        course_el = root.find("course") or root
        return {
            "fullname":  _text(course_el, "fullname"),
            "shortname": _text(course_el, "shortname"),
            "summary":   _text(course_el, "summary"),
            "lang":      _text(course_el, "lang"),
            "category":  _text(course_el, "category"),
        }

    def _parse_section_list(self, extract_dir):
        """
        Returns list of dicts sorted by section number (Moodle's ordering).
        Each dict: {id, number, name, summary, sequence}
        sequence is a comma-separated list of activity module IDs in display order.
        """
        sections_dir = os.path.join(extract_dir, "sections")
        if not os.path.exists(sections_dir):
            return []
        sections = []
        for entry in sorted(os.listdir(sections_dir)):
            xml_path = os.path.join(sections_dir, entry, "section.xml")
            if not os.path.exists(xml_path):
                continue
            tree = ET.parse(xml_path)
            root = tree.getroot()
            sections.append({
                "id":       root.get("id") or _text(root, "id"),
                "number":   int(_text(root, "number") or 0),
                "name":     _text(root, "name"),
                "summary":  _text(root, "summary"),
                "sequence": _text(root, "sequence"),  # e.g. "3,5,7"
            })
        sections.sort(key=lambda s: s["number"])
        return sections

    def _collect_activities(self, extract_dir):
        """
        Parse all activity folders. Returns a flat list of activity dicts.
        Each dict has: type, activity_id, section_id, name, content, + type-specific fields.
        """
        # Build a section_id lookup from the moodle_backup.xml manifest
        section_lookup = self._build_section_lookup(extract_dir)

        activities_dir = os.path.join(extract_dir, "activities")
        if not os.path.exists(activities_dir):
            return []

        activities = []
        for folder in sorted(os.listdir(activities_dir)):
            folder_path = os.path.join(activities_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            # folder name format: <type>_<moduleid>  e.g. "page_123", "quiz_456"
            parts = folder.rsplit("_", 1)
            if len(parts) != 2:
                continue
            atype, mod_id = parts[0], parts[1]

            if atype not in self.SUPPORTED_TYPES:
                # Record skip but don't spam
                inforef = os.path.join(folder_path, "inforef.xml")
                name = atype
                self.report["skipped_activities"].append(f"'{name}' ({atype}) — not supported")
                continue

            act = self._parse_activity(folder_path, atype, mod_id)
            if act:
                act["section_id"] = section_lookup.get(mod_id)
                act["type"] = atype
                act["activity_id"] = mod_id
                activities.append(act)

        # Sort by the section ordering
        return activities

    def _build_section_lookup(self, extract_dir):
        """
        Returns {module_id_str: section_id_str} by reading moodle_backup.xml.
        This tells us which section each activity belongs to.
        """
        backup_xml = os.path.join(extract_dir, "moodle_backup.xml")
        lookup = {}
        if not os.path.exists(backup_xml):
            return lookup
        tree = ET.parse(backup_xml)
        root = tree.getroot()
        for activity_el in root.findall(".//activity"):
            mod_id = activity_el.get("moduleid") or _text(activity_el, "moduleid")
            sec_id = _text(activity_el, "sectionid")
            if mod_id and sec_id:
                lookup[mod_id] = sec_id
        return lookup

    def _parse_activity(self, folder_path, atype, mod_id):
        """Parse a single activity folder into a dict."""
        try:
            if atype == "page":
                return self._parse_page(folder_path)
            elif atype == "resource":
                return self._parse_resource(folder_path)
            elif atype == "url":
                return self._parse_url(folder_path)
            elif atype == "label":
                return self._parse_label(folder_path)
            elif atype == "assign":
                return self._parse_assign(folder_path)
            elif atype == "quiz":
                return self._parse_quiz_meta(folder_path)
            elif atype == "folder":
                return self._parse_folder(folder_path)
        except Exception as e:
            logger.warning(f"Error parsing activity {atype}_{mod_id}: {e}")
        return None

    def _parse_page(self, folder_path):
        xml = os.path.join(folder_path, "page.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        page = root.find("page") or root
        return {
            "name":    _text(page, "name"),
            "content": _text(page, "content"),
        }

    def _parse_resource(self, folder_path):
        xml = os.path.join(folder_path, "resource.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        res = root.find("resource") or root
        name = _text(res, "name") or "Resource"
        # Content will be a file download link resolved later
        return {
            "name":    name,
            "content": f"<p><strong>📎 {name}</strong> — file resource</p>",
        }

    def _parse_url(self, folder_path):
        xml = os.path.join(folder_path, "url.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        url_el = root.find("url") or root
        name    = _text(url_el, "name") or "Link"
        ext_url = _text(url_el, "externalurl")
        return {
            "name":    name,
            "content": f'<p><a href="{ext_url}" target="_blank" rel="noopener">{name}</a></p>',
            "url":     ext_url,
        }

    def _parse_label(self, folder_path):
        xml = os.path.join(folder_path, "label.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        label = root.find("label") or root
        return {
            "name":    _text(label, "name") or "Label",
            "content": _text(label, "intro"),
        }

    def _parse_folder(self, folder_path):
        xml = os.path.join(folder_path, "folder.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        folder_el = root.find("folder") or root
        name = _text(folder_el, "name") or "Folder"
        return {
            "name":    name,
            "content": f"<p><strong>📁 {name}</strong> — folder resource</p>",
        }

    def _parse_assign(self, folder_path):
        xml = os.path.join(folder_path, "assign.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        assign = root.find("assign") or root
        return {
            "name":     _text(assign, "name"),
            "content":  _text(assign, "intro"),
            "duedate":  _text(assign, "duedate"),
        }

    def _parse_quiz_meta(self, folder_path):
        xml = os.path.join(folder_path, "quiz.xml")
        if not os.path.exists(xml):
            return None
        tree = ET.parse(xml)
        root = tree.getroot()
        quiz = root.find("quiz") or root
        return {
            "name":             _text(quiz, "name"),
            "content":          _text(quiz, "intro"),
            "timelimit":        _text(quiz, "timelimit"),
            "gradepass":        _text(quiz, "gradepass"),
            "shufflequestions": _text(quiz, "shufflequestions"),
        }

    def _parse_quiz_questions(self, extract_dir, activity_id):
        """
        Parse questions from the questions.xml inside the quiz activity folder.
        Returns list of question dicts with type, text, and answer options.
        """
        # Questions can be in activities/quiz_<id>/questions.xml or
        # in a shared questions bank at questions/questions.xml
        candidates = [
            os.path.join(extract_dir, "activities", f"quiz_{activity_id}", "questions.xml"),
            os.path.join(extract_dir, "questions", "questions.xml"),
        ]
        xml_path = next((p for p in candidates if os.path.exists(p)), None)
        if not xml_path:
            return []

        questions = []
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for q_el in root.findall(".//question"):
                qtype = q_el.get("type") or _text(q_el, "qtype") or ""
                if not qtype:
                    qtype_el = q_el.find("qtype")
                    qtype = (qtype_el.text or "").strip() if qtype_el is not None else ""

                name_el = q_el.find(".//name/text") or q_el.find("name")
                name = (name_el.text or "Question").strip() if name_el is not None else "Question"

                text_el = q_el.find(".//questiontext/text") or q_el.find("questiontext")
                text = ""
                if text_el is not None:
                    text = re.sub(r"<[^>]+>", " ", text_el.text or "").strip()

                options = []
                for ans in q_el.findall(".//answer"):
                    ans_text_el = ans.find("text") or ans.find("answertext")
                    ans_text = ""
                    if ans_text_el is not None:
                        ans_text = re.sub(r"<[^>]+>", " ", ans_text_el.text or "").strip()
                    fraction_el = ans.find("fraction")
                    fraction = float(fraction_el.text or 0) if fraction_el is not None else 0.0
                    options.append({
                        "text":    ans_text,
                        "correct": fraction > 0,
                    })

                questions.append({
                    "qtype":   qtype,
                    "name":    name,
                    "text":    text,
                    "options": options,
                })
        except Exception as e:
            logger.warning(f"Error parsing quiz questions for activity {activity_id}: {e}")

        return questions
