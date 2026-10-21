# 🧠 PACE AI Personal Tutor & Career Pathway Engine
## Comprehensive System Specification & Future Roadmap

**Challenge Category:** Youth Employment & Work Readiness  
**Target Audience:** Grade 10–12 High School Learners, Matriculants, TVET / Tertiary Students, and Young Job Seekers  
**Status:** In Development / Hackathon Feature Specification  
**Version:** 2.0 (Full Diagnostic & Predictive Architecture)

---

## 1. Executive Summary & Strategic Positioning

### The Core Problem in South Africa:
South Africa suffers from a broken education-to-employment pipeline. Over 50% of youth are unemployed, not because of a lack of ambition, but because of two structural failures:
1. **The High School Bottleneck:** Learners in Grades 10–12 struggle through abstract STEM subjects (like Life Sciences and Mathematics) with passive textbooks and overcrowded classrooms. Without timely academic support, they underperform, fail Matric, or achieve low Admission Point Scores (APS), shutting them out of tertiary education and high-demand careers.
2. **The Career Guidance Blindspot:** Millions of learners reach Matric without any data-driven guidance on what careers match their strengths, what APS score they need, or how high-demand technical and vocational micro-credentials can guarantee employment if university isn't viable.

### The PACE Academy Solution:
The **PACE AI Personal Tutor & Career Pathway Engine** bridges high school excellence with youth work readiness. It is **not a generic chatbot** that simply gives away homework answers. Instead, it is an **intelligent diagnostic companion and predictive career advisor** that:
* **Diagnoses Root Misconceptions (Socratic Learning):** Figures out *why* a student is struggling and guides them to the answer using step-by-step Socratic questioning and interactive 3D visual anchors.
* **Powers Grade 10–12 Academic Excellence:** Directly supports the CAPS curriculum (Life Sciences with 3D anatomical models, Physical Sciences, Mathematics) so learners master difficult exam topics and maximize their Matric results.
* **Forecasts APS & Career Pathways:** Analyzes school report marks, subject combinations, and platform engagement to forecast the student's Admission Point Score (APS) and generate hyper-personalized career roadmaps into tech, healthcare, and engineering.
* **Predicts Academic Risk (Hackathon 'Intelligence' 10/10):** Uses learning telemetry (time on 3D hotspots, code compilation failures, quiz trends) to forecast dropout risks and trigger proactive interventions before a student fails.

---

## 2. Core Architectural Pillars

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PACE AI INTELLIGENT TUTOR PLATFORM                              │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
           ┌───────────────────────────────┼───────────────────────────────┐
           ▼                               ▼                               ▼
┌───────────────────────┐      ┌───────────────────────┐      ┌────────────────────────┐
│ 1. SOCRATIC DIAGNOSTIC│      │ 2. PREDICTIVE EARLY   │      │ 3. CAREER & APS        │
│    ACADEMIC TUTOR     │      │    WARNING ENGINE     │      │    FORECASTING ENGINE  │
├───────────────────────┤      ├───────────────────────┤      ├────────────────────────┤
│ • Root-cause probing  │      │ • Telemetry analyzer  │      │ • Report card parser   │
│ • CAPS Grade 10-12    │      │ • Dropout forecasting │      │ • Dynamic APS calculator│
│ • 3D Hotspot grounding│      │ • Concept mastery %   │      │ • High-demand pathway  │
│ • Anti-cheating guard │      │ • Automated nudges    │      │   matching             │
└───────────────────────┘      └───────────────────────┘      └────────────────────────┘
```

---

## 3. Pillar 1: Socratic Diagnostic Academic Tutor (Grade 10–12 & Technical)

### A. The Socratic Diagnostic Flow vs. Generic Chatbots
Traditional AI tools (like ChatGPT) give students direct answers, encouraging passive reliance and academic dishonesty. The PACE AI Tutor acts like a patient, expert teacher:

```
[Student]: "What is the answer to question 3 on the heart?"
      │
      ▼
[PACE AI]: "I won't give you the answer directly, but let's figure it out together!
            Look at Hotspot #2 on the 3D Heart model above.
            Notice how thick that muscular wall is compared to the right side.
            Why do you think the left ventricle needs so much more muscle power?"
      │
      ▼
[Student]: "Because it pumps blood further?"
      │
      ▼
[PACE AI]: "Spot on! It pumps oxygenated blood to the entire body via the aorta.
            Now, look back at Question 3—which option matches what you just discovered?"
