import secrets
from datetime import date, datetime, timedelta

from app import db
from app.models import MovementKick, MovementSession, Settings

SESSION_LIMIT_SECONDS = 7200
TARGET_KICKS = 10


def format_duration(seconds):
    if seconds is None:
        return '—'
    seconds = int(seconds)
    if seconds < 0:
        return '—'
    if seconds < 60:
        return f'{seconds}秒'
    mins, secs = divmod(seconds, 60)
    if secs == 0:
        return f'{mins}分'
    return f'{mins}分{secs}秒'


def select_display_session(day_sessions):
    """优先取当日达标会话，否则取最近有一次点击的会话。"""
    qualified = next((s for s in day_sessions if s.is_qualified), None)
    if qualified:
        return qualified
    with_kicks = [s for s in day_sessions if s.started_at]
    if with_kicks:
        return with_kicks[-1]
    return day_sessions[-1] if day_sessions else None


def build_kick_rows(session):
    kicks = session.kicks.order_by(MovementKick.sequence).all()
    rows = []
    prev_time = None
    for kick in kicks:
        interval_seconds = None
        if prev_time is not None:
            interval_seconds = int((kick.kicked_at - prev_time).total_seconds())
        rows.append({
            'sequence': kick.sequence,
            'kicked_at': kick.kicked_at,
            'interval_seconds': interval_seconds,
        })
        prev_time = kick.kicked_at
    return rows


def get_recorded_dates():
    rows = (
        db.session.query(MovementSession.session_date)
        .distinct()
        .order_by(MovementSession.session_date)
        .all()
    )
    return [row[0] for row in rows]


def get_movement_neighbor_dates(target_date):
    dates = get_recorded_dates()
    if target_date not in dates:
        prev_date = None
        next_date = None
        for recorded_date in dates:
            if recorded_date < target_date:
                prev_date = recorded_date
            elif recorded_date > target_date and next_date is None:
                next_date = recorded_date
        return prev_date, next_date

    index = dates.index(target_date)
    prev_date = dates[index - 1] if index > 0 else None
    next_date = dates[index + 1] if index < len(dates) - 1 else None
    return prev_date, next_date


def build_day_summaries(sessions):
    sessions_by_date = {}
    for session in sessions:
        key = session.session_date.isoformat()
        sessions_by_date.setdefault(key, []).append(session)

    summaries = []
    for day_str in sorted(sessions_by_date.keys(), reverse=True):
        day_sessions = sessions_by_date[day_str]
        display = select_display_session(day_sessions)
        if not display:
            continue
        summaries.append({
            'date': display.session_date,
            'date_str': day_str,
            'gestational_week': display.gestational_week,
            'gestational_day': display.gestational_day,
            'started_at': display.started_at,
            'duration_seconds': display.duration_seconds(),
            'is_qualified': any(s.is_qualified for s in day_sessions),
            'attempt_count': len(day_sessions),
        })
    summaries.sort(key=lambda row: row['date'], reverse=True)
    return summaries


def calculate_gestational_week(due_date, current_date=None):
    if current_date is None:
        current_date = date.today()
    days_until_due = (due_date - current_date).days
    gestational_days = 280 - days_until_due
    if gestational_days < 0:
        return None, None
    return gestational_days // 7, gestational_days % 7


def get_gestational_week_for_date(record_date):
    settings = Settings.query.first()
    if not settings or not settings.due_date:
        return None, None
    return calculate_gestational_week(settings.due_date, record_date)


def ensure_api_token(settings):
    if not settings.movement_api_token:
        settings.movement_api_token = secrets.token_urlsafe(32)
        db.session.commit()
    return settings.movement_api_token


def verify_api_token(token):
    if not token:
        return False
    settings = Settings.query.first()
    return bool(settings and settings.movement_api_token and settings.movement_api_token == token)


def get_qualified_session(session_date):
    return MovementSession.query.filter_by(
        session_date=session_date,
        status=MovementSession.STATUS_COMPLETED,
        is_qualified=True,
    ).first()


def get_in_progress_session(session_date):
    return MovementSession.query.filter_by(
        session_date=session_date,
        status=MovementSession.STATUS_IN_PROGRESS,
    ).first()


def finalize_timeout(session, now=None):
    if session.status != MovementSession.STATUS_IN_PROGRESS:
        return session
    if not session.started_at or session.kick_count == 0:
        return session
    if now is None:
        now = datetime.now()
    deadline = session.started_at + timedelta(seconds=SESSION_LIMIT_SECONDS)
    if now > deadline:
        session.status = MovementSession.STATUS_FAILED
        session.is_qualified = False
        session.ended_at = deadline
        session.updated_at = now
        db.session.commit()
    return session


def can_start_new_session(session_date):
    if get_qualified_session(session_date):
        return False
    in_progress = get_in_progress_session(session_date)
    if in_progress:
        finalize_timeout(in_progress)
        in_progress = get_in_progress_session(session_date)
        if in_progress:
            return False
    return True


