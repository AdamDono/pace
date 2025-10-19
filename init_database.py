#!/usr/bin/env python3
"""
Initialize the database and create all tables
Run this before the migration
"""

from app import create_app, db
from app.models import User

def init_db():
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database initialized successfully!")
        print(f"✅ Database location: default.db")
        
        # Check if admin exists
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("\n💡 No admin user found. Creating one...")
            admin = User(
                email='admin@pace.com',
                username='admin',
                password='admin123',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created!")
            print("   Email: admin@pace.com")
            print("   Password: admin123")
        else:
            print(f"\n✅ Admin user already exists: {admin.email}")

if __name__ == '__main__':
    init_db()
