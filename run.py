from app import create_app, db
from app.models import User
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = create_app()

def ensure_admin_exists():
    """Ensure there's at least one admin user in the system"""
    with app.app_context():
        # Check if any admin exists
        admin_exists = db.session.query(
            db.session.query(User).filter_by(role='admin').exists()
        ).scalar()

        if not admin_exists:
            admin = User(
                email=os.getenv('ADMIN_EMAIL', 'admin@example.com'),
                password=os.getenv('ADMIN_PASSWORD', 'adminpassword'),
                role='admin'
            )
            db.session.add(admin)
            try:
                db.session.commit()
                print("✅ Created initial admin user")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to create admin: {str(e)}")

def check_database_connection():
    """Verify database connectivity"""
    with app.app_context():
        try:
            db.session.execute(db.text('SELECT 1'))
            print("✅ Database connection successful")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            return False

if __name__ == '__main__':
    # Verify database connection first
    if not check_database_connection():
        exit(1)
    
    # Ensure admin exists
    ensure_admin_exists()
    
    # Run the application
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )