from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, date, timedelta
from app import db
from app.models import Settings, WeightRecord, CheckupRecord
from sqlalchemy import desc
import calendar

bp = Blueprint('index', __name__)


def calculate_gestational_week(due_date, current_date=None):
    """根据预产期计算当前孕周"""
    if current_date is None:
        current_date = date.today()

    days_until_due = (due_date - current_date).days
    gestational_days = 280 - days_until_due

    if gestational_days < 0:
        return None, None

    weeks = gestational_days // 7
    days = gestational_days % 7
    return weeks, days


@bp.route('/')
@bp.route('/<int:year>/<int:month>')
def index(year=None, month=None):
    settings = Settings.query.first()

    if not settings or not settings.due_date:
        return redirect(url_for('index.setup'))

    due_date = settings.due_date
    gestational_week, gestational_day = calculate_gestational_week(due_date)

    if gestational_week is None:
        gestational_week = 40
        gestational_day = 0

    # 最新体重
    latest_weight = WeightRecord.query.order_by(desc(WeightRecord.record_date)).first()

    # 一周前体重对比
    week_ago = date.today()
    week_ago_weight = WeightRecord.query.filter(
        WeightRecord.record_date <= week_ago
    ).order_by(desc(WeightRecord.record_date)).first()

    # 最近产检
    recent_checkups = CheckupRecord.query.order_by(
        desc(CheckupRecord.checkup_date)
    ).limit(3).all()

    # 当前月的日历数据
    today = date.today()
    if year and month:
        current_month = date(year, month, 1)
    else:
        current_month = today

    start_date = date(current_month.year, current_month.month, 1)
    if current_month.month == 12:
        end_date = date(current_month.year + 1, 1, 1)
    else:
        end_date = date(current_month.year, current_month.month + 1, 1)

    # 获取当月有记录的日期
    weight_dates = {r.record_date.isoformat() for r in WeightRecord.query.filter(
        WeightRecord.record_date >= start_date, WeightRecord.record_date < end_date).all()}

    checkup_dates = {r.checkup_date.isoformat() for r in CheckupRecord.query.filter(
        CheckupRecord.checkup_date >= start_date, CheckupRecord.checkup_date < end_date).all()}

    all_record_dates = weight_dates | checkup_dates

    # 计算当月每天的孕周
    gestational_weeks_by_day = {}
    first_day_of_week = set()  # 存储每个孕周的第一天
    prev_gw = None
    for day in range(1, 32):
        try:
            day_date = date(current_month.year, current_month.month, day)
            gw, gd = calculate_gestational_week(due_date, day_date)
            if gw is not None:
                gestational_weeks_by_day[day] = gw
                if gw != prev_gw:
                    first_day_of_week.add(day)
                prev_gw = gw
        except ValueError:
            break

    # 日历 - 从周日开始
    cal = calendar.Calendar(firstweekday=0)
    month_days = list(cal.itermonthdays(current_month.year, current_month.month))
    current_month_str = current_month.strftime('%Y年%m月')

    # 上/下个月
    prev_month = date(current_month.year, current_month.month - 1, 1) if current_month.month > 1 else date(current_month.year - 1, 12, 1)
    next_month = date(current_month.year, current_month.month + 1, 1) if current_month.month < 12 else date(current_month.year + 1, 1, 1)

    return render_template(
        'index.html',
        gestational_week=gestational_week,
        gestational_day=gestational_day,
        due_date=due_date,
        latest_weight=latest_weight,
        recent_checkups=recent_checkups,
        current_month=current_month,
        current_month_str=current_month_str,
        month_days=month_days,
        all_record_dates=all_record_dates,
        checkup_dates=checkup_dates,
        prev_month=prev_month,
        next_month=next_month,
        today=today,
        gestational_weeks_by_day=gestational_weeks_by_day,
        first_day_of_week=first_day_of_week
    )


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """首次设置预产期"""
    settings = Settings.query.first()

    if request.method == 'POST':
        due_date_str = request.form.get('due_date')

        if not due_date_str:
            flash('请输入预产期', 'error')
            return redirect(url_for('index.setup'))

        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('日期格式不正确', 'error')
            return redirect(url_for('index.setup'))

        if settings:
            settings.due_date = due_date
        else:
            settings = Settings(due_date=due_date)
            db.session.add(settings)

        db.session.commit()
        flash('预产期设置成功！', 'success')
        return redirect(url_for('index.index'))

    return render_template('setup.html')


@bp.route('/settings', methods=['GET', 'POST'])
def settings_page():
    """设置页面"""
    settings = Settings.query.first()

    if request.method == 'POST':
        due_date_str = request.form.get('due_date')

        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('日期格式不正确', 'error')
            return redirect(url_for('index.settings_page'))

        if settings:
            settings.due_date = due_date
        else:
            settings = Settings(due_date=due_date)
            db.session.add(settings)

        db.session.commit()
        flash('设置已更新', 'success')
        return redirect(url_for('index.index'))

    return render_template('settings.html', settings=settings)
