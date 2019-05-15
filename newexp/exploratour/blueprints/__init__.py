from . import collections, navigation

def register(app):
    app.register_blueprint(collections.bp)
    app.register_blueprint(navigation.bp)
    app.add_url_rule('/', endpoint="index")
