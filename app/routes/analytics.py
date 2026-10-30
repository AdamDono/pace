import csv
import hashlib
import io
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import csrf, db
from app.models import Course, Enrollment, Lead, SiteAnalyticsEvent, User

analytics_bp = Blueprint('analytics', __name__)

_BOT_SIGNATURES = (
    'bot', 'crawl', 'spider', 'slurp', 'headless', 'uptime',
    'pingdom', 'lighthouse', 'gtmetrix', 'facebookexternalhit',
    'whatsapp', 'python-requests', 'curl/', 'wget/'
)


def is_analytics_user(user=None) -> bool:
    """Returns True if the user is analytics@gmail.com, has role='analytics', or is admin."""
    u = user or current_user
    if not u or not getattr(u, 'is_authenticated', False):
        return False
    email = (getattr(u, 'email', '') or '').strip().lower()
    role = (getattr(u, 'role', '') or '').strip().lower()
    return email == 'analytics@gmail.com' or role in ('analytics', 'admin')


def _parse_user_agent(ua_str: str) -> tuple:
    """Returns (device_type, browser, os_name) from User-Agent string."""
    ua = (ua_str or '').lower()

    # Device type
    if any(k in ua for k in ('ipad', 'tablet', 'kindle', 'playbook')) or ('android' in ua and 'mobile' not in ua):
        device = 'Tablet'
    elif any(k in ua for k in ('mobi', 'iphone', 'ipod', 'android', 'windows phone')):
        device = 'Mobile'
    else:
        device = 'Desktop'

    # Browser
    if 'samsungbrowser' in ua:
        browser = 'Samsung Internet'
    elif 'edg/' in ua or 'edga/' in ua or 'edgios/' in ua:
        browser = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        browser = 'Opera'
    elif 'chrome/' in ua or 'crios/' in ua:
        browser = 'Chrome'
    elif 'firefox/' in ua or 'fxios/' in ua:
        browser = 'Firefox'
    elif 'safari/' in ua:
        browser = 'Safari'
    else:
        browser = 'Other'

    # OS
    if 'iphone' in ua or 'ipad' in ua or 'ipod' in ua:
        os_name = 'iOS'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'windows' in ua:
        os_name = 'Windows'
    elif 'mac os x' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'linux' in ua:
        os_name = 'Linux'
    else:
        os_name = 'Other'

    return device, browser, os_name


def _classify_referrer(referrer_url: str, utm_source: str, host: str) -> str:
    """Classifies traffic origin into clean marketing channels."""
    src = (utm_source or '').strip().lower()
    ref = (referrer_url or '').strip().lower()

    if src:
        if any(k in src for k in ('fb', 'facebook', 'meta')):
            return 'Facebook / Meta'
        if any(k in src for k in ('ig', 'insta', 'instagram')):
            return 'Instagram'
        if 'whatsapp' in src or src == 'wa':
            return 'WhatsApp'
        if 'tiktok' in src:
            return 'TikTok'
        if 'google' in src or 'adwords' in src or 'gads' in src:
            return 'Google Search / Ads'
        if 'linkedin' in src:
            return 'LinkedIn'
        if 'youtube' in src or 'yt' == src:
            return 'YouTube'
        return utm_source.strip().title()[:80]

    if not ref:
        return 'Direct'

    try:
        parsed = urlparse(ref)
        domain = (parsed.netloc or '').lower().replace('www.', '')
    except Exception:
        domain = ''

    if not domain or (host and domain == host.lower().replace('www.', '')):
        return 'Direct'
    if 'whatsapp' in domain or 'wa.me' in domain:
        return 'WhatsApp'
    if 'facebook.' in domain or 'fb.com' in domain or 'fb.me' in domain or 'm.facebook.' in domain:
        return 'Facebook / Meta'
    if 'instagram.' in domain or 'l.instagram.' in domain:
        return 'Instagram'
    if 'tiktok.' in domain:
        return 'TikTok'
    if 'google.' in domain:
        return 'Google Search / Ads'
    if 'bing.' in domain or 'yahoo.' in domain or 'duckduckgo.' in domain:
        return 'Organic Search'
    if 'linkedin.' in domain or 'lnkd.in' in domain:
        return 'LinkedIn'
    if 'youtube.' in domain or 'youtu.be' in domain:
        return 'YouTube'
    if 't.co' == domain or 'twitter.' in domain or 'x.com' in domain:
        return 'X / Twitter'
    return domain[:80]


