import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class AIService:
    """
    Pace Academy AI Service powered by Google Gemini API.
    Handles Course Curriculum Design, Quill-Formatted Lesson Generation, 
    Quiz Formulation, and Style-Cloning from reference templates.
    """
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-3.5-flash"
    ALLOWED_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-flash-latest",
        "gemini-3.1-flash-lite",
        "gemini-pro-latest"
    ]

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("GEMINI_API_KEY")

    @classmethod
    def _normalize_model(cls, model: Optional[str]) -> str:
        if not model:
            return cls.DEFAULT_MODEL
        model_clean = model.strip().lower()
        if model_clean in cls.ALLOWED_MODELS:
            return model_clean
        if "pro" in model_clean:
            return "gemini-pro-latest"
        return cls.DEFAULT_MODEL

    @classmethod
    def _call_gemini(cls, prompt: str, system_instruction: Optional[str] = None, model: Optional[str] = None, response_json: bool = False) -> str:
        """Call Google Gemini REST API with fallback and error handling."""
        api_key = cls.get_api_key()
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please add it to your .env file or Render dashboard.")
        
        target_model = cls._normalize_model(model)
        models_to_try = [target_model]
        if target_model != cls.DEFAULT_MODEL:
            models_to_try.append(cls.DEFAULT_MODEL)
        if "gemini-flash-latest" not in models_to_try:
            models_to_try.append("gemini-flash-latest")

        last_error = None
        for current_model in models_to_try:
            url = f"{cls.BASE_URL}/{current_model}:generateContent?key={api_key}"

            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "topP": 0.95,
                    "topK": 40,
                    "maxOutputTokens": 8192,
                }
            }

            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            if response_json:
                payload["generationConfig"]["responseMimeType"] = "application/json"

            headers = {"Content-Type": "application/json"}
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    content_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return content_text.strip()
                else:
                    logger.warning(f"Gemini API returned {response.status_code} for {current_model}: {response.text}")
                    last_error = f"Gemini API ({response.status_code}): {response.text}"
            except Exception as ex:
                logger.warning(f"Request exception for model {current_model}: {ex}")
                last_error = str(ex)

        raise RuntimeError(f"Google Gemini generation failed: {last_error}")

    @classmethod
    def generate_course_blueprint(
        cls,
        title: str,
        topic: str,
        level: str = "Beginner",
        duration_weeks: int = 4,
        accreditation: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        reference_template: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a multi-module syllabus outline with lesson topics and objectives.
        """
        system_prompt = (
            "You are the Pace Academy Master Instructional Designer & Curriculum Architect. "
            "You design world-class, engaging, NQF/SETA-aligned vocational and technical courses. "
            "Always output strictly valid JSON matching the requested schema."
        )

        user_prompt = f"""
Create a structured course blueprint for:
- Course Title: {title}
- Main Topic / Subject: {topic}
- Target Audience Level: {level}
- Target Duration: {duration_weeks} Weeks
- Accreditation / Standard (if any): {accreditation or 'Standard Practical Skills'}
- Specific Teacher Instructions: {custom_instructions or 'Create balanced theoretical and practical modules with hands-on coding/application.'}

{f'REFERENCE STYLE / STRUCTURE EXAMPLE TO EMULATE:\n{reference_template}' if reference_template else ''}

Return a JSON object with this exact structure:
{{
  "title": "{title}",
  "short_description": "2-3 sentences explaining the value of the course",
  "category": "programming | business | design | marketing | accounting | technical",
  "difficulty_level": "{level.lower()}",
  "estimated_duration": {duration_weeks * 5},
  "learning_objectives": ["Objective 1", "Objective 2", "Objective 3", "Objective 4"],
  "prerequisites": ["Prerequisite 1", "Prerequisite 2"],
  "tags": "comma,separated,tags",
  "modules": [
    {{
      "module_number": 1,
      "title": "Module Title",
      "description": "Short module overview",
      "lessons": [
        {{
          "title": "Lesson Title",
          "summary": "Brief summary of what will be taught",
          "estimated_minutes": 15
        }}
      ]
    }}
  ]
}}
"""
        raw_json = cls._call_gemini(user_prompt, system_instruction=system_prompt, model=model, response_json=True)
        return json.loads(raw_json)

    @classmethod
    def generate_lesson_html(
        cls,
        course_title: str,
        module_title: str,
        lesson_title: str,
        custom_instructions: Optional[str] = None,
        reference_template: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Generates rich, semantic HTML lesson content specifically designed for Pace's Quill Editor.
        Includes headings, callout boxes, bullet points, and code syntax blocks.
        """
        system_prompt = (
            "You are an expert technical educator for Pace Academy. "
            "You write crystal-clear, engaging, interactive lesson materials. "
            "IMPORTANT: Output ONLY clean, valid HTML suitable for direct insertion into Quill Rich Text Editor. "
            "Do NOT wrap in <html>, <body>, or markdown ```html code blocks. "
            "Use only <h2>, <h3>, <p>, <strong>, <em>, <ul>, <ol>, <li>, <blockquote> (for pro-tips and warnings), "
            "and <pre class=\"ql-syntax\" spellcheck=\"false\"><code>...</code></pre> for code snippets."
        )

        user_prompt = f"""
Generate a complete, comprehensive lesson for:
- Course: {course_title}
- Module: {module_title}
- Lesson Title: {lesson_title}
- Instructions: {custom_instructions or 'Provide clear explanation, practical real-world analogy, step-by-step code/examples, common pitfalls, and key takeaways.'}

{f'REFERENCE LESSON STYLE TO CLONE (Follow this exact layout and tone):\n{reference_template}' if reference_template else ''}

Required Sections in HTML:
1. <h2>Introduction & Context</h2>
2. <blockquote><strong>💡 Key Principle:</strong> ...</blockquote>
3. <h3>Core Concepts & Step-by-Step Breakdown</h3>
4. <h3>Hands-on Code / Practical Example</h3> (<pre class="ql-syntax" spellcheck="false"><code>...</code></pre>)
5. <blockquote><strong>⚠️ Common Pitfall:</strong> ...</blockquote>
6. <h3>Summary Checklist</h3> (<ul><li>...</li></ul>)
"""
        raw_html = cls._call_gemini(user_prompt, system_instruction=system_prompt, model=model, response_json=False)
        
        # Clean any accidental markdown wraps
        if raw_html.startswith("```html"):
            raw_html = raw_html[7:]
        if raw_html.startswith("```"):
            raw_html = raw_html[3:]
        if raw_html.endswith("```"):
            raw_html = raw_html[:-3]
            
        return raw_html.strip()

    @classmethod
    def generate_quiz_for_lesson(
        cls,
        lesson_title: str,
        lesson_content: str,
        num_questions: int = 5,
        passing_score: float = 60.0,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a multiple choice quiz based on lesson content.
        Matches Pace Academy Quiz and QuizQuestion database schema.
        """
        system_prompt = (
            "You are an educational assessment expert for Pace Academy. "
            "Generate high-quality multiple choice quizzes that test practical comprehension. "
            "Rules: Exactly 4 options (A, B, C, D) per question, exactly 1 unambiguously correct option, "
            "clear pedagogical explanation, and no trick questions. "
            "Always return strictly valid JSON."
        )

        user_prompt = f"""
Generate an assessment quiz for:
- Lesson: {lesson_title}
- Number of Questions: {num_questions}
- Passing Score: {passing_score}%
- Lesson Material:
{lesson_content[:4000]}

Return JSON with this exact schema:
{{
  "title": "{lesson_title} - Knowledge Check",
  "passing_score": {passing_score},
  "time_limit": 10,
  "questions": [
    {{
      "question_text": "Question prompt here?",
      "option_a": "First option",
      "option_b": "Second option",
      "option_c": "Third option",
      "option_d": "Fourth option",
      "correct_answer": "option_a",
      "explanation": "Why this answer is correct..."
    }}
  ]
}}
"""
        raw_json = cls._call_gemini(user_prompt, system_instruction=system_prompt, model=model, response_json=True)
        return json.loads(raw_json)

    @classmethod
    def generate_complete_course_bundle(
        cls,
        title: str,
        topic: str,
        level: str = "Beginner",
        duration_weeks: int = 4,
        accreditation: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        reference_template: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates a complete turn-key course package with all modules, full Quill lesson contents,
        and knowledge-check quizzes ready for direct database insertion.
        """
        # Step 1: Blueprint
        blueprint = cls.generate_course_blueprint(
            title=title,
            topic=topic,
            level=level,
            duration_weeks=duration_weeks,
            accreditation=accreditation,
            custom_instructions=custom_instructions,
            reference_template=reference_template,
            model=model
        )

        # Step 2: Populate detailed lesson content and quizzes for each module
        for module in blueprint.get("modules", []):
            module_title = module.get("title", "Module")
            for lesson in module.get("lessons", []):
                lesson_title = lesson.get("title", "Lesson")
                
                # Generate rich Quill HTML for the lesson
                lesson_html = cls.generate_lesson_html(
                    course_title=title,
                    module_title=module_title,
                    lesson_title=lesson_title,
                    custom_instructions=custom_instructions,
                    reference_template=reference_template,
                    model=model
                )
                lesson["content_html"] = lesson_html
                
                # Generate quiz for the lesson
                quiz_data = cls.generate_quiz_for_lesson(
                    lesson_title=lesson_title,
                    lesson_content=lesson_html,
                    num_questions=3,
                    passing_score=70.0,
                    model=model
                )
                lesson["quiz"] = quiz_data

        return blueprint
