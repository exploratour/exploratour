
from apps.shortcuts import getparam, getintparam, redirect, url
from apps.templates.render import render
import cherrypy

from apps.importer import download, import_bamboo, import_mediapro, import_exploratour

class ImportController(object):
    def __init__(self):
        self.imports = {}

    def imp(self, **params):
        stash = {}

        # Get any existing Importer
        imp = None
        imp_id = getintparam("id", None, stash, params)
        if imp_id is not None:
            imp = self.imports.get(imp_id, None)
            if imp is None:
                context = {}
                context['error'] = 'Unknown import ID'
                return render("import/choose-file.html", context)

        if imp is None:
            # No import in progress
            if cherrypy.request.method == "POST":
                return self.handle_import_start(params)
            elif cherrypy.request.method == "GET":
                return render("import/choose-file.html", {})
        else:
            # Import in progress; let it handle the request.
            if cherrypy.request.method == "POST":
                if getparam("import_cancel", None):
                    imp.cancel()
                    redirect(url("home"))
                return imp.handle_post(params)
            elif cherrypy.request.method == "GET":
                return imp.handle_get(params)

        raise cherrypy.NotFound

    def handle_import_start(self, params):
        """Handle a POST request that starts an import."""
        if getparam("import_cancel", None):
            redirect(url("home"))
        imp = download.Importer()
        imp.start(params)
        if imp.error:
            context = {}
            context['error'] = imp.error
            return render("import/choose-file.html", context)
        self.imports[imp.id] = imp
        redirect(url("import", id=imp.id))


#### OLD CODE

    def from_bamboo(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            imp = import_bamboo.start_import(params)
            if imp.error:
                context['error'] = imp.error
                return render("import/from-bamboo.html", context)
            self.imports[imp.id] = imp
            redirect(url("import-status", id=imp.id))
        return render("import/from-bamboo.html", context)

    def from_mediapro(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            imp = import_mediapro.start_import(params)
            if imp.error:
                context['error'] = imp.error
                return render("import/from-mediapro.html", context)
            self.imports[imp.id] = imp
            redirect(url("import-status", id=imp.id))
        return render("import/from-mediapro.html", context)

    def from_exploratour(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            imp = import_exploratour.start_import(params)
            if imp.error:
                context['error'] = imp.error
                return render("import/from-exploratour.html", context)
            self.imports[imp.id] = imp
            redirect(url("import-status", id=imp.id))
        return render("import/from-exploratour.html", context)

    def status(self, id):
        imp = self.imports.get(id, None)
        context = dict(imp=imp)
        return render("import/status.html", context)