def record_analytics_event(
    event_type: str,
    event_label: str = None,
    page_path: str = None,
    custom_utm: dict = None
) -> None:
    """
    Safely records a first-party analytics event into SiteAnalyticsEvent.
    Never raises an exception so user requests are never interrupted.
    """
    try:
        ua_str = request.headers.get('User-Agent', '') or ''
        ua_lower = ua_str.lower()
        if any(bot in ua_lower for bot in _BOT_SIGNATURES) and event_type == 'page_view':
            return

        forwarded = request.headers.get('X-Forwarded-For', '')
        raw_ip = forwarded.split(',')[0].strip() if forwarded else (request.remote_addr or '0.0.0.0')
        visitor_hash = hashlib.sha256(f"pace_v1_{raw_ip}_{ua_str[:120]}".encode('utf-8')).hexdigest()[:24]

        # Maintain visitor session id and sticky first-touch attribution in session
        sess_id = session.get('_pace_an_sid')
        if not sess_id:
            sess_id = uuid.uuid4().hex[:24]
            session['_pace_an_sid'] = sess_id

        custom_utm = custom_utm or {}
        utm_source = (
            custom_utm.get('utm_source')
            or request.args.get('utm_source')
            or session.get('_pace_utm_source')
            or ''
        ).strip()[:100]
        utm_medium = (
            custom_utm.get('utm_medium')
            or request.args.get('utm_medium')
            or session.get('_pace_utm_medium')
            or ''
        ).strip()[:100]
        utm_campaign = (
            custom_utm.get('utm_campaign')
            or request.args.get('utm_campaign')
            or session.get('_pace_utm_campaign')
            or ''
        ).strip()[:150]

        if utm_source:
            session['_pace_utm_source'] = utm_source
        if utm_medium:
            session['_pace_utm_medium'] = utm_medium
        if utm_campaign:
            session['_pace_utm_campaign'] = utm_campaign

        raw_referrer = (custom_utm.get('referrer') or request.referrer or '').strip()[:500]
        host = request.host.split(':')[0] if request.host else ''
        classified_source = _classify_referrer(raw_referrer, utm_source, host)

        # Keep first non-Direct referrer sticky in session for funnel attribution
        if classified_source != 'Direct':
            session['_pace_ref_source'] = classified_source
        elif session.get('_pace_ref_source'):
            classified_source = session.get('_pace_ref_source')

        device_type, browser, os_name = _parse_user_agent(ua_str)
        uid = current_user.id if (current_user and getattr(current_user, 'is_authenticated', False)) else None

        ev = SiteAnalyticsEvent(
            visitor_hash=visitor_hash,
            session_id=sess_id,
            user_id=uid,
            event_type=(event_type or 'page_view')[:50],
            event_label=(event_label or '')[:255] if event_label else None,
            page_path=(page_path or request.path or '/')[:255],
            referrer_source=classified_source[:100],
            referrer_url=raw_referrer if raw_referrer else None,
            utm_source=utm_source if utm_source else None,
            utm_medium=utm_medium if utm_medium else None,
            utm_campaign=utm_campaign if utm_campaign else None,
            device_type=device_type,
            browser=browser,
            os_name=os_name,
        )
        db.session.add(ev)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.debug(f"Analytics event skipped: {exc}")


@analytics_bp.route('/analytics/event', methods=['POST'])
@csrf.exempt
def capture_client_event():
    """Public JSON endpoint for client-side funnel & interaction tracking."""
    data = request.get_json(silent=True) or {}
    event_type = (data.get('event_type') or '').strip()
    event_label = (data.get('event_label') or '').strip()
    page_path = (data.get('page_path') or request.path or '/').strip()

    allowed_types = {
        'page_view', 'bookworm_open', 'bookworm_question',
        'pricing_tab_click', 'plan_modal_open', 'lead_submitted',
        'cta_click', 'course_view'
    }
    if event_type not in allowed_types:
        return jsonify({'ok': False}), 400

    record_analytics_event(
        event_type=event_type,
        event_label=event_label,
        page_path=page_path,
        custom_utm={
            'utm_source': data.get('utm_source'),
            'utm_medium': data.get('utm_medium'),
            'utm_campaign': data.get('utm_campaign'),
            'referrer': data.get('referrer'),
        }
    )
    return jsonify({'ok': True})


def _resolve_period_start(period: str):
    now = datetime.utcnow()
    if period == 'today':
        return datetime(now.year, now.month, now.day)
    if period == '7d':
        return now - timedelta(days=7)
    if period == '30d':
        return now - timedelta(days=30)
    if period == '90d':
        return now - timedelta(days=90)
    return None  # 'all'


