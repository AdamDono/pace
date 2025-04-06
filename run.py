from app import create_app, db
from app.models import User

app = create_app()

def initialize_database():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        # Check if tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            raise RuntimeError("Failed to create 'users' table!")
        
        # Create initial admin user if none exists
        if not User.query.first():
            admin = User(
                email='admin@example.com',
                password='adminpassword',  # CHANGE THIS IN PRODUCTION!
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Created admin user: admin@example.com / adminpassword")

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)