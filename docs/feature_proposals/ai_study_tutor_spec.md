# 🤖 Pace AI In-Course Student Tutor — Feature Specification & Roadmap

## 1. Overview & Objective
An integrated, context-aware AI Study Companion embedded directly inside the Pace Academy **Course Reader** (`/student/course/<id>`). When a learner gets stuck on a complex concept, formula, code snippet, or reading passage, they can open the AI Tutor to receive instant, patient explanations grounded in the exact lesson material.

---

## 2. UI / UX Design Blueprint

### A. Floating Trigger Button
* **Location**: Bottom-right corner of the course reader canvas (or pinned in the reader top action bar).
* **Appearance**: Glassmorphic indigo badge with a pulsing sparkle icon: `✨ AI Tutor`.
* **Tooltip**: *"Stuck on this lesson? Ask your AI Tutor"*.

### B. Slide-Out Side Drawer (Non-Intrusive)
* **Trigger**: Clicking the floating button slides open a 400px wide sidebar from the right.
* **Layout**:
  * **Header**: "✨ Pace AI Tutor", active lesson context badge, and close button.
  * **Chat Thread Area**: Smooth scrollable conversation stream with rich markdown syntax, bold keywords, and code highlighting.
  * **Quick-Action Prompt Pills** (1-Click instant assistance):
    1. 💡 *Explain this concept simply (with analogies)*
    2. 📝 *Summarize key takeaways in 3 bullet points*
    3. 💻 *Step-by-step code / formula walkthrough*
    4. 🎯 *Give me a quick practice check before my quiz*
  * **Input Footer**: Text input field with send button + character counter.

---

## 3. Backend & Prompt Architecture (`app/services/ai_service.py`)

### Endpoint
`POST /student/course/<course_id>/section/<section_id>/ai-tutor`

### Payload
```json
{
  "question": "What is the difference between RAM and ROM in this chapter?",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

### Context Injection (System Prompt)
```python
SYSTEM_PROMPT = """
You are "Pace AI Tutor", an encouraging, patient, and expert vocational tutor for Pace Academy in South Africa.
You are assisting a student currently studying the lesson: "{lesson_title}" in module "{module_title}".

CURRENT LESSON MATERIAL (Ground Truth):
\"\"\"{lesson_content_text}\"\"\"

STRICT GUARDRAILS:
1. Grounding: Answer strictly using the context and principles in this course material. Do not hallucinate outside facts.
2. Tone: Friendly, encouraging, clear, and professional. Use South African workplace context where helpful.
3. Anti-Cheating & Socratic Method: If the student asks for direct answers to a quiz, test, or graded assignment, REFUSE politely. Instead, explain the underlying concept and guide them with a hint or analogy.
4. Escalation: If the student is still confused after 2 exchanges, encourage them to post their question to the Course Q&A Discussion Forum for instructor review.
"""
```

---

## 4. Academic Integrity & Safety Guardrails
1. **Zero Direct Answers on Quizzes**: Socratic questioning forces the student to demonstrate understanding.
2. **Context Window Capping**: Lessons are stripped of HTML tags and trimmed to ~8,000 characters to ensure ultra-fast responses and minimal token cost.
3. **Escalation Button**: If AI cannot resolve the doubt, a button appears: `💬 Post to Course Q&A Forum`.

---

## 5. Implementation Checklist (Ready to Build)
- [ ] Add `ask_lesson_tutor` method in [`app/services/ai_service.py`](file:///Users/dam1mac89/Desktop/pace/app/services/ai_service.py).
- [ ] Add `@student_bp.route('/course/<int:course_id>/tutor', methods=['POST'])` in [`app/routes/student.py`](file:///Users/dam1mac89/Desktop/pace/app/routes/student.py).
- [ ] Create partial `app/templates/student/_ai_tutor_drawer.html`.
- [ ] Include partial and floating button in [`app/templates/student/course_detail.html`](file:///Users/dam1mac89/Desktop/pace/app/templates/student/course_detail.html).
- [ ] Add JavaScript streaming/fetch handler with quick prompt chips.
