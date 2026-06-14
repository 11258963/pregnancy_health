from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from app import db
from app.models import MovementSession, Settings, UltrasoundRecord
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


def _optional_float(value):
    if value is None or str(value).strip() == '':
        return None
    return float(value)


def _optional_int(value):
    if value is None or str(value).strip() == '':
        return None
    return int(float(value))


def _parse_flexible_record_date(value):
    import re

    raw = (value or '').strip()
    if not raw:
        raise ValueError('请填写日期')

    normalized = raw.replace('/', '-').replace('.', '-')

    if re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2}', normalized):
        year, month, day = normalized.split('-')
        return date(int(year), int(month), int(day))

    digits = re.sub(r'\D', '', raw)
    if re.fullmatch(r'\d{8}', digits):
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))

    if re.fullmatch(r'\d{1,2}-\d{1,2}', normalized):
        month, day = normalized.split('-')
        return date(date.today().year, int(month), int(day))

    if re.fullmatch(r'\d{4}', raw):
        return date(date.today().year, int(raw[:2]), int(raw[2:]))

    raise ValueError('日期格式不正确，可用 2026-6-10、20260610 或 0610')


def _populate_ultrasound_from_form(record):
    record_date_str = request.form.get('record_date')
    record.record_date = _parse_flexible_record_date(record_date_str)
    if record.record_date > date.today():
        raise ValueError('日期不能晚于今天')
    gestational_week, gestational_day = get_gestational_week_for_date(record.record_date)
    if gestational_week is None:
        raise ValueError('请先在设置中配置预产期')
    record.gestational_week = gestational_week
    record.gestational_day = gestational_day or 0
    record.bpd = _optional_float(request.form.get('bpd'))
    record.hr = _optional_int(request.form.get('hr'))
    record.hc = _optional_float(request.form.get('hc'))
    record.ac = _optional_float(request.form.get('ac'))
    record.fl = _optional_float(request.form.get('fl'))
    record.estimated_weight = _optional_float(request.form.get('estimated_weight'))
    age = (request.form.get('estimated_gestational_age') or '').strip()
    record.estimated_gestational_age = age or None
    return record


def _build_extras_chart_data(records):
    ordered = sorted(records, key=lambda r: (r.record_date, r.id))
    return {
        'labels': [r.record_date.strftime('%m-%d') for r in ordered],
        'weeks': [f'{r.gestational_week}周{r.gestational_day}天' for r in ordered],
        'bpd': [r.bpd for r in ordered],
        'hc': [r.hc for r in ordered],
        'ac': [r.ac for r in ordered],
        'fl': [r.fl for r in ordered],
        'weight': [r.estimated_weight for r in ordered],
    }


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


@bp.route('/extras', methods=['GET', 'POST'])
def more_records_page():
    if request.method == 'POST':
        record = UltrasoundRecord()
        try:
            _populate_ultrasound_from_form(record)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('movement.more_records_page'))

        db.session.add(record)
        db.session.commit()
        flash('记录已保存', 'success')
        return redirect(url_for('movement.more_records_page'))

    sort = request.args.get('sort')
    if sort in ('asc', 'desc'):
        session['movement_extras_sort'] = sort
    else:
        sort = session.get('movement_extras_sort', 'asc')

    order = (
        (UltrasoundRecord.record_date.desc(), UltrasoundRecord.id.desc())
        if sort == 'desc'
        else (UltrasoundRecord.record_date.asc(), UltrasoundRecord.id.asc())
    )
    records = UltrasoundRecord.query.order_by(*order).all()
    today = date.today()
    return render_template(
        'movement/more_records.html',
        records=records,
        today=today,
        date_sort=sort,
        chart_data=_build_extras_chart_data(records),
    )


@bp.route('/extras/<int:record_id>/edit', methods=['GET', 'POST'])
def more_records_edit(record_id):
    record = UltrasoundRecord.query.get_or_404(record_id)
    if request.method == 'POST':
        try:
            _populate_ultrasound_from_form(record)
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('movement.more_records_edit', record_id=record_id))

        db.session.commit()
        flash('记录已更新', 'success')
        return redirect(url_for('movement.more_records_page'))

    return render_template('movement/more_records_edit.html', record=record, today=date.today())


@bp.route('/extras/<int:record_id>/delete', methods=['POST'])
def more_records_delete(record_id):
    record = UltrasoundRecord.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    flash('记录已删除', 'success')
    return redirect(url_for('movement.more_records_page'))


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
