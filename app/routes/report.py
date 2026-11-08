import io
import os
import zipfile
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, send_file, current_app, redirect, url_for, flash
from app import db
from app.models import Settings, WeightRecord, CheckupRecord, CheckupFile, UltrasoundRecord, MovementSession
from app.utils.movement import format_duration, TARGET_KICKS
from sqlalchemy import asc

bp = Blueprint('report', __name__, url_prefix='/report')


@bp.route('/')
def index():
    settings = Settings.query.first()
    if not settings or not settings.due_date:
        flash('请先设置预产期', 'warning')
        return redirect(url_for('index.setup'))

    due_date = settings.due_date
    birth_date = settings.birth_date

    # 计算孕期起始日期（预产期倒推 280 天）与总天数
    conception_start_date = due_date - timedelta(days=280)
    total_pregnancy_days = None
    actual_gestation_str = "未填写生产日期"
    if birth_date:
        total_pregnancy_days = (birth_date - conception_start_date).days
        total_weeks = total_pregnancy_days // 7
        total_days = total_pregnancy_days % 7
        actual_gestation_str = f"{total_weeks}周{total_days}天"

    # 体重数据 (按日期正序)
    weights = WeightRecord.query.order_by(asc(WeightRecord.record_date)).all()
    initial_weight = weights[0].weight if weights else None
    final_weight = weights[-1].weight if weights else None
    total_weight_gain = round(final_weight - initial_weight, 2) if (initial_weight and final_weight) else None

    # 产检记录 (按日期正序)
    checkups = CheckupRecord.query.order_by(asc(CheckupRecord.checkup_date)).all()

    # 统计附件总数与总大小
    total_files_count = 0
    total_files_size = 0
    for c in checkups:
        c_files = c.files.all()
        total_files_count += len(c_files)
        total_files_size += sum((f.file_size or 0) for f in c_files)

    # 超声记录 (按日期正序)
    ultrasounds = UltrasoundRecord.query.order_by(asc(UltrasoundRecord.record_date)).all()

    # 胎动数据汇总 (按日期正序)
    sessions = MovementSession.query.order_by(asc(MovementSession.session_date), asc(MovementSession.id)).all()

    # 按天汇总胎动
    days_map = {}
    for s in sessions:
        d = s.session_date
        if d not in days_map:
            days_map[d] = []
        days_map[d].append(s)

    movement_day_summaries = []
    qualified_days_count = 0
    valid_durations = []

    for d in sorted(days_map.keys()):
        day_sessions = days_map[d]
        # 优先取达标会话，否则取有点击的，或最后一条
        best = next((s for s in day_sessions if s.is_qualified), None)
        if not best:
            with_kicks = [s for s in day_sessions if s.kick_count > 0]
            best = with_kicks[-1] if with_kicks else day_sessions[-1]

        dur = best.duration_seconds()
        is_qual = any(s.is_qualified for s in day_sessions)
        if is_qual:
            qualified_days_count += 1
            if dur and dur > 0:
                valid_durations.append(dur)

        total_kicks = sum(s.kick_count for s in day_sessions)
        movement_day_summaries.append({
            'date': d,
            'gestational_week': best.gestational_week,
            'gestational_day': best.gestational_day,
            'total_kicks': total_kicks,
            'best_kicks': best.kick_count,
            'duration_formatted': format_duration(dur),
            'duration_seconds': dur,
            'is_qualified': is_qual,
            'status': best.status,
            'sessions_count': len(day_sessions)
        })

    avg_duration_str = format_duration(sum(valid_durations) / len(valid_durations)) if valid_durations else '—'
    movement_stats = {
        'total_sessions': len(sessions),
        'recorded_days': len(days_map),
        'qualified_days': qualified_days_count,
        'qualified_rate': f"{round(qualified_days_count / len(days_map) * 100, 1)}%" if days_map else '0%',
        'avg_qualified_duration': avg_duration_str,
        'target_kicks': TARGET_KICKS
    }

    # 上传目录绝对路径
    uploads_dir = os.path.abspath(current_app.config.get('UPLOAD_FOLDER', 'data/uploads'))

    return render_template(
        'report/index.html',
        settings=settings,
        due_date=due_date,
        birth_date=birth_date,
        conception_start_date=conception_start_date,
        total_pregnancy_days=total_pregnancy_days,
        actual_gestation_str=actual_gestation_str,
        weights=weights,
        initial_weight=initial_weight,
        final_weight=final_weight,
        total_weight_gain=total_weight_gain,
        checkups=checkups,
        total_files_count=total_files_count,
        total_files_size=total_files_size,
        ultrasounds=ultrasounds,
        movement_day_summaries=movement_day_summaries,
        movement_stats=movement_stats,
        uploads_dir=uploads_dir,
        now=datetime.now()
    )


@bp.route('/download-attachments-zip')
def download_attachments_zip():
    """打包下载所有产检附件"""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'data/uploads')

    memory_file = io.BytesIO()
    checkup_files = CheckupFile.query.all()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        added_names = set()
        for f in checkup_files:
            rec = f.record
            folder_name = f"第{rec.gestational_week}周_{rec.checkup_date.strftime('%Y%m%d')}_{rec.checkup_item[:15]}"

            # 寻找本地文件路径
            file_path = os.path.join(upload_folder, f'record_{f.checkup_record_id}', f.stored_filename)
            if not os.path.exists(file_path):
                file_path_alt = os.path.join(upload_folder, f.stored_filename)
                if os.path.exists(file_path_alt):
                    file_path = file_path_alt
                else:
                    continue

            arcname = f"{folder_name}/{f.original_filename}"
            # 避免重名覆盖
            suffix = 1
            base_arcname = arcname
            while arcname in added_names:
                name_part, ext = os.path.splitext(base_arcname)
                arcname = f"{name_part}_{suffix}{ext}"
                suffix += 1

            added_names.add(arcname)
            zf.write(file_path, arcname=arcname)

    memory_file.seek(0)
    zip_name = f"产检报告档案_{datetime.now().strftime('%Y%m%d')}.zip"
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_name
    )
