#!/usr/bin/env python3
"""
Database migration: Add user suspension/ban fields

This adds the following columns to the users table:
- is_suspended (Boolean)
- is_banned (Boolean)
- suspension_reason (Text)
- suspended_at (DateTime)
- suspended_until (DateTime)
- suspended_by (Integer - FK to users.id)

Run this migration:
    PYTHONPATH=/Users/dam1mac89/Desktop/pace python3 migrations/add_suspension_fields.py
"""

from app import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("User Suspension/Ban Fields Migration")
        print("=" * 50)
        
        try:
            print("Adding suspension/ban columns to users table...")
            
            # Add is_suspended
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN is_suspended BOOLEAN DEFAULT FALSE"))
                print("✓ Added is_suspended column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ is_suspended column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add is_banned
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE"))
                print("✓ Added is_banned column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ is_banned column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add suspension_reason
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN suspension_reason TEXT"))
                print("✓ Added suspension_reason column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ suspension_reason column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add suspended_at
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN suspended_at TIMESTAMP"))
                print("✓ Added suspended_at column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ suspended_at column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add suspended_until
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN suspended_until TIMESTAMP"))
                print("✓ Added suspended_until column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ suspended_until column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Add suspended_by
            try:
                db.session.execute(text("ALTER TABLE users ADD COLUMN suspended_by INTEGER REFERENCES users(id)"))
                print("✓ Added suspended_by column")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e).lower():
                    print("⚠ suspended_by column already exists")
                    db.session.rollback()
                else:
                    raise
            
            # Set default values for existing users
            try:
                db.session.execute(text("UPDATE users SET is_suspended = FALSE WHERE is_suspended IS NULL"))
                db.session.execute(text("UPDATE users SET is_banned = FALSE WHERE is_banned IS NULL"))
                print("✓ Set default values for existing users")
            except Exception as e:
                print(f"⚠ Could not set defaults: {e}")
                db.session.rollback()
            
            db.session.commit()
            print("\n✅ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Restart your Flask server")
            print("2. Test suspension features in admin panel")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {e}")
            raise

if __name__ == '__main__':
    migrate()
