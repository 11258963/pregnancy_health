from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date, timedelta
from app import db
from app.models import WeightRecord, CheckupRecord
from sqlalchemy import desc, or_

bp = Blueprint('diary', __name__, url_prefix='/diary')


@bp.route('/')
def index():
    """健康日记首页 - 按日期分组展示所有记录"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if year and month:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
    else:
        today = date.today()
        start_date = date(today.year, today.month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)

    # 获取该时间段的所有记录
    weight_records = WeightRecord.query.filter(
        WeightRecord.record_date >= start_date,
        WeightRecord.record_date < end_date
    ).order_by(WeightRecord.record_date).all()

    checkup_records = CheckupRecord.query.filter(
        CheckupRecord.checkup_date >= start_date,
        CheckupRecord.checkup_date < end_date
    ).order_by(CheckupRecord.checkup_date).all()

    # 按日期分组
    records_by_date = {}
    for r in weight_records:
        d = r.record_date.isoformat()
        if d not in records_by_date:
            records_by_date[d] = {'date': r.record_date, 'weight': None, 'checkup': None}
        records_by_date[d]['weight'] = r

    for r in checkup_records:
        d = r.checkup_date.isoformat()
        if d not in records_by_date:
            records_by_date[d] = {'date': r.checkup_date, 'weight': None, 'checkup': None}
        records_by_date[d]['checkup'] = r

    # 排序
    sorted_dates = sorted(records_by_date.keys(), reverse=True)

    current_month = start_date
    current_month_str = start_date.strftime('%Y年%m月')

    # 上一个月
    if start_date.month == 1:
        prev_year = start_date.year - 1
        prev_month = 12
    else:
        prev_year = start_date.year
        prev_month = start_date.month - 1

    # 下一个月
    if start_date.month == 12:
        next_year = start_date.year + 1
        next_month = 1
    else:
        next_year = start_date.year
        next_month = start_date.month + 1

    # 日历数据 - 使用monthdayscalendar正确处理每周起始日
    import calendar
    cal = calendar.Calendar(firstweekday=0)  # 周一开始
    month_days_raw = cal.monthdayscalendar(start_date.year, start_date.month)
    # 展平为单数组
    month_days = []
    for week in month_days_raw:
        for day in week:
            month_days.append(day)

    return render_template(
        'diary/index.html',
        current_month=current_month,
        current_month_str=current_month_str,
        year=start_date.year,
        month=start_date.month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        records_by_date=records_by_date,
        sorted_dates=sorted_dates,
        month_days=month_days,
        today=date.today()
    )


@bp.route('/date/<record_date>')
def date_detail(record_date):
    """查看特定日期的详细记录"""
    try:
        target_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        flash('日期格式不正确', 'error')
        return redirect(url_for('diary.index'))

    weight = WeightRecord.query.filter_by(record_date=target_date).first()
    checkup = CheckupRecord.query.filter_by(checkup_date=target_date).first()

    return render_template(
        'diary/date_detail.html',
        target_date=target_date,
        weight=weight,
        checkup=checkup,
        today=date.today()
    )
