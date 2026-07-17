"""
Migration script to add quiz time limits and enhanced settings
Run this from the project root: python3 migrations/add_quiz_time_limits.py
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
        print("🔄 Starting migration: Adding quiz time limits and settings...")
        
        try:
            # Check if columns already exist
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='quizzes' AND column_name='time_limit'
            """))
            
            if result.fetchone():
                print("  ⚠️  Migration already applied! Columns already exist.")
                return
            
            # Add new columns to quizzes table
            print("  ➕ Adding time_limit column to quizzes...")
            db.session.execute(text("""
                ALTER TABLE quizzes 
                ADD COLUMN IF NOT EXISTS time_limit INTEGER
            """))
            
            print("  ➕ Adding passing_score column to quizzes...")
            db.session.execute(text("""
                ALTER TABLE quizzes 
                ADD COLUMN IF NOT EXISTS passing_score FLOAT DEFAULT 60.0
            """))
            
            print("  ➕ Adding max_attempts column to quizzes...")
            db.session.execute(text("""
                ALTER TABLE quizzes 
                ADD COLUMN IF NOT EXISTS max_attempts INTEGER
            """))
            
            print("  ➕ Adding randomize_questions column to quizzes...")
            db.session.execute(text("""
                ALTER TABLE quizzes 
                ADD COLUMN IF NOT EXISTS randomize_questions BOOLEAN DEFAULT FALSE
            """))
            
            print("  ➕ Adding show_correct_answers column to quizzes...")
            db.session.execute(text("""
                ALTER TABLE quizzes 
                ADD COLUMN IF NOT EXISTS show_correct_answers BOOLEAN DEFAULT TRUE
            """))
            
            # Add new columns to quiz_attempts table
            print("  ➕ Adding time_taken column to quiz_attempts...")
            db.session.execute(text("""
                ALTER TABLE quiz_attempts 
                ADD COLUMN IF NOT EXISTS time_taken INTEGER
            """))
            
            print("  ➕ Adding completed_at column to quiz_attempts...")
            db.session.execute(text("""
                ALTER TABLE quiz_attempts 
                ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP
            """))
            
            # Update existing quizzes with default values
            print("  🔄 Updating existing quizzes with default values...")
            db.session.execute(text("""
                UPDATE quizzes 
                SET passing_score = 60.0 
                WHERE passing_score IS NULL
            """))
            
            db.session.execute(text("""
                UPDATE quizzes 
                SET randomize_questions = FALSE 
                WHERE randomize_questions IS NULL
            """))
            
            db.session.execute(text("""
                UPDATE quizzes 
                SET show_correct_answers = TRUE 
                WHERE show_correct_answers IS NULL
            """))
            
            # Create indexes for better performance
            print("  📊 Creating indexes for better query performance...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quiz_time_limit 
                ON quizzes(time_limit)
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student 
                ON quiz_attempts(student_id, quiz_id)
            """))
            
            # Commit all changes
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            print("\n📋 Summary of changes:")
            print("   - Added 5 new columns to 'quizzes' table:")
            print("     • time_limit (INTEGER) - Quiz duration in minutes")
            print("     • passing_score (FLOAT) - Minimum score to pass (default 60%)")
            print("     • max_attempts (INTEGER) - Maximum quiz attempts allowed")
            print("     • randomize_questions (BOOLEAN) - Randomize question order")
            print("     • show_correct_answers (BOOLEAN) - Show answers after submission")
            print("   - Added 2 new columns to 'quiz_attempts' table:")
            print("     • time_taken (INTEGER) - Time student took in seconds")
            print("     • completed_at (TIMESTAMP) - When quiz was completed")
            print("   - Created 2 indexes for query optimization")
            print("   - Updated existing quizzes with default values")
            
            # Show current quiz count
            result = db.session.execute(text("SELECT COUNT(*) FROM quizzes"))
            quiz_count = result.scalar()
            print(f"\n✅ {quiz_count} existing quizzes updated with new fields")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            print("\n⚠️  This might be because:")
            print("   1. The columns already exist (run migration again to check)")
            print("   2. Database connection issue")
            print("   3. Insufficient permissions")
            raise

if __name__ == '__main__':
    print("=" * 60)
    print("🎯 Quiz Time Limits Migration")
    print("=" * 60)
    print(f"Target Database: paceacademy (PostgreSQL)")
    print("=" * 60)
    
    # Ask for confirmation
    response = input("\n⚠️  This will modify your database. Continue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        run_migration()
    else:
        print("❌ Migration cancelled by user.")
        print("   No changes were made to the database.")
