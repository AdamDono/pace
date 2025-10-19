#!/usr/bin/env python3
"""
Database migration: Add user tracking fields for PostgreSQL

This adds the following columns to the users table:
- first_name (String(80))
- last_name (String(80))
- specialization (String(200))
- last_login (DateTime)
- created_at (DateTime)
- login_count (Integer)

Run this migration:
    python3 migrations/add_user_tracking_fields_postgres.py
"""

from app import create_app, db
from sqlalchemy import text
from datetime import datetime

def migrate():
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("User Tracking Fields Migration (PostgreSQL)")
        print("=" * 50)
        
        try:
            print("Adding new columns to users table...")
            
            # Add first_name
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN first_name VARCHAR(80)"))
                print("✓ Added first_name column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ first_name column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add last_name
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN last_name VARCHAR(80)"))
                print("✓ Added last_name column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ last_name column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add specialization
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN specialization VARCHAR(200)"))
                print("✓ Added specialization column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ specialization column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add last_login
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP"))
                print("✓ Added last_login column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ last_login column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add created_at
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                print("✓ Added created_at column")
                
                # Set default value for existing users
                db.session.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
                print("✓ Set default created_at for existing users")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ created_at column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add login_count
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0"))
                print("✓ Added login_count column")
                
                # Set default value for existing users
                db.session.execute(text("UPDATE users SET login_count = 0 WHERE login_count IS NULL"))
                print("✓ Set default login_count for existing users")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print("⚠ login_count column already exists")
                    db.session.rollback()
                else:
                    raise
            
            db.session.commit()
            print("\n✅ Migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {e}")
            raise

if __name__ == '__main__':
    print("=" * 50)
    print("User Tracking Fields Migration")
    print("=" * 50)
    migrate()
