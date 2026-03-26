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

    db.init_app(app)
    moment.init_app(app)

    from app.routes import index, weight, checkup, diary
    app.register_blueprint(index.bp)
    app.register_blueprint(weight.bp)
    app.register_blueprint(checkup.bp)
    app.register_blueprint(diary.bp)

    with app.app_context():
        db.create_all()
        # 确保上传目录存在
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        # 加载预产期设置
        from app.models import Settings
        settings = Settings.query.first()
        if settings and settings.due_date:
            app.config['DUE_DATE'] = settings.due_date

    return app
