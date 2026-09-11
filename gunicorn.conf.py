"""
Gunicorn configuration for Pace Academy.

Key responsibility: start APScheduler in exactly ONE worker process so that
the daily inactivity nudge and weekly digest cron jobs fire reliably without
duplicate emails being sent by multiple workers.
"""
import os

# ── Server socket ────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# ── Worker processes ─────────────────────────────────────────────────────────
workers = 2
worker_class = "sync"
timeout = 120

# ── Logging ──────────────────────────────────────────────────────────────────
loglevel = "info"
accesslog = "-"
errorlog = "-"

# ── Scheduler bootstrap ───────────────────────────────────────────────────────
# APScheduler must only run in ONE worker to avoid duplicate emails.
# We use the post_fork hook: only the worker with arbiter PID's first child
# (i.e. worker_id == 1 based on os.getpid() comparison) starts the scheduler.
# The simplest reliable approach: use a file lock so only the first worker wins.

_scheduler_started = False

def post_fork(server, worker):
    """Called in the worker process after forking. Start scheduler in worker #1 only."""
    global _scheduler_started
    # Each worker gets here independently; use a simple lock file so only one wins.
    lock_path = "/tmp/pace_scheduler.lock"
    try:
        # Try to create lock file exclusively
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)

        # This worker won the lock — start the scheduler
        from app import create_app
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.utils.digest import send_weekly_digests
        from app.utils.nudge import send_inactivity_nudges

        app = create_app()

        scheduler = BackgroundScheduler()

        # 1. Weekly Digest — every Monday at 08:00 (server time = UTC)
        scheduler.add_job(
            func=send_weekly_digests,
            args=[app],
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_digest',
            name='Weekly Digest Email',
            replace_existing=True,
        )
        # 2. Daily Inactivity Nudge — every day at 09:00 AM
        scheduler.add_job(
            func=send_inactivity_nudges,
            args=[app],
            trigger=CronTrigger(hour=9, minute=0),
            id='daily_inactivity_nudges',
            name='Daily Inactivity Nudge Emails',
            replace_existing=True,
        )
        scheduler.start()
        server.log.info("✅ APScheduler started in worker PID %s — cron jobs active.", os.getpid())

    except FileExistsError:
        # Another worker already owns the scheduler — this is expected
        server.log.info("ℹ️  Scheduler already running in another worker — skipping (PID %s).", os.getpid())

def on_exit(server):
    """Clean up the lock file when gunicorn exits."""
    lock_path = "/tmp/pace_scheduler.lock"
    try:
        os.remove(lock_path)
    except FileNotFoundError:
        pass
