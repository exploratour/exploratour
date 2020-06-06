from . import collections, records, navigation, media


def register(app):
    app.register_blueprint(collections.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(navigation.bp)
    app.register_blueprint(media.bp)
    app.add_url_rule("/", endpoint="index")
