from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, date, time
from app import db
from app.models import WeightRecord, Settings
from sqlalchemy import desc

bp = Blueprint('weight', __name__, url_prefix='/weight')


def calculate_gestational_week(due_date, current_date=None):
    if current_date is None:
        current_date = date.today()
    days_until_due = (due_date - current_date).days
    gestational_days = 280 - days_until_due
    if gestational_days < 0:
        return None, None
    weeks = gestational_days // 7
    days = gestational_days % 7
    return weeks, days


def get_gestational_week_for_date(record_date):
    settings = Settings.query.first()
    if not settings or not settings.due_date:
        return None, None
    return calculate_gestational_week(settings.due_date, record_date)


def get_baseline_weight():
    """获取孕前体重（最早的体重记录）"""
    earliest = WeightRecord.query.order_by(WeightRecord.record_date).first()
    if earliest:
        return earliest.weight
    return None


def calculate_suggested_weight(baseline_weight, gestational_week):
    """计算建议体重范围（美柚公式）
    - 孕0-13周：下限=孕前体重，上限=孕前体重+周数*0.143
    - 孕14周起：下限=孕前体重+(孕周-14)*0.285，上限=孕前体重+2.0+(孕周-14)*0.43
    """
    if baseline_weight is None or gestational_week is None:
        return None, None

    if gestational_week <= 13:
        upper = baseline_weight + gestational_week * 0.143
        return baseline_weight, round(upper, 2)
    else:
        min_gain = (gestational_week - 14) * 0.285
        max_gain = 2.0 + (gestational_week - 14) * 0.43
        return baseline_weight + min_gain, baseline_weight + max_gain


@bp.route('/')
def list():
    return redirect(url_for('weight.chart'))


@bp.route('/list')
def list_view():
    records = WeightRecord.query.order_by(desc(WeightRecord.record_date)).all()
    sync_data = request.args.get('sync_data', '')
    return render_template('weight/list.html', records=records, sync_data=sync_data)


@bp.route('/latest_json')
def latest_json():
    """返回最新体重记录的JSON格式，用于Apple Health同步"""
    record = WeightRecord.query.order_by(desc(WeightRecord.record_date)).first()
    if not record:
        return jsonify({'error': '暂无体重记录'})

    return jsonify({
        'date': record.record_date.isoformat(),
        'time': record.record_time.strftime('%H:%M') if record.record_time else '08:00',
        'weight': record.weight,
        'gestational_week': record.gestational_week,
        'gestational_day': record.gestational_day
    })


@bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        record_date_str = request.form.get('record_date')
        record_time_str = request.form.get('record_time')
        weight_val = request.form.get('weight')

        if not record_date_str or not weight_val:
            flash('请填写日期和体重', 'error')
            return redirect(url_for('weight.add'))

        try:
            record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
            record_time = datetime.strptime(record_time_str, '%H:%M').time() if record_time_str else None
            weight = float(weight_val)
        except ValueError:
            flash('数据格式不正确', 'error')
            return redirect(url_for('weight.add'))

        # 检查是否已存在相同的日期、时间和体重记录
        existing = WeightRecord.query.filter_by(
            record_date=record_date,
            record_time=record_time,
            weight=weight
        ).first()

        if existing:
            flash('相同的日期、时间和体重记录已存在，无需重复添加', 'warning')
            return redirect(url_for('weight.list'))

        gestational_week, gestational_day = get_gestational_week_for_date(record_date)
        if gestational_week is None:
            flash('请先设置预产期', 'error')
            return redirect(url_for('index.setup'))

        # 计算建议体重
        baseline = get_baseline_weight()
        if baseline is None:
            baseline = weight  # 第一条记录作为孕前体重
        suggested_min, suggested_max = calculate_suggested_weight(baseline, gestational_week)

        record = WeightRecord(
            record_date=record_date,
            record_time=record_time,
            gestational_week=gestational_week,
            gestational_day=gestational_day or 0,
            weight=weight,
            suggested_min=round(suggested_min, 1) if suggested_min else None,
            suggested_max=round(suggested_max, 1) if suggested_max else None
        )
        db.session.add(record)
        db.session.commit()

        flash('体重记录已添加', 'success')
        # 准备同步到 Apple Health 的数据
        sync_data = f"{record.record_date.isoformat()} {record.record_time.strftime('%H:%M') if record.record_time else '08:00'} {record.weight}kg"
        return redirect(url_for('weight.list_view', sync_data=sync_data))

    return render_template('weight/add.html', record_date=date.today().isoformat(), today=date.today().isoformat(), current_time=datetime.now().strftime('%H:%M'))


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    record = WeightRecord.query.get_or_404(id)

    if request.method == 'POST':
        record_date_str = request.form.get('record_date')
        record_hour = request.form.get('record_hour')
        record_minute = request.form.get('record_minute')
        weight_val = request.form.get('weight')

        try:
            record.record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
            if record_hour and record_minute:
                record.record_time = time(int(record_hour), int(record_minute))
            else:
                record.record_time = None
            record.weight = float(weight_val)

            # 重新计算孕周和建议体重
            gestational_week, gestational_day = get_gestational_week_for_date(record.record_date)
            if gestational_week is not None:
                record.gestational_week = gestational_week
                record.gestational_day = gestational_day or 0
                baseline = get_baseline_weight()
                if baseline is None:
                    baseline = record.weight
                suggested_min, suggested_max = calculate_suggested_weight(baseline, gestational_week)
                record.suggested_min = round(suggested_min, 1) if suggested_min else None
                record.suggested_max = round(suggested_max, 1) if suggested_max else None
        except ValueError:
            flash('数据格式不正确', 'error')
            return redirect(url_for('weight.edit', id=id))

        db.session.commit()
        flash('体重记录已更新', 'success')
        return redirect(url_for('weight.list'))

    return render_template('weight/edit.html', record=record)


@bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    record = WeightRecord.query.get_or_404(id)
    db.session.delete(record)
    db.session.commit()
    flash('体重记录已删除', 'success')
    return redirect(url_for('weight.list'))


@bp.route('/chart')
def chart():
    records = WeightRecord.query.order_by(WeightRecord.record_date).all()

    data = {
        'labels': [r.record_date.isoformat() for r in records],
        'weeks': [f"{r.gestational_week}周{r.gestational_day}天" for r in records],
        'weights': [r.weight for r in records],
        'suggested_min': [r.suggested_min for r in records],
        'suggested_max': [r.suggested_max for r in records],
        'dates': [r.record_date.strftime('%m/%d') for r in records]
    }

    return render_template('weight/chart.html', data=data, chart_title='体重曲线-有记录')


@bp.route('/chart/by_date')
def chart_by_date():
    records = WeightRecord.query.order_by(WeightRecord.record_date).all()

    if not records:
        data = {'labels': [], 'weeks': [], 'weights': [], 'suggested_min': [], 'suggested_max': [], 'dates': []}
        return render_template('weight/chart.html', data=data, chart_title='体重曲线-日')

    # 生成从第一条记录到最后一条记录的所有日期
    from datetime import timedelta
    start_date = records[0].record_date
    end_date = records[-1].record_date

    # 创建日期到记录的映射
    record_map = {r.record_date: r for r in records}

    all_dates = []
    all_labels = []
    all_weeks = []
    all_weights = []
    all_suggested_min = []
    all_suggested_max = []
    all_has_record = []

    current = start_date
    while current <= end_date:
        all_dates.append(current.strftime('%Y-%m-%d'))

        if current in record_map:
            r = record_map[current]
            all_weights.append(r.weight)
            all_suggested_min.append(r.suggested_min)
            all_suggested_max.append(r.suggested_max)
            all_weeks.append(f"{r.gestational_week}周{r.gestational_day}天")
            all_has_record.append(True)
        else:
            # 无记录的日期，体重为 null，但建议范围仍需计算
            all_weights.append(None)
            all_suggested_min.append(None)
            all_suggested_max.append(None)
            all_weeks.append(None)
            all_has_record.append(False)

        current += timedelta(days=1)

    data = {
        'labels': all_dates,
        'weeks': all_weeks,
        'weights': all_weights,
        'suggested_min': all_suggested_min,
        'suggested_max': all_suggested_max,
        'dates': all_dates,
        'has_record': all_has_record
    }

    return render_template('weight/chart.html', data=data, chart_title='体重曲线-日')


@bp.route('/chart/by_week')
def chart_by_week():
    records = WeightRecord.query.order_by(WeightRecord.record_date).all()

    if not records:
        data = {'labels': [], 'weights': [], 'suggested_min': [], 'suggested_max': []}
        return render_template('weight/chart.html', data=data, chart_title='体重曲线-孕周')

    # 按孕周分组计算平均体重
    week_data = {}
    for r in records:
        gw = r.gestational_week
        if gw not in week_data:
            week_data[gw] = {'weights': [], 'suggested_min': r.suggested_min, 'suggested_max': r.suggested_max}
        week_data[gw]['weights'].append(r.weight)

    # 获取所有孕周并排序
    all_weeks = sorted(week_data.keys())
    week_labels = [f"孕{w}周" for w in all_weeks]
    week_avg_weights = [sum(week_data[w]['weights']) / len(week_data[w]['weights']) for w in all_weeks]
    week_suggested_min = [week_data[w]['suggested_min'] for w in all_weeks]
    week_suggested_max = [week_data[w]['suggested_max'] for w in all_weeks]

    data = {
        'labels': week_labels,
        'weights': week_avg_weights,
        'suggested_min': week_suggested_min,
        'suggested_max': week_suggested_max
    }

    return render_template('weight/chart.html', data=data, chart_title='体重曲线-孕周')
