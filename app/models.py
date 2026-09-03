import os
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

# ---------------------------------------------------------------------------
# Activity type system (Moodle-inspired Level 2)
# Each Section has one of these types. The type determines what the teacher
# fills in and how the student sees the content.
# ---------------------------------------------------------------------------
ACTIVITY_TYPES = {
    'lesson':     {'label': 'Lesson',      'icon': '📖', 'color': 'blue'},
    'video':      {'label': 'Video',       'icon': '🎥', 'color': 'purple'},
    'quiz':       {'label': 'Quiz',        'icon': '❓', 'color': 'amber'},
    'assignment': {'label': 'Assignment',  'icon': '📝', 'color': 'pink'},
    'resource':   {'label': 'Resource',    'icon': '📎', 'color': 'gray'},
    'url':        {'label': 'Link',        'icon': '🔗', 'color': 'green'},
}

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    bio = db.Column(db.Text, nullable=True)
    contact = db.Column(db.String(120), nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    id_number = db.Column(db.String(30), nullable=True)  # SA National ID or Passport Number for certificate accreditation
    
    # Teacher-specific fields
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    specialization = db.Column(db.String(200), nullable=True)
    
    # Activity tracking fields
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    login_count = db.Column(db.Integer, default=0)
    
    # Suspension/Ban fields
    is_suspended = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    suspension_reason = db.Column(db.Text, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    suspended_until = db.Column(db.DateTime, nullable=True)
    suspended_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Explicit __init__ to handle all fields
    def __init__(self, email, username, password, role, bio=None, contact=None, 
                 first_name=None, last_name=None, specialization=None, id_number=None):
        self.email = email
        self.username = username
        self.password = password  # Triggers @password.setter
        self.role = role
        self.bio = bio
        self.contact = contact
        self.first_name = first_name
        self.last_name = last_name
        self.specialization = specialization
        self.id_number = id_number
        self.created_at = datetime.utcnow()
        self.login_count = 0

    @property
    def full_name(self):
        """Return full name if present, else fallback to username or email prefix"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return self.username
        return self.email.split('@')[0]

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_account_active(self):
        """Check if account is active (not banned or suspended)"""
        if self.is_banned:
            return False
        if self.is_suspended:
            # Check if suspension has expired
            if self.suspended_until and datetime.utcnow() > self.suspended_until:
                # Auto-unsuspend
                self.is_suspended = False
                self.suspended_until = None
                db.session.commit()
                return True
            return False
        return True
    
    def get_suspension_status(self):
        """Get detailed suspension status"""
        if self.is_banned:
            return {'status': 'banned', 'reason': self.suspension_reason}
        if self.is_suspended:
            if self.suspended_until and datetime.utcnow() > self.suspended_until:
                # Auto-unsuspend
                self.is_suspended = False
                self.suspended_until = None
                db.session.commit()
                return {'status': 'active'}
            return {
                'status': 'suspended',
                'reason': self.suspension_reason,
                'until': self.suspended_until,
                'suspended_at': self.suspended_at
            }
        return {'status': 'active'}

    # Relationship to enrollments
    enrollments = db.relationship('Enrollment', back_populates='student', cascade='all, delete-orphan')

    # Relationship to courses (as teacher) - REMOVED conflicting relationship
    # Use Course.teacher relationship instead
    ratings = db.relationship('Rating', back_populates='user')

    def is_teacher_for_course(self, course_id):
        """Check if the user is the teacher or a co-teacher for a specific course."""
        if self.role != 'teacher':
            return False
        # Check if they are the primary owner/creator
        if any(course.id == course_id for course in self.taught_courses):
            return True
        # Check if they are in the co_teachers list of the course
        from app.models import Course
        course = Course.query.get(course_id)
        if course and self in course.co_teachers:
            return True
        return False

# Association table for additional assisting/co-teachers on a course
course_co_teachers = db.Table('course_co_teachers',
    db.Column('course_id', db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Added index
    title = db.Column(db.String(100), nullable=False, index=True)  # Added index for search
    description = db.Column(db.Text, nullable=False)
    youtube_url = db.Column(db.String(255))
    status = db.Column(db.String(20), default='draft', index=True)  # Added index for filtering
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # Added index for sorting
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_feedback = db.Column(db.Text)
    pdf_filename = db.Column(db.String(120))
    banner_image = db.Column(db.String(120))  # Thumbnail for preview
    intro_text = db.Column(db.Text, nullable=True)
    intro_video = db.Column(db.String(255))
    teacher_bio = db.Column(db.Text, nullable=True)
    teacher_contact = db.Column(db.String(120), nullable=True)
    resources = db.Column(db.Text, nullable=True)
    
    # New fields for enhanced course creation
    category = db.Column(db.String(50), nullable=True)  # e.g., 'programming', 'design', 'business'
    accreditation_name = db.Column(db.String(255), nullable=True)  # e.g. 'National Certificate: IT Systems Support'
    difficulty_level = db.Column(db.String(20), default='intermediate')  # 'beginner', 'intermediate', 'advanced'
    estimated_duration = db.Column(db.Integer, nullable=True)  # in hours
    language = db.Column(db.String(20), default='english')
    learning_objectives = db.Column(db.Text, nullable=True)  # JSON string of objectives
    prerequisites = db.Column(db.Text, nullable=True)  # JSON string of prerequisites
    tags = db.Column(db.String(255), nullable=True)  # comma-separated tags
    is_draft = db.Column(db.Boolean, default=True)  # for autosave functionality
    last_autosave = db.Column(db.DateTime, nullable=True)
    
    # Visibility & Seats controls
    visibility = db.Column(db.String(20), default='public', index=True)  # 'public', 'private'
    is_coming_soon = db.Column(db.Boolean, default=False, index=True)  # Waitlist / Pre-launch mode
    max_seats = db.Column(db.Integer, nullable=True)  # Optional student capacity cap
    
    # Custom & Co-Branded Certificate Design Fields
    certificate_theme = db.Column(db.String(30), default='gold')  # 'gold', 'navy', 'emerald', 'dark', 'burgundy'
    custom_certificate_title = db.Column(db.String(120), nullable=True)  # e.g. "Certificate of Completion"
    instructor_signature = db.Column(db.String(255), nullable=True)  # Lead Instructor signature image path or Cloudinary URL
    partner_name = db.Column(db.String(150), nullable=True)  # Skills provider / corporate partner name
    partner_logo = db.Column(db.String(255), nullable=True)  # Partner logo image path or Cloudinary URL
    partner_accreditation_number = db.Column(db.String(120), nullable=True)  # e.g. "QCTO Reg No: 07-QCTO/SDP..."
    partner_signatory_name = db.Column(db.String(120), nullable=True)  # Partner Director / Signatory name
    partner_signatory_title = db.Column(db.String(120), nullable=True)  # Partner Director / Signatory title
    partner_signatory_signature = db.Column(db.String(255), nullable=True)  # Partner signature image path
    
    teacher = db.relationship('User', backref='taught_courses')
    co_teachers = db.relationship('User', secondary=course_co_teachers, backref='assisted_courses')
    modules = db.relationship('Module', 
                             back_populates='course',
                             order_by='Module.order',
                             cascade='all, delete-orphan')
    sections = db.relationship('Section', 
                             back_populates='course',
                             order_by='Section.order',
                             cascade='all, delete-orphan')
    enrollments = db.relationship('Enrollment', back_populates='course', cascade='all, delete-orphan')
    ratings = db.relationship('Rating', back_populates='course', cascade='all, delete-orphan')

    @property
    def seats_remaining(self):
        if self.max_seats is None:
            return None
        enrolled_count = len(self.enrollments) if self.enrollments else 0
        return max(0, self.max_seats - enrolled_count)

class Module(db.Model):
    __tablename__ = 'modules'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    course = db.relationship('Course', back_populates='modules')
    sections = db.relationship('Section', 
                             back_populates='module',
                             order_by='Section.order',
                             cascade='all, delete-orphan')

class Section(db.Model):
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=True)  # New field for hierarchical structure
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    section_type = db.Column(db.String(20), default='text')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False)
    duration = db.Column(db.Integer, default=0)
    media_type = db.Column(db.String(20), default='text')
    media_file = db.Column(db.String(120))
    video_url = db.Column(db.String(255), nullable=True)
    
    quizzes = db.relationship('Quiz', back_populates='section', cascade='all, delete-orphan', order_by='desc(Quiz.id)')
    course = db.relationship('Course', back_populates='sections')
    module = db.relationship('Module', back_populates='sections')  # New relationship
    enrollment_sections = db.relationship('EnrollmentSection', back_populates='section')
    assignments = db.relationship('Assignment', back_populates='section', cascade='all, delete-orphan', order_by='desc(Assignment.id)')

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'contacted', 'enrolled', 'rejected'
    employment_status = db.Column(db.String(50), nullable=True)
    
    # Enterprise fields
    lead_type = db.Column(db.String(20), default='individual')  # 'individual' or 'enterprise'
    organization = db.Column(db.String(150), nullable=True)
    estimated_learners = db.Column(db.Integer, nullable=True)
    inquiry_type = db.Column(db.String(100), nullable=True)  # 'licensing', 'whitelabel', 'custom', 'other'
    
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    course = db.relationship('Course', backref='leads')

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Added index
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), index=True)  # Added index
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # Added index
    completed = db.Column(db.Boolean, default=False, index=True)  # Added index for filtering
    completed_at = db.Column(db.DateTime, nullable=True)  # When course was completed
    certificate_path = db.Column(db.String(255))  # Added for certificate storage
    is_blocked = db.Column(db.Boolean, default=False, index=True)  # Per-course block by admin
    block_reason = db.Column(db.String(500), nullable=True)  # Reason for blocking
    last_nudge_sent_at = db.Column(db.DateTime, nullable=True)  # Timestamp of last inactivity nudge email
    
    student = db.relationship('User', back_populates='enrollments')
    course = db.relationship('Course', back_populates='enrollments')
    sections = db.relationship('EnrollmentSection', back_populates='enrollment', cascade='all, delete-orphan')

class EnrollmentSection(db.Model):
    __tablename__ = 'enrollment_sections'
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), index=True)  # Added index
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), index=True)  # Added index
    completed = db.Column(db.Boolean, default=False, index=True)  # Added index
    completed_at = db.Column(db.DateTime)
    
    # Analytics tracking fields
    time_spent = db.Column(db.Integer, default=0)  # Total time in seconds
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)  # Last time viewed
    view_count = db.Column(db.Integer, default=0)  # Number of times viewed
    started_at = db.Column(db.DateTime, default=datetime.utcnow)  # First time accessed
    
    enrollment = db.relationship('Enrollment', back_populates='sections')
    section = db.relationship('Section', back_populates='enrollment_sections')

class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    
    # Code assignment fields
    is_coding_assignment = db.Column(db.Boolean, default=False)
    programming_language = db.Column(db.String(20), nullable=True)  # 'python', 'javascript', 'java', etc.
    starter_code = db.Column(db.Text, nullable=True)  # Template code for students
    allow_file_upload = db.Column(db.Boolean, default=True)
    enable_code_execution = db.Column(db.Boolean, default=False)  # Allow students to run code
    max_attempts = db.Column(db.Integer, default=3)  # Max submission attempts allowed (default 3)
    
    section = db.relationship('Section', back_populates='assignments')
    submissions = db.relationship('AssignmentSubmission', back_populates='assignment', cascade='all, delete-orphan')

class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)  # Track attempt number (1, 2, 3)
    submission_text = db.Column(db.Text, nullable=True, default='')
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reviewed = db.Column(db.Boolean, default=False)
    feedback = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.Text, nullable=True)
    
    # Code submission fields
    code_submission = db.Column(db.Text, nullable=True)  # Student's code
    submission_type = db.Column(db.String(20), default='text')  # 'text', 'code', 'file'
    programming_language = db.Column(db.String(20), nullable=True)
    execution_output = db.Column(db.Text, nullable=True)  # Output when student ran code
    execution_error = db.Column(db.Text, nullable=True)  # Any errors from execution
    grade = db.Column(db.Float, nullable=True)  # Numerical grade
    
    assignment = db.relationship('Assignment', back_populates='submissions')
    student = db.relationship('User')
    
    def to_json(self):
        """Serialize submission for JavaScript consumption"""
        import json
        return json.dumps({
            'id': self.id,
            'submission_text': self.submission_text or '',
            'submission_type': self.submission_type or 'text',
            'code_submission': self.code_submission or '',
            'programming_language': self.programming_language or '',
            'file_path': self.file_path or '',
            'feedback': self.feedback or '',
            'grade': self.grade,
            'reviewed': self.reviewed
        })

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    time_limit = db.Column(db.Integer, nullable=True)  # Time limit in minutes (null = unlimited)
    passing_score = db.Column(db.Float, default=60.0)  # Minimum score to pass (percentage)
    max_attempts = db.Column(db.Integer, nullable=True)  # Max attempts allowed (null = unlimited)
    randomize_questions = db.Column(db.Boolean, default=False)  # Randomize question order
    show_correct_answers = db.Column(db.Boolean, default=True)  # Show correct answers after submission
    section = db.relationship('Section', back_populates='quizzes')
    questions = db.relationship('QuizQuestion', back_populates='quiz', cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', back_populates='quiz', cascade='all, delete-orphan')

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, nullable=False)
    option_b = db.Column(db.Text, nullable=False)
    option_c = db.Column(db.Text, nullable=True)
    option_d = db.Column(db.Text, nullable=True)
    correct_answer = db.Column(db.String(10), nullable=False)
    quiz = db.relationship('Quiz', back_populates='questions')
    answers = db.relationship('QuizAnswer', back_populates='question', cascade='all, delete-orphan')

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    attempted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    time_taken = db.Column(db.Integer, nullable=True)  # Time taken in seconds
    completed_at = db.Column(db.DateTime, nullable=True)  # When quiz was completed
    quiz = db.relationship('Quiz', back_populates='attempts')
    student = db.relationship('User')
    answers = db.relationship('QuizAnswer', back_populates='attempt', cascade='all, delete-orphan')
    
class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    rating = db.Column(db.Float)
    comment = db.Column(db.Text)
    rated_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='ratings')
    course = db.relationship('Course', back_populates='ratings')

class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False)
    attempt = db.relationship('QuizAttempt', back_populates='answers')
    question = db.relationship('QuizQuestion', back_populates='answers')

# ===== VIDEO FEATURES =====

class VideoWatchProgress(db.Model):
    """Track how much of a video each student has watched"""
    __tablename__ = 'video_watch_progress'
    id = db.Column(db.Integer, primary_key=True)
    enrollment_section_id = db.Column(db.Integer, db.ForeignKey('enrollment_sections.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Video progress tracking
    video_current_time = db.Column(db.Float, default=0.0)  # Current playback position in seconds (renamed from current_time to avoid PostgreSQL keyword)
    duration = db.Column(db.Float, default=0.0)  # Total video duration
    watch_percentage = db.Column(db.Float, default=0.0)  # Percentage watched
    completed = db.Column(db.Boolean, default=False)  # Watched >90%
    
    # Engagement metrics
    total_watch_time = db.Column(db.Integer, default=0)  # Actual time spent watching (seconds)
    play_count = db.Column(db.Integer, default=0)  # Number of times played
    last_watched = db.Column(db.DateTime, default=datetime.utcnow)
    playback_speed = db.Column(db.Float, default=1.0)  # Last used playback speed
    
    # Relationships
    enrollment_section = db.relationship('EnrollmentSection', backref='video_progress')
    section = db.relationship('Section', backref='video_watches')
    student = db.relationship('User', backref='video_watches')

class VideoInteractiveQuestion(db.Model):
    """Questions that appear at specific timestamps in videos"""
    __tablename__ = 'video_interactive_questions'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    
    # Question details
    question_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.Float, nullable=False)  # When to pause video (in seconds)
    
    # Multiple choice options
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=True)
    option_d = db.Column(db.String(255), nullable=True)
    correct_answer = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', or 'D'
    
    # Settings
    pause_video = db.Column(db.Boolean, default=True)  # Whether to pause video
    required = db.Column(db.Boolean, default=False)  # Must answer to continue
    explanation = db.Column(db.Text, nullable=True)  # Shown after answering
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer, default=0)
    
    # Relationships
    section = db.relationship('Section', backref='interactive_questions')
    responses = db.relationship('VideoQuestionResponse', back_populates='question', cascade='all, delete-orphan')

class VideoQuestionResponse(db.Model):
    """Student responses to interactive video questions"""
    __tablename__ = 'video_question_responses'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('video_interactive_questions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Response details
    selected_answer = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', or 'D'
    is_correct = db.Column(db.Boolean, nullable=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_taken = db.Column(db.Integer, default=0)  # Seconds to answer
    
    # Relationships
    question = db.relationship('VideoInteractiveQuestion', back_populates='responses')
    student = db.relationship('User', backref='video_question_responses')

class VideoSubtitle(db.Model):
    """Subtitle/caption files for videos"""
    __tablename__ = 'video_subtitles'
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=False)
    
    # Subtitle details
    language = db.Column(db.String(10), nullable=False)  # 'en', 'es', 'fr', etc.
    language_name = db.Column(db.String(50), nullable=False)  # 'English', 'Spanish', etc.
    subtitle_file = db.Column(db.String(255), nullable=False)  # Path to .vtt or .srt file
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    section = db.relationship('Section', backref='subtitles')

# ===== NOTIFICATION SYSTEM =====

class Notification(db.Model):
    """In-app notifications for users"""
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Notification content
    notification_type = db.Column(db.String(50), nullable=False)  # 'assignment_feedback', 'quiz_graded', 'announcement', etc.
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Optional link to relevant page
    link_url = db.Column(db.String(255), nullable=True)
    
    # Metadata
    read = db.Column(db.Boolean, default=False)
    emailed = db.Column(db.Boolean, default=False)  # Track if email was sent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Priority level
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high', 'urgent'
    
    # Related entity IDs (optional, for advanced filtering)
    related_course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    related_assignment_id = db.Column(db.Integer, nullable=True)
    related_quiz_id = db.Column(db.Integer, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notifications', cascade='all, delete-orphan'))
    related_course = db.relationship('Course', backref='notifications')

class NotificationPreference(db.Model):
    """User preferences for notifications"""
    __tablename__ = 'notification_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Email notification preferences
    email_assignment_feedback = db.Column(db.Boolean, default=True)
    email_quiz_graded = db.Column(db.Boolean, default=True)
    email_course_announcement = db.Column(db.Boolean, default=True)
    email_course_completion = db.Column(db.Boolean, default=True)
    email_certificate_ready = db.Column(db.Boolean, default=True)
    email_new_course_content = db.Column(db.Boolean, default=True)
    email_assignment_due_soon = db.Column(db.Boolean, default=True)
    
    # In-app notification preferences
    inapp_assignment_feedback = db.Column(db.Boolean, default=True)
    inapp_quiz_graded = db.Column(db.Boolean, default=True)
    inapp_course_announcement = db.Column(db.Boolean, default=True)
    inapp_course_completion = db.Column(db.Boolean, default=True)
    inapp_certificate_ready = db.Column(db.Boolean, default=True)
    inapp_new_course_content = db.Column(db.Boolean, default=True)
    
    # Digest email preferences
    weekly_digest = db.Column(db.Boolean, default=True)
    digest_day = db.Column(db.String(10), default='Monday')  # Day of week for digest
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notification_preferences', uselist=False, cascade='all, delete-orphan'))

class Announcement(db.Model):
    """Course announcements from teachers"""
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Announcement details
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Settings
    send_email = db.Column(db.Boolean, default=True)  # Send email to all enrolled students
    pinned = db.Column(db.Boolean, default=False)  # Pin to top of announcements
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course = db.relationship('Course', backref=db.backref('announcements', cascade='all, delete-orphan'))
    teacher = db.relationship('User', backref='announcements_created')


class LiveSession(db.Model):
    """Live Video Classroom Sessions created by teachers"""
    __tablename__ = 'live_sessions'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    
    room_name = db.Column(db.String(120), unique=True, nullable=False)  # Jitsi meeting room identifier
    custom_meeting_url = db.Column(db.String(500), nullable=True)  # Optional Zoom/Meet fallback link
    
    status = db.Column(db.String(20), default='scheduled')  # 'scheduled', 'live', 'ended', 'cancelled'
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    recording_url = db.Column(db.String(500), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref=db.backref('live_sessions', lazy=True, cascade='all, delete-orphan'))
    creator = db.relationship('User', backref='created_live_sessions')


class LiveAttendance(db.Model):
    """Student attendance tracking for live sessions"""
    __tablename__ = 'live_attendances'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('live_sessions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_ping = db.Column(db.DateTime, default=datetime.utcnow)
    
    session = db.relationship('LiveSession', backref=db.backref('attendances', lazy=True, cascade='all, delete-orphan'))
    student = db.relationship('User', backref='live_attendances')


class LiveQuestion(db.Model):
    """Pre-meeting student questions submitted for live sessions"""
    __tablename__ = 'live_questions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('live_sessions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    question_text = db.Column(db.Text, nullable=False)
    is_answered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('LiveSession', backref=db.backref('questions', lazy=True, cascade='all, delete-orphan'))
    student = db.relationship('User', backref='live_questions')


# ==============================================================================
# COURSE DISCUSSION FORUM & Q&A COMMUNITY MODELS
# ==============================================================================

class ForumThread(db.Model):
    """Discussion thread or question in a course"""
    __tablename__ = 'forum_threads'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=True)  # Null if general course question
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_resolved = db.Column(db.Boolean, default=False)
    views_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref=db.backref('forum_threads', lazy=True, cascade='all, delete-orphan'))
    section = db.relationship('Section', backref=db.backref('forum_threads', lazy=True))
    author = db.relationship('User', backref='forum_threads')
    replies = db.relationship('ForumReply', backref='thread', lazy='dynamic', cascade='all, delete-orphan', order_by='ForumReply.created_at.asc()')
    upvotes = db.relationship('ForumUpvote', backref='thread', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def upvotes_count(self):
        return self.upvotes.filter_by(reply_id=None).count()

    @property
    def replies_count(self):
        return self.replies.count()

    @property
    def has_instructor_reply(self):
        return self.replies.filter_by(is_instructor_reply=True).first() is not None

    @property
    def accepted_reply(self):
        return self.replies.filter_by(is_accepted_solution=True).first()

    def has_upvoted(self, user_id):
        if not user_id:
            return False
        return self.upvotes.filter_by(user_id=user_id, reply_id=None).first() is not None


class ForumReply(db.Model):
    """Reply or comment on a forum thread"""
    __tablename__ = 'forum_replies'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('forum_threads.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_reply_id = db.Column(db.Integer, db.ForeignKey('forum_replies.id'), nullable=True)

    content = db.Column(db.Text, nullable=False)
    is_instructor_reply = db.Column(db.Boolean, default=False)
    is_accepted_solution = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref='forum_replies')
    parent = db.relationship('ForumReply', remote_side=[id], backref=db.backref('children', lazy=True, cascade='all, delete-orphan'))
    upvotes = db.relationship('ForumUpvote', backref='reply', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def upvotes_count(self):
        return self.upvotes.filter_by(thread_id=None).count()

    def has_upvoted(self, user_id):
        if not user_id:
            return False
        return self.upvotes.filter_by(user_id=user_id, thread_id=None).first() is not None


class ForumUpvote(db.Model):
    """User upvotes for threads and replies"""
    __tablename__ = 'forum_upvotes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('forum_threads.id'), nullable=True)
    reply_id = db.Column(db.Integer, db.ForeignKey('forum_replies.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='forum_upvotes')