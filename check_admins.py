from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admins = User.query.filter_by(role='admin').all()
    print("\n--- ADMIN ACCOUNTS ---")
    for u in admins:
        print(f"Email: {u.email} | Username: {u.username}")
    print("----------------------\n")