@analytics_bp.route('/analytics')
@analytics_bp.route('/analytics/dashboard')
@login_required
def dashboard():
    """Dedicated Executive Analytics Command Center for analytics@gmail.com and admins."""
    if not is_analytics_user():
        abort(403)

    period = request.args.get('period', '30d').strip().lower()
    if period not in ('today', '7d', '30d', '90d', 'all'):
        period = '30d'

    start_dt = _resolve_period_start(period)
    base_q = SiteAnalyticsEvent.query
    lead_q = Lead.query
    if start_dt:
        base_q = base_q.filter(SiteAnalyticsEvent.created_at >= start_dt)
        lead_q = lead_q.filter(Lead.created_at >= start_dt)

    # 1. Core KPIs
    total_pageviews = base_q.filter(SiteAnalyticsEvent.event_type == 'page_view').count()
    unique_visitors = (
        db.session.query(func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)))
        .filter(*([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else []))
        .scalar()
        or 0
    )
    unique_sessions = (
        db.session.query(func.count(func.distinct(SiteAnalyticsEvent.session_id)))
        .filter(*([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else []))
        .scalar()
        or 0
    )
    bookworm_opens = base_q.filter(SiteAnalyticsEvent.event_type == 'bookworm_open').count()
    bookworm_questions = base_q.filter(SiteAnalyticsEvent.event_type == 'bookworm_question').count()
    pricing_tab_clicks = base_q.filter(SiteAnalyticsEvent.event_type == 'pricing_tab_click').count()
    plan_modal_opens = base_q.filter(SiteAnalyticsEvent.event_type == 'plan_modal_open').count()
    cta_clicks = base_q.filter(SiteAnalyticsEvent.event_type == 'cta_click').count()

    leads_in_period = lead_q.order_by(Lead.created_at.desc()).all()
    total_leads = len(leads_in_period)
    conversion_rate = round((total_leads / unique_visitors) * 100, 1) if unique_visitors > 0 else 0.0

    # Platform-wide totals
    total_students = User.query.filter_by(role='student').count()
    total_enrollments = Enrollment.query.count()
    total_courses = Course.query.filter_by(status='approved').count()

    # 2. Daily Traffic Series (Last 14 days or selected window)
    chart_days = 14 if period in ('today', '7d', '30d') else 30
    now = datetime.utcnow()
    day_labels = []
    daily_pageviews = []
    daily_visitors = []

    window_start = datetime(now.year, now.month, now.day) - timedelta(days=chart_days - 1)
    recent_events = (
        SiteAnalyticsEvent.query
        .filter(SiteAnalyticsEvent.created_at >= window_start)
        .all()
    )
    pv_by_day = {}
    vis_by_day = {}
    for ev in recent_events:
        d_key = ev.created_at.strftime('%Y-%m-%d')
        if ev.event_type == 'page_view':
            pv_by_day[d_key] = pv_by_day.get(d_key, 0) + 1
        vis_by_day.setdefault(d_key, set()).add(ev.visitor_hash)

    for i in range(chart_days):
        d_obj = window_start + timedelta(days=i)
        d_key = d_obj.strftime('%Y-%m-%d')
        day_labels.append(d_obj.strftime('%d %b'))
        daily_pageviews.append(pv_by_day.get(d_key, 0))
        daily_visitors.append(len(vis_by_day.get(d_key, set())))

    # 3. Traffic Sources Breakdown
    source_rows = (
        db.session.query(
            SiteAnalyticsEvent.referrer_source,
            func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).label('visitors'),
            func.count(SiteAnalyticsEvent.id).label('events')
        )
        .filter(*([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else []))
        .group_by(SiteAnalyticsEvent.referrer_source)
        .order_by(func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).desc())
        .all()
    )
    traffic_sources = [
        {
            'source': r.referrer_source or 'Direct',
            'visitors': r.visitors,
            'events': r.events,
            'pct': round((r.visitors / unique_visitors) * 100, 1) if unique_visitors else 0
        }
        for r in source_rows
    ]

    # 4. Device Breakdown & Browser Breakdown
    device_rows = (
        db.session.query(
            SiteAnalyticsEvent.device_type,
            func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).label('visitors')
        )
        .filter(*([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else []))
        .group_by(SiteAnalyticsEvent.device_type)
        .order_by(func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).desc())
        .all()
    )
    devices = [
        {
            'device': r.device_type or 'Desktop',
            'visitors': r.visitors,
            'pct': round((r.visitors / unique_visitors) * 100, 1) if unique_visitors else 0
        }
        for r in device_rows
    ]

    os_rows = (
        db.session.query(
            SiteAnalyticsEvent.os_name,
            func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).label('visitors')
        )
        .filter(*([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else []))
        .group_by(SiteAnalyticsEvent.os_name)
        .order_by(func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).desc())
        .all()
    )

    # 5. Pricing Tabs & Plan Interest Breakdown
    tab_rows = (
        db.session.query(
            SiteAnalyticsEvent.event_label,
            func.count(SiteAnalyticsEvent.id).label('clicks')
        )
        .filter(
            SiteAnalyticsEvent.event_type == 'pricing_tab_click',
            *([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else [])
        )
        .group_by(SiteAnalyticsEvent.event_label)
        .order_by(func.count(SiteAnalyticsEvent.id).desc())
        .all()
    )

    plan_rows = (
        db.session.query(
            SiteAnalyticsEvent.event_label,
            func.count(SiteAnalyticsEvent.id).label('opens')
        )
        .filter(
            SiteAnalyticsEvent.event_type == 'plan_modal_open',
            *([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else [])
        )
        .group_by(SiteAnalyticsEvent.event_label)
        .order_by(func.count(SiteAnalyticsEvent.id).desc())
        .all()
    )

    # 6. Top Pages Visited
    page_rows = (
        db.session.query(
            SiteAnalyticsEvent.page_path,
            func.count(SiteAnalyticsEvent.id).label('views'),
            func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).label('visitors')
        )
        .filter(
            SiteAnalyticsEvent.event_type == 'page_view',
            *([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else [])
        )
        .group_by(SiteAnalyticsEvent.page_path)
        .order_by(func.count(SiteAnalyticsEvent.id).desc())
        .limit(10)
        .all()
    )

    # 7. UTM Ad Campaign Attribution Table (for paid ads!)
    utm_rows = (
        db.session.query(
            SiteAnalyticsEvent.utm_source,
            SiteAnalyticsEvent.utm_medium,
            SiteAnalyticsEvent.utm_campaign,
            func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).label('visitors'),
            func.count(SiteAnalyticsEvent.id).label('events')
        )
        .filter(
            SiteAnalyticsEvent.utm_source.isnot(None),
            SiteAnalyticsEvent.utm_source != '',
            *([SiteAnalyticsEvent.created_at >= start_dt] if start_dt else [])
        )
        .group_by(
            SiteAnalyticsEvent.utm_source,
            SiteAnalyticsEvent.utm_medium,
            SiteAnalyticsEvent.utm_campaign
        )
        .order_by(func.count(func.distinct(SiteAnalyticsEvent.visitor_hash)).desc())
        .limit(15)
        .all()
    )

    # 8. Live Recent Activity Feed (latest 35 events)
    recent_feed = (
        SiteAnalyticsEvent.query
        .order_by(SiteAnalyticsEvent.created_at.desc())
        .limit(35)
        .all()
    )

    return render_template(
        'analytics/dashboard.html',
        period=period,
        total_pageviews=total_pageviews,
        unique_visitors=unique_visitors,
        unique_sessions=unique_sessions,
        bookworm_opens=bookworm_opens,
        bookworm_questions=bookworm_questions,
        pricing_tab_clicks=pricing_tab_clicks,
        plan_modal_opens=plan_modal_opens,
        cta_clicks=cta_clicks,
        total_leads=total_leads,
        conversion_rate=conversion_rate,
        total_students=total_students,
        total_enrollments=total_enrollments,
        total_courses=total_courses,
        day_labels=day_labels,
        daily_pageviews=daily_pageviews,
        daily_visitors=daily_visitors,
        traffic_sources=traffic_sources,
        devices=devices,
        os_rows=os_rows,
        tab_rows=tab_rows,
        plan_rows=plan_rows,
        page_rows=page_rows,
        utm_rows=utm_rows,
        recent_feed=recent_feed,
        recent_leads=leads_in_period[:12],
    )


@analytics_bp.route('/analytics/export.csv')
@login_required
def export_csv():
    """Exports analytics events to CSV for Excel, Google Sheets, or grant reporting."""
    if not is_analytics_user():
        abort(403)

    period = request.args.get('period', '30d').strip().lower()
    start_dt = _resolve_period_start(period)
    q = SiteAnalyticsEvent.query
    if start_dt:
        q = q.filter(SiteAnalyticsEvent.created_at >= start_dt)
    events = q.order_by(SiteAnalyticsEvent.created_at.desc()).limit(5000).all()

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow([
        'Timestamp (UTC)', 'Event Type', 'Event Label', 'Page Path',
        'Traffic Source', 'UTM Source', 'UTM Medium', 'UTM Campaign',
        'Device Type', 'OS', 'Browser', 'Visitor Hash'
    ])
    for ev in events:
        writer.writerow([
            ev.created_at.strftime('%Y-%m-%d %H:%M:%S') if ev.created_at else '',
            ev.event_type,
            ev.event_label or '',
            ev.page_path or '',
            ev.referrer_source or 'Direct',
            ev.utm_source or '',
            ev.utm_medium or '',
            ev.utm_campaign or '',
            ev.device_type or '',
            ev.os_name or '',
            ev.browser or '',
            ev.visitor_hash or ''
        ])

    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=pace_analytics_{period}.csv'}
    )

