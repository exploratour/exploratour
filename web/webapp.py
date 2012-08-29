import cherrypy
import config
import os

def initialise():
    """Do generic initialisation tasks.

    """
    if not os.path.isdir(config.logdir):
        os.makedirs(config.logdir)
    if not os.path.isdir(config.datadir):
        os.makedirs(config.datadir)

    # Import the store, to ensure it's initialised before we enter
    # multithreaded code.
    import apps.store.store

    import mimetypes
    mimetypes.add_type('video/mp4', '.m4v')
    mimetypes.add_type('video/mp4', '.mp4')
    mimetypes.add_type('video/ogg', '.ogv')
    mimetypes.add_type('video/webm', '.webm')

class WebApp(object):
    def __init__(self):
        # Set up controller objects
        import apps.main.views
        self.c_main = apps.main.views.MainController()
        #import apps.dataview.views
        #self.c_dataview = apps.dataview.views.DataViewController()
        import apps.export.views
        self.c_export = apps.export.views.ExportController()
        import apps.importer.views
        self.c_import = apps.importer.views.ImportController()
        import apps.mediainfo.views
        self.c_media = apps.mediainfo.views.MediaController()
        import apps.record.views
        self.c_record = apps.record.views.RecordController()
        self.c_coll = apps.record.views.CollectionController()
        self.c_tmpl = apps.record.views.TemplateController()
        self.c_colls = apps.record.views.CollectionsController()
        self.c_tmpls = apps.record.views.TemplatesController()
        import apps.search.views
        self.c_search = apps.search.views.SearchController()
        import apps.settings.views
        self.c_settings = apps.settings.views.SettingsController()
        import apps.thumbnail.views
        self.c_thumbnail = apps.thumbnail.views.ThumbnailController()
        import apps.users.views
        self.c_user = apps.users.views.UserController()

        import apps.errors.views
        self.c_error = apps.errors.views.ErrorController()

    def get_config(self):
        """Get the configuration for this app.

        """
        routes = cherrypy.dispatch.RoutesDispatcher()

        routes.connect('home', '/', controller=self.c_main, action="index")

        routes.connect('media', '/media',
                       controller=self.c_media, action="media")
        routes.connect('mediainfo', '/mediainfo',
                       controller=self.c_media, action="mediainfo")
        routes.connect('mediapreview', '/mediapreview',
                       controller=self.c_media, action="mediapreview")
        routes.connect('thumbnail', '/thumbnail',
                       controller=self.c_thumbnail, action="thumbnail")
        routes.connect('tile', '/tile',
                       controller=self.c_thumbnail, action="tile")

        routes.connect('record-create', '/record_create',
                       controller=self.c_record, action="create")
        routes.connect('record-edit', '/record/{id}/edit',
                       controller=self.c_record, action="edit")
        routes.connect('record-copy', '/record/{id}/copy',
                       controller=self.c_record, action="copy")
        routes.connect('record-delete', '/record/{id}/delete',
                       controller=self.c_record, action="delete")
        routes.connect('record-view', '/record/{id}',
                       controller=self.c_record, action="view")
        routes.connect('record-unframed', '/record/{id}/unframed',
                       controller=self.c_record, action="unframed")
        routes.connect('record-gallery', '/record/{id}/gallery',
                       controller=self.c_record, action="gallery")

        routes.connect('record-edit-fragment', '/record_edit_fragment',
                       controller=self.c_record, action="edit_fragment")

        routes.connect('coll-create', '/coll_create',
                       controller=self.c_coll, action="create")
        routes.connect('coll-delete', '/coll/{id}/delete',
                       controller=self.c_coll, action="delete")
        routes.connect('coll-reorder', '/coll/{id}/reorder',
                       controller=self.c_coll, action="reorder")
        routes.connect('coll-reparent', '/coll/{id}/reparent',
                       controller=self.c_coll, action="reparent")
        routes.connect('coll-view', '/coll/{id}',
                       controller=self.c_coll, action="view")

        routes.connect('tmpl-create', '/tmpl_create',
                       controller=self.c_tmpl, action="create")
        routes.connect('tmpl-edit', '/tmpl/{id}/edit',
                       controller=self.c_tmpl, action="edit")
        routes.connect('tmpl-view', '/tmpl/{id}',
                       controller=self.c_tmpl, action="view")
        routes.connect('tmpl-delete', '/tmpl/{id}/delete',
                       controller=self.c_tmpl, action="delete")

#        routes.connect('view-create', '/view_create',
#                       controller=self.c_dataview, action="create")
#        routes.connect('view-view', '/view/{id}',
#                       controller=self.c_dataview, action="view")

        routes.connect('records-export-inprogress', '/export/records/{export_id}.{fmt}',
                       controller=self.c_export, action="export_records")
        routes.connect('records-export', '/export/records',
                       controller=self.c_export, action="export_records")

        routes.connect('backup', '/backup',
                       controller=self.c_export, action="export_backup")

        routes.connect('import-download', '/import',
                       controller=self.c_import, action="imp")

        routes.connect('import-from-bamboo', '/import/from/bamboo',
                       controller=self.c_import, action="from_bamboo")
        routes.connect('import-from-mediapro', '/import/from/mediapro',
                       controller=self.c_import, action="from_mediapro")
        routes.connect('import-from-exploratour', '/import/from/exploratour',
                       controller=self.c_import, action="from_exploratour")
        routes.connect('import-status', '/import/status/{id}',
                       controller=self.c_import, action="status")

        routes.connect('search', '/search',
                       controller=self.c_search, action="search")
        routes.connect('ac', '/ac',
                       controller=self.c_search, action="ac")

        routes.connect('colls-list', '/colls/list',
                       controller=self.c_colls, action="list")

        routes.connect('tmpls-list', '/tmpls/list',
                       controller=self.c_tmpls, action="list")
        routes.connect('tmpls-pick', '/tmpls/pick',
                       controller=self.c_tmpls, action="pick")

        routes.connect('user-lastdate', '/user/lastdate',
                       controller=self.c_user, action="lastdate")

        routes.connect('reindex', '/reindex',
                       controller=self.c_search, action="reindex")

        routes.connect('settings-roots', '/settings/roots',
                       controller=self.c_settings, action="roots")

        return {
            '/': {
                'request.dispatch': routes,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': config.staticdir,
            },
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename':
                    os.path.join(config.staticdir, "favicon.png"),
            },
        }

    def get_server_config(self):
        return {
            'error_page.404': self.c_error.error_page_404,
        }
