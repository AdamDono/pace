"""
Database migration: Add user tracking fields

This adds the following columns to the users table:
- first_name (String(80))
- last_name (String(80))
- specialization (String(200))
- last_login (DateTime)
- created_at (DateTime)
- login_count (Integer)

Run this migration:
    python migrations/add_user_tracking_fields.py
"""

import sqlite3
import os
from datetime import datetime

def migrate():
    # Try common database locations
    db_paths = [
        'default.db',
        'instance/lms.db',
        'lms.db',
        'instance/default.db'
    ]
    
    conn = None
    db_path = None
    
    for path in db_paths:
        try:
            if os.path.exists(path):
                conn = sqlite3.connect(path)
                db_path = path
                print(f"✓ Found database at: {path}")
                break
        except:
            continue
    
    if conn is None:
        print("\n❌ No database found!")
        print("\nSearched for:")
        for path in db_paths:
            print(f"  - {path}")
        print("\n💡 Solution:")
        print("1. Make sure your Flask app is configured")
        print("2. Run this command to initialize the database:")
        print("   flask shell")
        print("   >>> from app import db")
        print("   >>> db.create_all()")
        print("   >>> exit()")
        print("\n3. Then run this migration again")
        return
    
    cursor = conn.cursor()
    
    try:
        print("Adding new columns to users table...")
        
        # Add first_name
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN first_name VARCHAR(80)")
            print("✓ Added first_name column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ first_name column already exists")
            else:
                raise
        
        # Add last_name
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_name VARCHAR(80)")
            print("✓ Added last_name column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ last_name column already exists")
            else:
                raise
        
        # Add specialization
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN specialization VARCHAR(200)")
            print("✓ Added specialization column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ specialization column already exists")
            else:
                raise
        
        # Add last_login
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")
            print("✓ Added last_login column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ last_login column already exists")
            else:
                raise
        
        # Add created_at
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at DATETIME")
            print("✓ Added created_at column")
            
            # Set default value for existing users
            cursor.execute(f"UPDATE users SET created_at = ? WHERE created_at IS NULL", 
                         (datetime.utcnow().isoformat(),))
            print("✓ Set default created_at for existing users")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ created_at column already exists")
            else:
                raise
        
        # Add login_count
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0")
            print("✓ Added login_count column")
            
            # Set default value for existing users
            cursor.execute("UPDATE users SET login_count = 0 WHERE login_count IS NULL")
            print("✓ Set default login_count for existing users")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("⚠ login_count column already exists")
            else:
                raise
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 50)
    print("User Tracking Fields Migration")
    print("=" * 50)
    migrate()
