from app import create_app, db
from app.models import (
    User, Course, Module, Section, Assignment, Quiz, QuizQuestion, QuizAttempt, QuizAnswer,
    Enrollment, EnrollmentSection, Rating, AssignmentSubmission, Lead, 
    VideoWatchProgress, VideoInteractiveQuestion, VideoQuestionResponse, VideoSubtitle,
    Notification, NotificationPreference, Announcement
)

app = create_app()

with app.app_context():
    # 1. Delete deeply nested dependencies
    VideoQuestionResponse.query.delete()
    VideoInteractiveQuestion.query.delete()
    VideoWatchProgress.query.delete()
    VideoSubtitle.query.delete()
    
    Notification.query.delete()
    Announcement.query.delete()
    Lead.query.delete()
    
    QuizAnswer.query.delete()
    QuizAttempt.query.delete()
    QuizQuestion.query.delete()
    
    AssignmentSubmission.query.delete()
    
    EnrollmentSection.query.delete()
    Enrollment.query.delete()
    Rating.query.delete()
    
    # 2. Delete course structural elements
    Assignment.query.delete()
    Quiz.query.delete()
    Section.query.delete()
    Module.query.delete()
    Course.query.delete()
    
    # 3. Delete non-admin users and their preferences
    non_admins = User.query.filter(User.role != 'admin').all()
    for user in non_admins:
        NotificationPreference.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        
    db.session.commit()
    print("Database cleaned successfully. Only admin users remain. All courses and progress deleted.")
