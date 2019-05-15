from flask import Flask
from .storage import Storage, Record, Collection

def create_app(test_config=None):
    app = Flask("exploratour", instance_relative_config=True)

    storage = Storage()
    storage.create_tables()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        storage.session.remove()

    @app.route("/")
    def records():
        return "Records {}".format(storage.session.query(Record).count())

    return app
