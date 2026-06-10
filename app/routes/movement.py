from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app import db
from app.models import MovementSession, Settings
from app.utils.movement import (
    TARGET_KICKS,
    SESSION_LIMIT_SECONDS,
    abandon_session,
    add_kick,
    build_day_summaries,
    build_kick_rows,
    build_status_payload,
    can_start_new_session,
    ensure_api_token,
    finalize_timeout,
    format_duration,
    get_in_progress_session,
    get_or_create_in_progress_session,
    get_movement_neighbor_dates,
    get_qualified_session,
    get_gestational_week_for_date,
    repair_session_kicks,
    undo_last_kick,
    verify_api_token,
)

bp = Blueprint('movement', __name__, url_prefix='/movement')


def _require_api_auth():
    token = request.headers.get('X-API-Token') or request.args.get('token')
    if not token:
        return True
    return verify_api_token(token)


@bp.route('/')
def count_page():
    today = date.today()
    status = build_status_payload(today)
    return render_template('movement/count.html', status=status, target_kicks=TARGET_KICKS)


@bp.route('/list')
def list_page():
    sessions = MovementSession.query.order_by(
        MovementSession.session_date.desc(),
        MovementSession.created_at.desc(),
    ).all()

    for session in sessions:
        finalize_timeout(session)

    day_summaries = build_day_summaries(sessions)

    today = date.today()
    if day_summaries:
        latest_date = day_summaries[0]['date']
        filter_month = latest_date.month
        filter_day = latest_date.day
    else:
        filter_month = today.month
        filter_day = today.day

    return render_template(
        'movement/list.html',
        day_summaries=day_summaries,
        format_duration=format_duration,
        filter_year=today.year,
        filter_month=filter_month,
        filter_day=filter_day,
    )


@bp.route('/list/<record_date>')
def list_day_detail(record_date):
    try:
        target_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        flash('日期格式不正确', 'error')
        return redirect(url_for('movement.list_page'))

    sessions = MovementSession.query.filter_by(
        session_date=target_date,
    ).order_by(MovementSession.created_at).all()

    for session in sessions:
        finalize_timeout(session)

    session_details = []
    for index, session in enumerate(sessions, start=1):
        session_details.append({
            'index': index,
            'session': session,
            'kick_rows': build_kick_rows(session),
        })

    prev_date, next_date = get_movement_neighbor_dates(target_date)
    gestational_week, gestational_day = get_gestational_week_for_date(target_date)
    if gestational_week is None:
        gestational_week, gestational_day = 0, 0

    return render_template(
        'movement/day_detail.html',
        target_date=target_date,
        session_details=session_details,
        format_duration=format_duration,
        target_kicks=TARGET_KICKS,
        prev_date=prev_date,
        next_date=next_date,
        gestational_week=gestational_week,
        gestational_day=gestational_day,
        has_records=bool(sessions),
    )


