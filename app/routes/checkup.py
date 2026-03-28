from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from datetime import datetime, date
import os
from app import db
from app.models import CheckupRecord, CheckupFile, Settings
from app.utils.file_handler import validate_file, save_file, delete_file as delete_file_handler, delete_all_files_for_record, get_file_path
from sqlalchemy import desc, and_, or_

bp = Blueprint('checkup', __name__, url_prefix='/checkup')


def calculate_gestational_week(due_date, checkup_date):
    days_until_due = (due_date - checkup_date).days
    gestational_days = 280 - days_until_due
    if gestational_days < 0:
        return None, None
    weeks = gestational_days // 7
    days = gestational_days % 7
    return weeks, days


def get_gestational_week_for_date(checkup_date):
    settings = Settings.query.first()
    if not settings or not settings.due_date:
        return None, None
    return calculate_gestational_week(settings.due_date, checkup_date)


@bp.route('/')
def list():
    records = CheckupRecord.query.order_by(desc(CheckupRecord.checkup_date)).all()
    return render_template('checkup/list.html', records=records, items=CheckupRecord.CHECKUP_ITEMS)


@bp.route('/files')
def all_files():
    """展示所有检查附件，按日期和孕周排序"""
    # 查询所有附件及其关联的检查记录
    files = CheckupFile.query.join(CheckupRecord).order_by(desc(CheckupRecord.checkup_date)).all()
    return render_template('checkup/all_files.html', files=files)


@bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        checkup_date_str = request.form.get('checkup_date')
        checkup_items = request.form.getlist('checkup_items')
        doctor_notes = request.form.get('doctor_notes')
        next_appointment_str = request.form.get('next_appointment')

        if not checkup_date_str or not checkup_items:
            flash('请填写日期和检查项目', 'error')
            return redirect(url_for('checkup.add'))

        try:
            checkup_date = datetime.strptime(checkup_date_str, '%Y-%m-%d').date()
            gestational_week, gestational_day = get_gestational_week_for_date(checkup_date)
        except ValueError:
            flash('日期格式不正确', 'error')
            return redirect(url_for('checkup.add'))

        if gestational_week is None:
            flash('请先设置预产期', 'error')
            return redirect(url_for('index.setup'))

        next_appointment = None
        if next_appointment_str:
            try:
                next_appointment = datetime.strptime(next_appointment_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        record = CheckupRecord(
            checkup_date=checkup_date,
            gestational_week=gestational_week,
            gestational_day=gestational_day or 0,
            checkup_item=', '.join(checkup_items),
            checkup_item_code=None,
            doctor_notes=doctor_notes,
            next_appointment=next_appointment
        )
        db.session.add(record)
        db.session.commit()  # Commit first to get record ID

        # Handle file uploads
        files = request.files.getlist('files')
        for file in files:
            if file and file.filename:
                valid, result_msg = validate_file(file)
                if valid:
                    stored_filename, original_filename, file_type, file_size = save_file(file, record.id)
                    file_record = CheckupFile(
                        checkup_record_id=record.id,
                        original_filename=original_filename,
                        stored_filename=stored_filename,
                        file_type=file_type,
                        mime_type=file.content_type,
                        file_size=file_size
                    )
                    db.session.add(file_record)
                else:
                    flash(f'文件 {file.filename} 跳过: {result_msg}', 'warning')

        db.session.commit()

        flash('检查记录已添加', 'success')
        return redirect(url_for('checkup.list'))

    return render_template('checkup/add.html',
                           checkup_date=date.today().isoformat(),
                           today=date.today().isoformat(),
                           items=CheckupRecord.CHECKUP_ITEMS,
                           groups=CheckupRecord.CHECKUP_GROUPS,
                           descriptions=CheckupRecord.CHECKUP_DESCRIPTIONS)


def _checkup_neighbor_newer(record):
    """按检查日期（新→旧）列表中，当前条的「上一篇」：日期更新或同日更晚创建的记录。"""
    return CheckupRecord.query.filter(
        or_(
            CheckupRecord.checkup_date > record.checkup_date,
            and_(CheckupRecord.checkup_date == record.checkup_date, CheckupRecord.id > record.id),
        )
    ).order_by(CheckupRecord.checkup_date.asc(), CheckupRecord.id.asc()).first()


def _checkup_neighbor_older(record):
    """「下一篇」：日期更旧或同日更早的记录。"""
    return CheckupRecord.query.filter(
        or_(
            CheckupRecord.checkup_date < record.checkup_date,
            and_(CheckupRecord.checkup_date == record.checkup_date, CheckupRecord.id < record.id),
        )
    ).order_by(CheckupRecord.checkup_date.desc(), CheckupRecord.id.desc()).first()


@bp.route('/detail/<int:id>')
def detail(id):
    record = CheckupRecord.query.get_or_404(id)
    images = [f for f in record.files if f.file_type == 'image']
    documents = [f for f in record.files if f.file_type == 'document']
    neighbor_newer = _checkup_neighbor_newer(record)
    neighbor_older = _checkup_neighbor_older(record)
    return render_template(
        'checkup/detail.html',
        record=record,
        items=CheckupRecord.CHECKUP_ITEMS,
        descriptions=CheckupRecord.CHECKUP_DESCRIPTIONS,
        images=images,
        documents=documents,
        neighbor_newer=neighbor_newer,
        neighbor_older=neighbor_older,
    )


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    record = CheckupRecord.query.get_or_404(id)

    if request.method == 'POST':
        record.checkup_date = datetime.strptime(request.form.get('checkup_date'), '%Y-%m-%d').date()
        checkup_items = request.form.getlist('checkup_items')
        record.checkup_item = ', '.join(checkup_items) if checkup_items else ''
        record.doctor_notes = request.form.get('doctor_notes')

        next_appointment_str = request.form.get('next_appointment')
        if next_appointment_str:
            record.next_appointment = datetime.strptime(next_appointment_str, '%Y-%m-%d').date()
        else:
            record.next_appointment = None

        # Handle new file uploads
        files = request.files.getlist('files')
        for file in files:
            if file and file.filename:
                valid, result_msg = validate_file(file)
                if valid:
                    stored_filename, original_filename, file_type, file_size = save_file(file, record.id)
                    file_record = CheckupFile(
                        checkup_record_id=record.id,
                        original_filename=original_filename,
                        stored_filename=stored_filename,
                        file_type=file_type,
                        mime_type=file.content_type,
                        file_size=file_size
                    )
                    db.session.add(file_record)
                else:
                    flash(f'文件 {file.filename} 跳过: {result_msg}', 'warning')

        db.session.commit()
        flash('检查记录已更新', 'success')
        return redirect(url_for('checkup.detail', id=id))

    images = [f for f in record.files if f.file_type == 'image']
    documents = [f for f in record.files if f.file_type == 'document']
    return render_template('checkup/edit.html', record=record, items=CheckupRecord.CHECKUP_ITEMS, groups=CheckupRecord.CHECKUP_GROUPS, descriptions=CheckupRecord.CHECKUP_DESCRIPTIONS, images=images, documents=documents)


@bp.route('/file/<int:record_id>/<filename>')
def file(record_id, filename):
    """Serve uploaded files"""
    record = CheckupRecord.query.get_or_404(record_id)
    file_record = CheckupFile.query.filter_by(
        checkup_record_id=record_id,
        stored_filename=filename
    ).first_or_404()

    file_path = get_file_path(filename, record_id)

    if not os.path.exists(file_path):
        flash('文件未找到', 'error')
        return redirect(url_for('checkup.detail', id=record_id))

    return send_file(
        file_path,
        mimetype=file_record.mime_type,
        as_attachment=False,
        download_name=file_record.original_filename
    )


@bp.route('/file/<int:file_id>/delete', methods=['POST'])
def delete_file(file_id):
    """Delete a specific file"""
    file_record = CheckupFile.query.get_or_404(file_id)
    record_id = file_record.checkup_record_id

    # Delete physical file
    delete_file_handler(file_record.stored_filename, record_id)

    # Delete database record
    db.session.delete(file_record)
    db.session.commit()

    flash('文件已删除', 'success')
    return redirect(url_for('checkup.edit', id=record_id))


@bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    record = CheckupRecord.query.get_or_404(id)

    # Delete all associated files from disk
    delete_all_files_for_record(id)

    # Files will be cascade deleted via DB relationship
    CheckupFile.query.filter_by(checkup_record_id=id).delete()

    db.session.delete(record)
    db.session.commit()
    flash('检查记录已删除', 'success')
    return redirect(url_for('checkup.list'))
