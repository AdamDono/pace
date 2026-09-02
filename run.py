from app import create_app, db
from app.models import User
import os
from dotenv import load_dotenv


load_dotenv()

app = create_app()

def ensure_admin_exists():
    """Ensure there's at least one admin user in the system"""
    with app.app_context():
        admin_exists = db.session.query(
            db.session.query(User).filter_by(role='admin').exists()
        ).scalar()

        if not admin_exists:
            admin = User(
                email=os.getenv('ADMIN_EMAIL', 'admin@example.com'),
                role='admin'
            )
            admin.password = os.getenv('ADMIN_PASSWORD', 'adminpassword')
            db.session.add(admin)
            try:
                db.session.commit()
                print("✅ Created initial admin user")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to create admin: {str(e)}")

def check_database_connection():
    """Verify database connectivity and auto-create new tables"""
    with app.app_context():
        try:
            db.session.execute(db.text('SELECT 1'))
            db.create_all()
            print("✅ Database connection successful and tables verified")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            return False


def start_scheduler():
    """
    Start the APScheduler background scheduler for recurring tasks.

    Jobs:
        - weekly_digest: Emails opted-in users a summary every Monday at 08:00.

    The scheduler is only started in the main process to avoid double-firing
    when Werkzeug's reloader spawns a child process.
    """
    # In debug mode Werkzeug spawns a child process — only run in that child
    # (WERKZEUG_RUN_MAIN == 'true') or in non-debug production mode.
    is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    is_production = os.getenv('FLASK_DEBUG', 'false').lower() != 'true'

    if is_reloader_child or is_production:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            from app.utils.digest import send_weekly_digests
            from app.utils.nudge import send_inactivity_nudges

            scheduler = BackgroundScheduler()
            # 1. Weekly Digest (Every Monday at 08:00 AM)
            scheduler.add_job(
                func=send_weekly_digests,
                args=[app],
                trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
                id='weekly_digest',
                name='Weekly Digest Email',
                replace_existing=True,
            )
            # 2. Daily Inactivity & Progress Nudges (Every Morning at 09:00 AM)
            scheduler.add_job(
                func=send_inactivity_nudges,
                args=[app],
                trigger=CronTrigger(hour=9, minute=0),
                id='daily_inactivity_nudges',
                name='Daily Inactivity Nudge Emails',
                replace_existing=True,
            )
            scheduler.start()
            print("✅ Scheduler started — Weekly digest (Mondays 08:00) & Daily nudges (Daily 09:00) are active")
            return scheduler
        except ImportError:
            print("⚠️ Notice: 'apscheduler' not installed locally — skipping background cron scheduler.")
            return None
    return None


if __name__ == '__main__':

    if not check_database_connection():
        exit(1)

    # Ensure admin exists
    ensure_admin_exists()

    # Start background scheduler (weekly digest, etc.)
    start_scheduler()

    # Run the application
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )
