from flask import Flask, render_template
from .storage import Storage, Record, Collection


def create_app(test_config=None):
    app = Flask("exploratour", instance_relative_config=True)

    storage = Storage()
    storage.create_tables()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        storage.session.remove()

    from . import blueprints

    blueprints.register(app)

    return app