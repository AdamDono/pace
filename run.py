from app import create_app, db
from app.models import User

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Drop all tables first (only for development)
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        # Add test user
        if not User.query.filter_by(email='test@example.com').first():
            user = User(
                email='test@example.com',
                password='unhashed_for_now',
                role='student'
            )
            db.session.add(user)
            db.session.commit()
    
    app.run(debug=True)