from apps.lockto.utils import get_lockto_coll
from apps.shortcuts import redirect, url
from apps.store.models import Collection
from apps.search.models import SearchParams, Search
from apps.export.impl.base import Exporter
from apps.templates.render import render
from apps.shortcuts import get_or_404, getparam, getintparam
from apps.bgprocess import pool, TaskProgress
from apps.search.models import SearchCollection
import cherrypy
import config
import tempfile

# Cause the exporters to be registered
import apps.export.impl

# Map from task id to the export task
exports = {}

class ExportRecords(object):
    """An export task"""
    def __init__(self, exporter, search):
        self.exporter = exporter
        self.search = search

    def perform(self):
        yield TaskProgress("Started export")

        count = len(self.search)
        for index, r in enumerate(self.search):
            self.exporter.add(r.object)
            yield TaskProgress("Phase 1: Fetched %d of %d" % (index + 1, count))
        for progress in self.exporter.export(tempfile.mkdtemp(dir=config.tmpdir)):
            yield TaskProgress("Phase 2: %s" % progress)
        self.headers = self.exporter.headers
        self.resultpath = self.exporter.resultpath
        del self.exporter

    def respond(self):
        """Send the result of the export to the browser"""
        cherrypy.response.headers.update(self.headers)
        return open(self.resultpath)


class ExportController(object):
    def _get_export_records(self, stash, record_id, issearch, coll, incsubs):
        """Returns a search queryset, and a description of the export."""

        # record_id is set to export a single record.
        if record_id is not None:
            search = SearchCollection.doc_type('record').field.id == record_id
            return search, "record with id %s" % record_id, None

        # if issearch is set, export the search results.
        if issearch is not None:
            params = SearchParams(stash)
            search_obj = Search(params)
            if not search_obj.validate():
                redirect(url("search", **stash))
            desc = "%d records found by search.\n" % search_obj.match_count
            return search_obj.query, desc + search_obj.query_desc, None

        # FIXME - allow selected records here.

        # If we've got no collection set, but have a lock, set the collection
        # to the locked one.
        lockedto = get_lockto_coll()
        if lockedto is not None and coll is None:
            coll = lockedto.id

        # coll is set to export a whole collection.
        if coll is not None:
            coll_obj = get_or_404(Collection, coll)
            search = coll_obj.items_from_search(incsubs=incsubs)

            desc = "all %d records from collection %s" % (
                len(search),
                coll_obj.title
            )
            if incsubs:
                desc += " (including subcollections)"
            return search, desc, coll_obj

        # If none of the above are set, export everything.
        return SearchCollection.doc_type('record').all()[:], "all records", None


    def export_records(self, export_id=None, fmt='rtf', download=False,
                       **params):
        """Export a set of records.

        """
        # Read parameters first, to ensure they all get stashed.
        stash = {}
        record_id = getparam('record_id', None, stash, params)
        issearch = getparam('issearch', None, stash, params)
        coll = getparam('coll', None, stash, params)
        incsubs = getintparam('incsubs', 1, stash, params)

        # Make a new exporter, and get any parameters it needs into the stash.
        try:
            exp = Exporter.get(fmt)()
        except KeyError:
            raise cherrypy.NotFound
        exp.read_params(stash, params)

        # Handle exports which are in progress, or have finished
        if export_id is not None:
            try:
                export_id = int(export_id)
            except ValueError:
                export_id = None
        if export_id is not None:
            try:
                running_exp = exports[export_id]
            except KeyError:
                # Invalid export id (most probably due to a server restart)
                running_exp = None
            if running_exp is not None:
                # Export in progress
                progress = pool.get_progress(export_id)
                context = dict(export_id=export_id, fmt=fmt, progress=progress,
                               stash=stash)
                if not progress.complete:
                    return render('export/in_progress.html', context)
                if progress.failed:
                    return render('export/failed.html', context)
                # Export complete
                if not download:
                    # Display a "Export prepared"
                    return render('export/complete.html', context)
                return running_exp.respond()

        # Read the set of things to export.
        search, desc, topcoll = self._get_export_records(stash, record_id, issearch,
                                                coll, incsubs)

        if not getparam('export', False, stash, params):
            # Not ready to start the export yet.
            context = dict(
                           fmts = Exporter.fmts(params),
                           fmt = fmt,
                           export_desc = desc,
                           stash = stash,
                          )

            exp.add_to_context(context, search, stash, params)
            return render('export/pickfmt.html', context)

        # Start the exporter
        task = ExportRecords(exp, search)
        export_id = pool.add_task(task)
        exports[export_id] = task

        redirect(url("records-export-inprogress", export_id=export_id, fmt=fmt, **stash))

    def export_backup(self, export_id=None, download=False, **params):
        # Read parameters first, to ensure they all get stashed.
        stash = {}

        # Make a new exporter, and get any parameters it needs into the stash.
        exp = Exporter.get('xml')()
        exp.read_params(stash, params)

        # Handle exports which are in progress, or have finished
        if export_id is not None:
            try:
                export_id = int(export_id)
            except ValueError:
                export_id = None
        if export_id is not None:
            try:
                running_exp = exports[export_id]
            except KeyError:
                # Invalid export id (most probably due to a server restart)
                running_exp = None
            if running_exp is not None:
                # Export in progress
                progress = pool.get_progress(export_id)
                context = dict(export_id=export_id, fmt='xml', progress=progress,
                               stash=stash)
                if not progress.complete:
                    return render('export/in_progress.html', context)
                if progress.failed:
                    return render('export/failed.html', context)
                # Export complete
                if not download:
                    # Display a "Export prepared"
                    return render('export/complete.html', context)
                return running_exp.respond()

        # Read the set of things to export.
        search, desc, topcoll = self._get_export_records(stash, None, None, None, True)

        if not getparam('export', False, stash, params):
            # Not ready to start the export yet.
            context = dict(
                           export_desc = desc,
                           stash = stash,
                          )

            exp.add_to_context(context, search, stash, params)
            return render('backup/pick.html', context)

        # Start the exporter
        task = ExportRecords(exp, search)
        export_id = pool.add_task(task)
        exports[export_id] = task

        redirect(url("records-export-inprogress", export_id=export_id, fmt='xml', **stash))
