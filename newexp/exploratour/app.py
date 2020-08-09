from flask import Flask, render_template
from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
import secrets

db = SQLAlchemy()

def create_app(test_config=None):
    app = Flask("exploratour", instance_relative_config=True)

    db.init_app(app)

    app.config["SECRET_KEY"] = secrets.token_urlsafe(20)
    DebugToolbarExtension(app)

    with app.app_context():
        from .storage import storage
        storage.create_tables()

        from . import blueprints
        blueprints.register(app)

        return app
