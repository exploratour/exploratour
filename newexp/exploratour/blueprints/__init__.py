from . import collections, records, navigation


def register(app):
    app.register_blueprint(collections.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(navigation.bp)
    app.add_url_rule("/", endpoint="index")