def get_or_create_in_progress_session(session_date):
    qualified = get_qualified_session(session_date)
    if qualified:
        return qualified, False

    session = get_in_progress_session(session_date)
    if session:
        finalize_timeout(session)
        session = get_in_progress_session(session_date)
        if session:
            return session, False
        if not can_start_new_session(session_date):
            qualified = get_qualified_session(session_date)
            return qualified, False

    if not can_start_new_session(session_date):
        return get_qualified_session(session_date), False

    gestational_week, gestational_day = get_gestational_week_for_date(session_date)
    if gestational_week is None:
        gestational_week, gestational_day = 0, 0

    session = MovementSession(
        session_date=session_date,
        gestational_week=gestational_week,
        gestational_day=gestational_day,
        status=MovementSession.STATUS_IN_PROGRESS,
    )
    db.session.add(session)
    db.session.commit()
    return session, True


def repair_session_kicks(session):
    """按实际点击时间重排序号，并同步 kick_count。"""
    kicks = session.kicks.order_by(MovementKick.kicked_at, MovementKick.id).all()
    changed = False
    for index, kick in enumerate(kicks, start=1):
        if kick.sequence != index:
            kick.sequence = index
            changed = True
    actual_count = len(kicks)
    if session.kick_count != actual_count:
        session.kick_count = actual_count
        changed = True
    if actual_count == 0:
        if session.started_at is not None:
            session.started_at = None
            changed = True
    elif session.started_at is None:
        session.started_at = kicks[0].kicked_at
        changed = True
    if changed:
        session.updated_at = datetime.now()
        db.session.commit()
    return session


def add_kick(session, kicked_at=None):
    if kicked_at is None:
        kicked_at = datetime.now()

    finalize_timeout(session, kicked_at)
    db.session.refresh(session)
    repair_session_kicks(session)
    db.session.refresh(session)

    if session.status != MovementSession.STATUS_IN_PROGRESS:
        return session, 'session_not_active'

    current_count = session.kicks.count()
    if current_count >= TARGET_KICKS:
        session.kick_count = current_count
        db.session.commit()
        return session, 'already_completed'

    new_sequence = current_count + 1
    if new_sequence == 1:
        session.started_at = kicked_at

    kick = MovementKick(
        session_id=session.id,
        kicked_at=kicked_at,
        sequence=new_sequence,
    )
    db.session.add(kick)
    session.kick_count = new_sequence
    session.updated_at = kicked_at

    if new_sequence >= TARGET_KICKS:
        session.status = MovementSession.STATUS_COMPLETED
        session.is_qualified = True
        session.ended_at = kicked_at

    db.session.commit()
    return session, None


def undo_last_kick(session):
    finalize_timeout(session)
    db.session.refresh(session)
    repair_session_kicks(session)
    db.session.refresh(session)

    if session.status != MovementSession.STATUS_IN_PROGRESS:
        return session, 'session_not_active'

    last_kick = session.kicks.order_by(
        MovementKick.kicked_at.desc(),
        MovementKick.id.desc(),
    ).first()
    if not last_kick:
        return session, 'no_kick_to_undo'

    db.session.delete(last_kick)
    db.session.flush()
    session.kick_count = session.kicks.count()
    if session.kick_count <= 0:
        session.kick_count = 0
        session.started_at = None
    session.updated_at = datetime.now()
    db.session.commit()
    repair_session_kicks(session)
    return session, None


def abandon_session(session):
    if session.status != MovementSession.STATUS_IN_PROGRESS:
        return session, 'session_not_active'

    session.status = MovementSession.STATUS_ABANDONED
    session.is_qualified = False
    session.ended_at = datetime.now()
    session.updated_at = datetime.now()
    db.session.commit()
    return session, None


def build_status_payload(session_date=None):
    if session_date is None:
        session_date = date.today()

    qualified = get_qualified_session(session_date)
    if qualified:
        return {
            'qualified_today': True,
            'can_start': False,
            'can_restart': False,
            'session': qualified.to_dict(),
        }

    in_progress = get_in_progress_session(session_date)
    if in_progress:
        finalize_timeout(in_progress)
        in_progress = get_in_progress_session(session_date)
        if in_progress:
            repair_session_kicks(in_progress)
            return {
                'qualified_today': False,
                'can_start': False,
                'can_restart': False,
                'session': in_progress.to_dict(),
            }

    last_session = (
        MovementSession.query.filter_by(session_date=session_date)
        .order_by(MovementSession.id.desc())
        .first()
    )
    display_session = None
    if last_session and last_session.status == MovementSession.STATUS_FAILED:
        display_session = last_session.to_dict()

    return {
        'qualified_today': False,
        'can_start': True,
        'can_restart': (
            last_session is not None
            and last_session.status == MovementSession.STATUS_FAILED
        ),
        'session': display_session,
    }
