import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'pregnancy-health-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_PATH') or f'sqlite:///{os.path.join(basedir, "data", "pregnancy.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 文件上传设置 - 使用环境变量，默认为 /data/uploads
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/data/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # 预产期（首次设置后保存）
    DUE_DATE = None

    # 孕周计算常量
    PREGNANCY_DAYS = 280  # 40周
