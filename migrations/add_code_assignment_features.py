"""
Migration script to add code assignment and execution features
Run this from the project root: python migrations/add_code_assignment_features.py
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
        print("🔄 Starting migration: Adding code assignment features...")
        
        try:
            # Add new columns to assignments table
            print("  ➕ Adding code assignment fields to assignments table...")
            
            db.session.execute(text("""
                ALTER TABLE assignments 
                ADD COLUMN IF NOT EXISTS is_coding_assignment BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS programming_language VARCHAR(20),
                ADD COLUMN IF NOT EXISTS starter_code TEXT,
                ADD COLUMN IF NOT EXISTS allow_file_upload BOOLEAN DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS enable_code_execution BOOLEAN DEFAULT FALSE
            """))
            
            # Add new columns to assignment_submissions table
            print("  ➕ Adding code submission fields to assignment_submissions table...")
            
            db.session.execute(text("""
                ALTER TABLE assignment_submissions 
                ADD COLUMN IF NOT EXISTS code_submission TEXT,
                ADD COLUMN IF NOT EXISTS submission_type VARCHAR(20) DEFAULT 'text',
                ADD COLUMN IF NOT EXISTS programming_language VARCHAR(20),
                ADD COLUMN IF NOT EXISTS execution_output TEXT,
                ADD COLUMN IF NOT EXISTS execution_error TEXT,
                ADD COLUMN IF NOT EXISTS grade FLOAT
            """))
            
            # Create indexes for better performance
            print("  ➕ Creating indexes...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_assignments_coding ON assignments(is_coding_assignment);
            """))
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_submissions_type ON assignment_submissions(submission_type);
            """))
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("\n💻 Code assignment features are now enabled:")
            print("   - CodeMirror editor support")
            print("   - Multiple programming languages")
            print("   - Starter code templates")
            print("   - Code execution (Python & JavaScript)")
            print("   - File upload support")
            print("   - Syntax highlighting")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()