@bp.route('/chart')
def chart_page():
    sessions = MovementSession.query.filter(
        MovementSession.started_at.isnot(None),
    ).order_by(MovementSession.session_date).all()

    for session in sessions:
        finalize_timeout(session)

    duration_labels = []
    duration_values = []
    duration_colors = []
    duration_meta = []

    for session in sessions:
        if session.duration_seconds() is None:
            continue
        label = session.session_date.strftime('%m/%d')
        if session.status != MovementSession.STATUS_COMPLETED or not session.is_qualified:
            attempt_index = MovementSession.query.filter(
                MovementSession.session_date == session.session_date,
                MovementSession.id <= session.id,
            ).count()
            if attempt_index > 1:
                label += f' #{attempt_index}'
        duration_labels.append(label)
        duration_values.append(round(session.duration_seconds() / 60, 1))
        duration_colors.append('#5bb5a0' if session.is_qualified else '#e57373')
        duration_meta.append({
            'start': session.started_at.strftime('%H:%M') if session.started_at else '',
            'end': session.ended_at.strftime('%H:%M') if session.ended_at else '',
            'qualified': session.is_qualified,
            'count': session.kick_count,
        })

    calendar_days = []
    start_day = date.today() - timedelta(days=29)
    for i in range(30):
        day = start_day + timedelta(days=i)
        day_sessions = MovementSession.query.filter_by(session_date=day).all()
        qualified = any(s.is_qualified for s in day_sessions)
        has_failed = any(
            s.status in (MovementSession.STATUS_FAILED, MovementSession.STATUS_ABANDONED)
            for s in day_sessions
        )
        has_in_progress = any(s.status == MovementSession.STATUS_IN_PROGRESS for s in day_sessions)
        if qualified:
            state = 'qualified'
        elif has_failed or has_in_progress:
            state = 'unqualified'
        else:
            state = 'none'
        calendar_days.append({
            'date': day.isoformat(),
            'label': day.strftime('%d'),
            'state': state,
        })

    week_map = {}
    for session in sessions:
        if not session.is_qualified:
            continue
        key = session.gestational_week
        week_map.setdefault(key, []).append(session.duration_seconds() / 60)

    week_labels = sorted(week_map.keys())
    week_values = [
        round(sum(week_map[w]) / len(week_map[w]), 1) if week_map[w] else 0
        for w in week_labels
    ]

    return render_template(
        'movement/chart.html',
        duration_labels=duration_labels,
        duration_values=duration_values,
        duration_colors=duration_colors,
        duration_meta=duration_meta,
        calendar_days=calendar_days,
        week_labels=week_labels,
        week_values=week_values,
    )


@bp.route('/api/status')
def api_status():
    session_date_str = request.args.get('date')
    if session_date_str:
        session_date = datetime.strptime(session_date_str, '%Y-%m-%d').date()
    else:
        session_date = date.today()
    return jsonify(build_status_payload(session_date))


@bp.route('/api/kick', methods=['POST'])
def api_kick():
    if not _require_api_auth():
        return jsonify({'error': 'invalid_token'}), 401

    session_date = date.today()
    qualified = get_qualified_session(session_date)
    if qualified:
        return jsonify({'error': 'already_qualified_today', 'session': qualified.to_dict()}), 409

    in_progress = get_in_progress_session(session_date)
    if in_progress:
        session = in_progress
    elif can_start_new_session(session_date):
        session, _ = get_or_create_in_progress_session(session_date)
    else:
        return jsonify({'error': 'cannot_start'}), 409

    session = MovementSession.query.filter_by(id=session.id).with_for_update().first()
    session, error = add_kick(session)
    if error:
        return jsonify({'error': error, 'session': session.to_dict()}), 400

    status = build_status_payload(session_date)
    return jsonify({'session': session.to_dict(), **status})


@bp.route('/api/undo', methods=['POST'])
def api_undo():
    if not _require_api_auth():
        return jsonify({'error': 'invalid_token'}), 401

    session = get_in_progress_session(date.today())
    if not session:
        return jsonify({'error': 'no_active_session'}), 404

    session, error = undo_last_kick(session)
    if error:
        return jsonify({'error': error, 'session': session.to_dict()}), 400

    return jsonify({'session': session.to_dict(), **build_status_payload(date.today())})


@bp.route('/api/abandon', methods=['POST'])
def api_abandon():
    if not _require_api_auth():
        return jsonify({'error': 'invalid_token'}), 401

    session = get_in_progress_session(date.today())
    if not session:
        return jsonify({'error': 'no_active_session'}), 404

    session, error = abandon_session(session)
    if error:
        return jsonify({'error': error}), 400

    return jsonify({'session': session.to_dict(), **build_status_payload(date.today())})


@bp.route('/api/settings')
def api_settings():
    settings = Settings.query.first()
    if not settings:
        return jsonify({'reminder_enabled': True, 'reminder_hour': 19})
    return jsonify({
        'reminder_enabled': settings.movement_reminder_enabled if settings.movement_reminder_enabled is not None else True,
        'reminder_hour': 19,
        'target_kicks': TARGET_KICKS,
        'session_limit_seconds': SESSION_LIMIT_SECONDS,
    })
