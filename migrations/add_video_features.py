"""
Migration script to add video feature tables
Run this from the project root: python migrations/add_video_features.py
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
        print("🔄 Starting migration: Adding video feature tables...")
        
        try:
            # Create VideoWatchProgress table
            print("  ➕ Creating video_watch_progress table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS video_watch_progress (
                    id SERIAL PRIMARY KEY,
                    enrollment_section_id INTEGER REFERENCES enrollment_sections(id),
                    section_id INTEGER REFERENCES sections(id),
                    student_id INTEGER REFERENCES users(id),
                    video_current_time FLOAT DEFAULT 0.0,
                    duration FLOAT DEFAULT 0.0,
                    watch_percentage FLOAT DEFAULT 0.0,
                    completed BOOLEAN DEFAULT FALSE,
                    total_watch_time INTEGER DEFAULT 0,
                    play_count INTEGER DEFAULT 0,
                    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    playback_speed FLOAT DEFAULT 1.0
                )
            """))
            
            # Create VideoInteractiveQuestion table
            print("  ➕ Creating video_interactive_questions table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS video_interactive_questions (
                    id SERIAL PRIMARY KEY,
                    section_id INTEGER REFERENCES sections(id),
                    question_text TEXT NOT NULL,
                    timestamp FLOAT NOT NULL,
                    option_a VARCHAR(255) NOT NULL,
                    option_b VARCHAR(255) NOT NULL,
                    option_c VARCHAR(255),
                    option_d VARCHAR(255),
                    correct_answer VARCHAR(1) NOT NULL,
                    pause_video BOOLEAN DEFAULT TRUE,
                    required BOOLEAN DEFAULT FALSE,
                    explanation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    "order" INTEGER DEFAULT 0
                )
            """))
            
            # Create VideoQuestionResponse table
            print("  ➕ Creating video_question_responses table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS video_question_responses (
                    id SERIAL PRIMARY KEY,
                    question_id INTEGER REFERENCES video_interactive_questions(id),
                    student_id INTEGER REFERENCES users(id),
                    selected_answer VARCHAR(1) NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    time_taken INTEGER DEFAULT 0
                )
            """))
            
            # Create VideoSubtitle table
            print("  ➕ Creating video_subtitles table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS video_subtitles (
                    id SERIAL PRIMARY KEY,
                    section_id INTEGER REFERENCES sections(id),
                    language VARCHAR(10) NOT NULL,
                    language_name VARCHAR(50) NOT NULL,
                    subtitle_file VARCHAR(255) NOT NULL,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("\n🎬 Video features are now enabled:")
            print("   - Watch time tracking")
            print("   - Interactive video quizzes")
            print("   - Subtitle/caption support")
            print("   - Playback speed control")
            print("   - Video analytics")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()
