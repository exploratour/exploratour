from apps.store.models import Record, Collection, Template
from apps.templates.render import render
import cherrypy
from lxml import etree

class MainController(object):
    def index(self):
        context = dict(
            records = len(Record.objects),
            collections = len(Collection.objects),
            templates = len(Template.objects),
        )
        return render("index.html", context)
