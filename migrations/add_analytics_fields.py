"""
Migration script to add analytics tracking fields to enrollment_sections table
Run this from the project root: python migrations/add_analytics_fields.py
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
        print("🔄 Starting migration: Adding analytics fields to enrollment_sections...")
        
        try:
            # Detect database type
            from sqlalchemy.engine import reflection
            inspector = reflection.Inspector.from_engine(db.engine)
            
            # Get existing columns
            columns = inspector.get_columns('enrollment_sections')
            existing_columns = [col['name'] for col in columns]
            
            print(f"  ℹ️  Database: {db.engine.name}")
            print(f"  ℹ️  Existing columns: {len(existing_columns)}")
            
            # Define columns to add (PostgreSQL syntax)
            columns_to_add = {
                'time_spent': 'INTEGER DEFAULT 0',
                'last_accessed': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'view_count': 'INTEGER DEFAULT 0',
                'started_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            # Add columns that don't exist
            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_columns:
                    print(f"  ➕ Adding column: {column_name}")
                    db.session.execute(text(f"ALTER TABLE enrollment_sections ADD COLUMN {column_name} {column_type}"))
                else:
                    print(f"  ✓ Column already exists: {column_name}")
            
            # Initialize timestamps for existing records (works for both SQLite and PostgreSQL)
            print("  🔄 Initializing timestamps for existing records...")
            db.session.execute(text("""
                UPDATE enrollment_sections 
                SET started_at = CURRENT_TIMESTAMP 
                WHERE started_at IS NULL
            """))
            db.session.execute(text("""
                UPDATE enrollment_sections 
                SET last_accessed = CURRENT_TIMESTAMP 
                WHERE last_accessed IS NULL
            """))
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("\n📊 Analytics tracking is now enabled:")
            print("   - Time spent tracking (in seconds)")
            print("   - Last accessed timestamps")
            print("   - View count per section")
            print("   - Section start date tracking")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    run_migration()
