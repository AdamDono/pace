from app import create_app, db
from app.models import User
import os

app = create_app()

def initialize_database():
    with app.app_context():
        print("Dropping existing tables...")
        db.drop_all()  # Clears old schema
        
        print("Creating fresh tables...")
        db.create_all()  # Creates new schema based on current models
        
        # Verify table creation
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            raise RuntimeError("Failed to create 'users' table!")
        
        # Create initial admin only in development
        if os.getenv('FLASK_ENV') == 'development':
            if not User.query.first():
                admin = User(
                    email=os.getenv('ADMIN_EMAIL', 'admin@example.com'),
                    password=os.getenv('ADMIN_PASSWORD', 'adminpassword'),
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("Initial admin user created")

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)