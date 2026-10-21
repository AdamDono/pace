import os
import sys
from dotenv import load_dotenv

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

remote_url = os.getenv('DATABASE_URL')
if not remote_url:
    print("❌ DATABASE_URL is not set.")
    sys.exit(1)

os.makedirs('instance', exist_ok=True)
local_db_path = os.path.abspath('instance/pace_local.db')
local_url = f'sqlite:///{local_db_path}'

# Point app to local SQLite so create_app() sets up local tables instantly
os.environ['DATABASE_URL'] = local_url

from app import create_app, db
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker

print("📦 Creating local SQLite database schema...")
app = create_app()
with app.app_context():
    db.create_all()
    print("✅ Local SQLite schema created.")

print("🔌 Connecting to remote Neon PostgreSQL to fetch live data...")
remote_engine = create_engine(remote_url)
remote_meta = MetaData()
remote_meta.reflect(bind=remote_engine)

local_engine = create_engine(local_url)
LocalSession = sessionmaker(bind=local_engine)
RemoteSession = sessionmaker(bind=remote_engine)

remote_session = RemoteSession()
local_session = LocalSession()

ordered_tables = [
    'users', 'courses', 'course_co_teachers', 'modules', 'sections',
    'quizzes', 'quiz_questions', 'quiz_attempts',
    'assignments', 'assignment_submissions',
    'enrollments', 'enrollment_sections',
    'forum_threads', 'forum_replies', 'forum_upvotes',
    'leads', 'live_sessions', 'live_attendances',
    'notifications', 'notification_preferences'
]

print("\n🚀 Transferring real data to local database...")
for tname in ordered_tables:
    if tname in remote_meta.tables:
        rtable = remote_meta.tables[tname]
        rows = remote_session.execute(rtable.select()).fetchall()
        if rows:
            ltable = Table(tname, MetaData(), autoload_with=local_engine)
            col_names = [col.name for col in ltable.columns]
            
            insert_dicts = []
            for row in rows:
                row_dict = dict(row._mapping)
                filtered_dict = {k: v for k, v in row_dict.items() if k in col_names}
                insert_dicts.append(filtered_dict)
            
            local_session.execute(ltable.insert(), insert_dicts)
            local_session.commit()
            print(f"  ✓ {tname}: {len(rows)} records synced")

remote_session.close()
local_session.close()
print(f"\n🎉 Local database sync complete! Database is saved at {local_db_path}")