```

### B. Curriculum & 3D Spatial Grounding
The AI Tutor has full bidirectional awareness of the active lesson canvas:
1. **3D Model Context:** If a student is studying the *3D Guide to a DNA Molecule* or *Human Heart*, the AI knows which hotspot pin the student has clicked and references the exact spatial landmark.
2. **Code Sandbox Context:** In technical courses, if a student's Python code throws an `IndexError`, the AI parses the AST (Abstract Syntax Tree) and asks targeted questions to guide the student to spot their off-by-one error.
3. **South African CAPS Curriculum Grounding:** Pre-loaded with South African Department of Basic Education (DBE) curriculum standards for Grade 10–12 Life Sciences, Physical Sciences, and Math.

---

## 4. Pillar 2: Predictive Early Warning & Mastery Engine (Hackathon "Intelligence")

This pillar directly satisfies the judging criterion: *"Can the app 'think' for itself, forecast, and predict the user’s likely future behaviour by analyzing patterns in data inputs?"*

### A. Input Data Telemetry Matrix
The system continuously streams fine-grained student interaction data:
* **3D Spatial Engagement:** Time spent rotating models, zooming, and interacting with hotspot descriptions.
* **Code Execution Velocity:** Number of failed syntax compilations, execution runtime errors, and time between runs.
* **Quiz & Assessment Dynamics:** Hesitation time per question, answer switching behavior, and repeated failures on specific learning objectives.
* **Reading Pace & Retention:** Scroll velocity compared against average reading comprehension benchmarks.

### B. Predictive Models & Risk Algorithms
```python
# Conceptual Formula for Student Mastery Probability
Mastery_Score = (
    (Quiz_First_Attempt_Rate * 0.35) +
    (Spatial_3D_Interaction_Depth * 0.25) +
    (Code_Sandbox_Success_Ratio * 0.25) +
    (Consistency_Interval_Score * 0.15)
)

if Mastery_Score < 0.50:
    Risk_Status = "HIGH_DROPOUT_RISK"
    Trigger_Proactive_Intervention()
```

### C. Proactive Interventions (The App "Thinking Ahead")
* If the predictive model detects a student struggling on *Protein Synthesis* in Grade 12 Life Sciences, the tutor does not wait for them to fail the exam.
* **Automatic Proactive Nudge:** A notification pops up:  
  *"Hey Thabo! We noticed the transcription step was tricky on the quiz. Let's do a 3-minute interactive check on the 3D DNA model before moving to translation."*

---

## 5. Pillar 3: High School Career Guidance & APS Forecasting Engine

### A. The Problem It Solves
Most high schoolers pick university degrees blindly or don't know what an Admission Point Score (APS) is until it is too late in Grade 12. PACE bridges Grade 10–12 directly into high-income employment opportunities.

### B. Key Engine Capabilities:
1. **School Report Card Evaluator:**
   * Learners input or upload their term marks (Grade 10, 11, or 12).
   * Subjects tracked: English (HL/FAL), Mathematics / Math Literacy, Life Sciences, Physical Sciences, Information Technology, Accounting, etc.
2. **Dynamic APS Calculator:**
   * Automatically calculates current APS based on DBE grading scales (Levels 1–7).
   * Simulates "What-If" scenarios: *"If you increase your Life Sciences mark by 8% in Term 3, your APS rises to 34, unlocking Biomedical Science at Wits/UP."*
3. **Dual-Track Pathway Recommendations:**
   * **Track A: University / Degree Pathways:** Recommends specific university faculties matching their current APS and subject prerequisites.
   * **Track B: Direct-to-Employment Technical & Micro-Credential Pathways:** For learners whose APS or financial situation does not allow university, PACE generates immediate, debt-free skills pathways:
     * *Example:* Grade 11 Math Literacy + Tech Interest $\rightarrow$ PACE Cloud Computing & Data Literacy Track $\rightarrow$ Entry-Level Junior Cloud Practitioner / Data Wrangler jobs.

---

## 6. UI / UX Design Blueprint

### A. In-Course Socratic AI Drawer
* **Trigger:** Floating glassmorphic button with pulsing indicator at the bottom-right of the course reader: `✨ Ask AI Tutor`.
* **Side Drawer:** Slides out smoothly (420px desktop, full-screen mobile).
* **Context Banner:** Displays active topic badge, e.g., `📍 Grade 11 Life Sciences: Cardiovascular System`.
* **Interactive Quick Chips:**
  * 🔍 *"Why is this concept important for my exam?"*
  * 🧊 *"Explain what this 3D model hotspot shows."*
  * 🧪 *"Test me with an exam-style multiple-choice question."*
  * 💡 *"I don't get this paragraph—explain it using a real-world analogy."*

### B. Student Career & Academic Command Center (`/student/career-pathway`)
* **APS Score Card:** Visual radial gauge showing current predicted APS (e.g., `32 / 42 - Bachelor Degree Pass`).
* **Subject Breakdown Table:** Lists subjects, current marks, target marks, and recommended focus areas.
* **Career Match Cards:** High-matching careers with market demand ratings in South Africa, median starting salaries, and required PACE certifications.

---

## 7. Backend Architecture & Data Schema

### A. Database Models (`app/models.py`)

```python
class StudentReportCard(db.Model):
    __tablename__ = 'student_report_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grade = db.Column(db.Integer, nullable=False) # 10, 11, 12
    term = db.Column(db.Integer, nullable=False)  # 1, 2, 3, 4
    year = db.Column(db.Integer, nullable=False)
    subjects_data = db.Column(db.JSON, nullable=False) # e.g. {"Mathematics": 68, "Life Sciences": 74}
    calculated_aps = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StudentLearningTelemetry(db.Model):
    __tablename__ = 'student_learning_telemetry'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    time_spent_seconds = db.Column(db.Integer, default=0)
    spatial_3d_events = db.Column(db.Integer, default=0) # Hotspot clicks, rotations
    quiz_attempts = db.Column(db.Integer, default=0)
    code_compilations = db.Column(db.Integer, default=0)
    mastery_probability = db.Column(db.Float, default=1.0)
    risk_level = db.Column(db.String(20), default='low') # low, medium, high
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### B. Socratic System Prompt Architecture (`app/services/ai_service.py`)

```python
SOCRATIC_TUTOR_SYSTEM_PROMPT = """
You are the PACE Academy Intelligent Personal Tutor, supporting South African learners in high school (Grade 10-12 CAPS) and technical career programs.

CONTEXT OF THIS LESSON:
Lesson Title: {lesson_title}
Subject / Module: {module_title}
Active 3D Spatial Models: {active_3d_models_or_hotspots}
Current Text Content: \"\"\"{lesson_content_summary}\"\"\"

CORE PEDAGOGICAL RULES:
1. THE SOCRATIC DIAGNOSTIC METHOD: Never simply give the student the direct answer to questions or quiz problems. 
   - Ask clarifying diagnostic questions to isolate where their understanding breaks down.
   - Use vivid South African analogies and everyday visual references.
   - If a 3D model is present in the lesson, explicitly reference the spatial landmarks and hotspot pins.
2. TONE & EMPOWERMENT: Be encouraging, patient, authoritative, and empowering. Address the student with dignity.
3. CAREER CONNECTION: When relevant, briefly connect the concept to real-world jobs in South Africa (e.g., how understanding DNA relates to biotechnology careers or medical diagnostics).
4. ACADEMIC INTEGRITY: If the student asks for exam answers or essay generation, guide their thinking instead.
"""
```

---

## 8. Hackathon Judging Matrix Alignment

| Judging Criterion | Score Potential | How PACE Demonstrates It |
| :--- | :---: | :--- |
| **Product (0–10)** | **10** | Fully operational platform with live 3D models, code sandbox, automated certification, and structured lessons. |
| **Creativity (0–10)** | **10** | First platform in South Africa combining 3D spatial WebGL simulation with diagnostic Socratic tutoring. |
| **Usability (0–10)** | **10** | Mobile-first, responsive, zero-install 3D viewer, intuitive sliding drawer, and clean progress indicators. |
| **Sustainability (0–10)**| **10** | Scalable B2B model licensing to schools, skills development providers, and SETA accredited institutions. |
| **Impact (0–10)** | **10** | Direct assault on South Africa's 50%+ youth unemployment by rescuing high schoolers and training work-ready youth. |
| **Intelligence (0–10)** | **10** | Goes beyond a basic chatbot: predicts student mastery, forecasts dropout risk from telemetry, and dynamically calculates APS career pathways. |
| **Presentation (0–10)** | **10** | Engaging live demo contrasting standard static textbooks with rotating 3D models and an AI tutor that diagnoses understanding live. |

---

## 9. Implementation Roadmap & Execution Checklist

- [x] **Phase 1 (Complete):** Core LMS, Quill Rich Editor, Course Builder, and 3D Model Hotspot Pipeline.
- [ ] **Phase 2 (Immediate Hackathon Deliverable):** 
  - [ ] Implement AI Tutor floating drawer UI in course reader (`_ai_tutor_drawer.html`).
  - [ ] Add `ask_socratic_tutor` API route in `app/routes/student.py` backed by `app/services/ai_service.py`.
  - [ ] Add Grade 10–12 Life Sciences demonstration course with interactive 3D Heart and DNA models.
- [ ] **Phase 3 (Post-Hackathon):**
  - [ ] Build `/student/career-pathway` APS calculator and report card evaluation dashboard.
  - [ ] Integrate background learning telemetry tracking to calculate real-time `mastery_probability`.
  - [ ] Add automated SMS / WhatsApp nudges for at-risk learners via Africa's Talking / Twilio.
