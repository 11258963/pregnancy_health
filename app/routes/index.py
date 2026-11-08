from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime, date, timedelta
from app import db
from app.models import Settings, WeightRecord, CheckupRecord
from app.utils.movement import TARGET_KICKS, build_status_payload
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
    birth_date = settings.birth_date
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

    # 今日动作记录
    movement_status = build_status_payload(today)
    if year and month:
        current_month = date(year, month, 1)
    elif birth_date:
        current_month = date(birth_date.year, birth_date.month, 1)
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
            if birth_date and day_date > birth_date:
                prev_gw = None
                continue
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
        movement_status=movement_status,
        movement_target_kicks=TARGET_KICKS,
        current_month=current_month,
        current_month_str=current_month_str,
        month_days=month_days,
        all_record_dates=all_record_dates,
        checkup_dates=checkup_dates,
        prev_month=prev_month,
        next_month=next_month,
        today=today,
        gestational_weeks_by_day=gestational_weeks_by_day,
        first_day_of_week=first_day_of_week,
        birth_date=birth_date
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

        birth_date_str = request.form.get('birth_date')
        birth_date_val = None
        if birth_date_str:
            try:
                birth_date_val = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if settings:
            settings.due_date = due_date
            settings.birth_date = birth_date_val
        else:
            settings = Settings(due_date=due_date, birth_date=birth_date_val)
            db.session.add(settings)

        db.session.commit()
        flash('设置已更新', 'success')
        return redirect(url_for('index.index'))

    from app.utils.movement import ensure_api_token
    api_token = ensure_api_token(settings) if settings else None
    kick_api_url = None
    if api_token:
        kick_api_url = url_for('movement.api_kick', token=api_token, _external=True)

    return render_template(
        'settings.html',
        settings=settings,
        kick_api_url=kick_api_url,
    )


@bp.route('/settings/reset-cycle', methods=['POST'])
def reset_cycle():
    """归档当前周期数据并在底层新建归档文件夹，然后清空网站活跃数据开始新周期"""
    import shutil
    from app.models import CheckupFile, MovementSession, MovementKick, UltrasoundRecord, FetalRecord

    settings = Settings.query.first()
    due_date_str = settings.due_date.strftime('%Y%m%d') if (settings and settings.due_date) else 'unknown'
    archive_date_str = datetime.now().strftime('%Y%m%d')
    base_folder_name = f"{due_date_str}at{archive_date_str}"

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')

    # 确定底层 data 目录
    if upload_folder and os.path.exists(upload_folder):
        data_dir = os.path.dirname(os.path.abspath(upload_folder))
    elif db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        data_dir = os.path.dirname(os.path.abspath(db_path))
    else:
        data_dir = os.path.join(os.getcwd(), 'data')

    archives_dir = os.path.join(data_dir, 'archive')
    archive_folder_name = base_folder_name
    target_archive_path = os.path.join(archives_dir, archive_folder_name)
    if os.path.exists(target_archive_path):
        archive_folder_name = f"{base_folder_name}_{datetime.now().strftime('%H%M%S')}"
        target_archive_path = os.path.join(archives_dir, archive_folder_name)

    os.makedirs(target_archive_path, exist_ok=True)

    # 1. 复制当前 SQLite 数据库文件至归档目录
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        if os.path.exists(db_path):
            shutil.copy2(db_path, os.path.join(target_archive_path, 'pregnancy.db'))

    # 2. 复制当前上传附件至归档目录，并清空活跃上传目录中的内容
    if upload_folder and os.path.exists(upload_folder):
        target_uploads_archive = os.path.join(target_archive_path, 'uploads')
        shutil.copytree(upload_folder, target_uploads_archive, dirs_exist_ok=True)
        for item in os.listdir(upload_folder):
            item_path = os.path.join(upload_folder, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            elif not item.startswith('.'):
                try:
                    os.remove(item_path)
                except Exception:
                    pass

    # 3. 清空活跃数据库中的所有表记录
    try:
        db.session.query(MovementKick).delete()
        db.session.query(MovementSession).delete()
        db.session.query(CheckupFile).delete()
        db.session.query(CheckupRecord).delete()
        db.session.query(UltrasoundRecord).delete()
        db.session.query(WeightRecord).delete()
        db.session.query(FetalRecord).delete()
        db.session.query(Settings).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'归档清空数据库时出错: {str(e)}', 'error')
        return redirect(url_for('index.settings_page'))

    current_app.config['DUE_DATE'] = None

    flash(f'当前周期已安全归档至底层独立文件夹 archive/{archive_folder_name}/，网站数据已清零！请设置新预产期。', 'success')
    return redirect(url_for('index.setup'))
