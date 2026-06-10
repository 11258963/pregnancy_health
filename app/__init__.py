import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_moment import Moment
from config import Config

db = SQLAlchemy()
moment = Moment()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure SQLite parent directory exists before opening the database.
    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if database_uri.startswith('sqlite:///'):
        db_path = database_uri.replace('sqlite:///', '', 1)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db.init_app(app)
    moment.init_app(app)

    from app.routes import index, weight, checkup, diary, movement
    app.register_blueprint(index.bp)
    app.register_blueprint(weight.bp)
    app.register_blueprint(checkup.bp)
    app.register_blueprint(diary.bp)
    app.register_blueprint(movement.bp)

    with app.app_context():
        db.create_all()
        _migrate_settings_columns()
        # 确保上传目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # 加载预产期设置
        from app.models import Settings
        settings = Settings.query.first()
        if settings and settings.due_date:
            app.config['DUE_DATE'] = settings.due_date

    return app


def _migrate_settings_columns():
    """为已有 SQLite 数据库补充 settings 新字段。"""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if 'settings' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('settings')}
    statements = []
    if 'movement_api_token' not in columns:
        statements.append('ALTER TABLE settings ADD COLUMN movement_api_token VARCHAR(64)')
    if 'movement_reminder_enabled' not in columns:
        statements.append('ALTER TABLE settings ADD COLUMN movement_reminder_enabled BOOLEAN DEFAULT 1')
    if not statements:
        return
    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
