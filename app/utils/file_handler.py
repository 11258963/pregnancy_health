import os
import uuid
from werkzeug.utils import secure_filename as werkzeug_secure_filename

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}


def allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_file_type(filename):
    """根据扩展名判断文件类型"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif ext in ALLOWED_DOCUMENT_EXTENSIONS:
        return 'document'
    return None


def secure_filename_with_ext(filename):
    """生成安全的文件名"""
    if '.' not in filename:
        return f"{uuid.uuid4().hex}"

    name = werkzeug_secure_filename(filename.rsplit('.', 1)[0])
    ext = filename.rsplit('.', 1)[1].lower()

    # 生成唯一文件名避免冲突
    unique_name = f"{uuid.uuid4().hex}_{name[:50]}"
    return f"{unique_name}.{ext}"


def validate_file(file):
    """验证文件是否有效"""
    if not file or file.filename == '':
        return False, 'No file provided'

    # 检查扩展名
    file_type = get_file_type(file.filename)
    if not file_type:
        return False, 'File type not allowed'

    return True, file_type


def save_file(file, record_id):
    """保存文件到磁盘

    Args:
        file: Werkzeug FileStorage object
        record_id: The checkup record ID

    Returns:
        tuple: (stored_filename, original_filename, file_type, file_size, file_path)
    """
    from flask import current_app

    original_filename = file.filename
    stored_filename = secure_filename_with_ext(original_filename)
    file_type = get_file_type(original_filename)

    # 创建子目录: uploads/record_{id}/
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], f'record_{record_id}')
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, stored_filename)
    file.save(file_path)

    # 获取文件大小
    file_size = os.path.getsize(file_path)

    return stored_filename, original_filename, file_type, file_size


def delete_file(stored_filename, record_id):
    """删除文件"""
    from flask import current_app

    file_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        f'record_{record_id}',
        stored_filename
    )
    if os.path.exists(file_path):
        os.remove(file_path)


def delete_all_files_for_record(record_id):
    """删除记录的所有文件及目录"""
    from flask import current_app

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], f'record_{record_id}')
    if os.path.exists(upload_dir):
        import shutil
        shutil.rmtree(upload_dir)


def get_file_path(stored_filename, record_id):
    """获取文件的完整路径"""
    from flask import current_app

    return os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        f'record_{record_id}',
        stored_filename
    )
