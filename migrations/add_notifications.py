"""
Migration script to add notification system tables
Run this from the project root: python migrations/add_notifications.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def run_migration():
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting migration: Adding notification system tables...")
        
        try:
            # Create Notifications table
            print("  ➕ Creating notifications table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) NOT NULL,
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    link_url VARCHAR(255),
                    read BOOLEAN DEFAULT FALSE,
                    emailed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read_at TIMESTAMP,
                    priority VARCHAR(20) DEFAULT 'normal',
                    related_course_id INTEGER REFERENCES courses(id),
                    related_assignment_id INTEGER,
                    related_quiz_id INTEGER
                )
            """))
            
            # Create NotificationPreferences table
            print("  ➕ Creating notification_preferences table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) NOT NULL UNIQUE,
                    email_assignment_feedback BOOLEAN DEFAULT TRUE,
                    email_quiz_graded BOOLEAN DEFAULT TRUE,
                    email_course_announcement BOOLEAN DEFAULT TRUE,
                    email_course_completion BOOLEAN DEFAULT TRUE,
                    email_certificate_ready BOOLEAN DEFAULT TRUE,
                    email_new_course_content BOOLEAN DEFAULT TRUE,
                    email_assignment_due_soon BOOLEAN DEFAULT TRUE,
                    inapp_assignment_feedback BOOLEAN DEFAULT TRUE,
                    inapp_quiz_graded BOOLEAN DEFAULT TRUE,
                    inapp_course_announcement BOOLEAN DEFAULT TRUE,
                    inapp_course_completion BOOLEAN DEFAULT TRUE,
                    inapp_certificate_ready BOOLEAN DEFAULT TRUE,
                    inapp_new_course_content BOOLEAN DEFAULT TRUE,
                    weekly_digest BOOLEAN DEFAULT TRUE,
                    digest_day VARCHAR(10) DEFAULT 'Monday'
                )
            """))
            
            # Create Announcements table
            print("  ➕ Creating announcements table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    course_id INTEGER REFERENCES courses(id) NOT NULL,
                    teacher_id INTEGER REFERENCES users(id) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    send_email BOOLEAN DEFAULT TRUE,
                    pinned BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes for better performance
            print("  ➕ Creating indexes...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_announcements_course_id ON announcements(course_id);
            """))
            
            # Create default notification preferences for existing users
            print("  ➕ Creating default preferences for existing users...")
            db.session.execute(text("""
                INSERT INTO notification_preferences (user_id)
                SELECT id FROM users
                WHERE id NOT IN (SELECT user_id FROM notification_preferences)
            """))
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("\n🔔 Notification system is now enabled:")
            print("   - In-app notifications")
            print("   - Email notifications")
            print("   - User preferences")
            print("   - Course announcements")
            print("   - Weekly digest emails")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()
