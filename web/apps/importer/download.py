import cherrypy
import config
import itertools
import lxml.etree as etree
import os
import shutil
import tempfile
import threading
from apps.bgprocess import pool, TaskProgress
from apps.mediainfo.views import mapper
from apps.record.errors import ValidationError
from apps.shortcuts import getparam, getintparam, redirect, url
from apps.store.models import Record, Collection
from apps.templates.render import render

class IdAllocator(object):
    """Threadsafe sequential ID allocator."""
    def __init__(self):
        self.cond = threading.Condition()
        self.nextid = 1

    def get(self):
        self.cond.acquire()
        try:
            ret = self.nextid
            self.nextid += 1
            return ret;
        finally:
            self.cond.release()

g_allocator = IdAllocator()


class Importer(object):
    """Download, analyse and import a file."""
    def __init__(self):
        self.id = g_allocator.get()
        self.tmpdir = None
        self._error = None

        # Set if there's info to be got from user.
        self._info_getter = None

        # Set if there's a task to do.
        self._task_id = None
        self._task = None

        # Description of current activity
        self._status = None

        self._cancelled = False

    def start(self, params):
        """Start the import process. """
        fileobj = params.get('file', None)
        if self.receive_file(fileobj):
            self.set_task(ImportAnalysisTask(self.infile_path, self))

    @property
    def error(self):
        """Return error message iff import failed; None otherwise."""
        return self._error

    def cancel(self):
        self._status = 'Cancelled'
        self._cancelled = True
        if self._info_getter is not None:
            self._info_getter = None
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def handle_get(self, params):
        context = dict(status=self._status, import_id=self.id,
                       cancelled=self._cancelled)

        # FIXME - threadsafety of access to _info_getter, _task, _task_id ;
        # they should be atomically read and written.

        if self._info_getter is not None:
            return self._info_getter.handle_get(params, context)

        if self._task is not None:
            progress = pool.get_progress(self._task_id)
            context['status'] = "%s: %s" % (self._status, progress.msg)
            if progress.failed:
                context['status'] = "Failed: %s" % context['status']
                context['finished'] = True
            if progress.complete:
                context['finished'] = True

        if self._task is None and self._info_getter is None:
            context['finished'] = True
        return render("import/status.html", context)

    def handle_post(self, params):
        context = dict(status=self._status, import_id=self.id)
        if self._info_getter is not None:
            return self._info_getter.handle_post(params, context)

        # Not a valid request if there isn't an info getter.
        raise cherrypy.HTTPError(400)

    def finish(self):
        """Clean up at end of import."""
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir)

    def receive_file(self, fileobj):
        """Receive a file and store in tmpdir."""
        self._status = 'Receiving import file'
        if fileobj is None or not fileobj.filename:
            self._error = 'No file supplied'
            return False
        self.filename = fileobj.filename
        self.tmpdir = tempfile.mkdtemp(dir=config.tmpdir)
        self.infile_path = os.path.join(self.tmpdir, "input")
        with open(self.infile_path, "wb") as fd:
            shutil.copyfileobj(fileobj.file, fd)
        return True

    def set_task(self, task):
        self._status = task.status
        self._info_getter = None
        self._task = None
        self._task_id = pool.add_task(task)
        self._task = task

    def set_info_getter(self, info_getter):
        self._status = info_getter.status
        self._task_id = None
        self._task = None
        self._info_getter = info_getter


class StopImport(Exception): pass


class ImportTask(object):
    def __init__(self, importer):
        self._stop = False
        self.importer = importer

    def cancel(self):
        self._stop = True

    def perform(self):
        for progress in self.do():
            yield progress
            if progress.failed or progress.complete:
                break
            if self._stop:
                break

class ImportInfoGetter(object):
    def __init__(self, handler, importer):
        self.handler = handler
        self.importer = importer

    def set_next(self, item):
        if hasattr(item, 'perform'):
            self.importer.set_task(item)
        else:
            self.importer.set_info_getter(item)

class ImportAnalysisTask(ImportTask):
    status = "Analysing import file"

    def __init__(self, infile_path, importer):
        super(ImportAnalysisTask, self).__init__(importer)
        self.infile_path = infile_path

    def do(self):
        stat = os.stat(self.infile_path)
        yield TaskProgress("Parsing input file: %d bytes" % stat.st_size)

        with open(self.infile_path) as fd:
            start = fd.read(5)

        if start == '<?xml':
            handler = self.detect_xml_type()
            if not handler:
                yield TaskProgress("Unable to detect input XML file type",
                                   failed=True)
        else:
            yield TaskProgress("Unable to detect input file type",
                               failed=True)

        for progress in handler.probe():
            yield progress

        ig = ImportMappingInfoGetter(handler, self.importer)
        self.importer.set_info_getter(ig)

    def detect_xml_type(self):
        tree = etree.parse(self.infile_path)
        root = tree.getroot()
        if root.tag == 'container':
            return ExploratourImportHandler(root)


class ImportMappingInfoGetter(ImportInfoGetter):
    status = "Reviewing import file"

    def get_conflict_option(self, paramname, params):
        value = getparam(paramname, 'newid', None, params)
        if value not in ('overwrite', 'skip', 'newid', 'allnewid'):
            value = 'newid'
        return value

    def build_form_context(self, params):
        context = {}
        class Info(object):
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        # Determine how conflicts should be resolved
        self.handler.record_conflict_resolution = self.get_conflict_option('record_conflict', params)
        context['record_conflict'] = self.handler.record_conflict_resolution

        self.handler.coll_conflict_resolution = self.get_conflict_option('coll_conflict', params)
        context['coll_conflict'] = self.handler.coll_conflict_resolution

        # Get the media root mappings supplied by the client.
        media_root_mappings = {}
        for num, (root, rootinfo) in enumerate(sorted(self.handler.media_roots.items())):
            newroot = getparam('r%d' % num, root, None, params)
            rootinfo['newroot'] = newroot
            if newroot != root:
                media_root_mappings[root] = newroot
        self.handler.update_media_root_mappings(media_root_mappings)

        # Calculate the info, after the mappings have been applied.
        info = Info(filename = self.importer.filename,
                    records_count = len(self.handler.records),
                    record_identical = self.handler.record_identical,
                    record_conflicts = self.handler.record_conflicts,
                    record_new = self.handler.record_new,
                    collections = self.handler.collections,
                    coll_identical = self.handler.coll_identical,
                    coll_conflicts = self.handler.coll_conflicts,
                    coll_new = self.handler.coll_new,
                    media_files_count = len(self.handler.media_paths),
                    media_roots = enumerate(sorted(self.handler.media_roots.items())),
                   )
        context['info'] = info
        context['import_id'] = getintparam("id", None, None, params)
        return context

    def handle_get(self, params, context):
        context.update(self.build_form_context(params))
        return render("import/choose-mappings.html", context)

    def handle_post(self, params, context):
        context.update(self.build_form_context(params))
        do_import = getparam('import', None, None, params)
        if do_import:
            self.set_next(ImportPerformTask(self.handler, self.importer))
            redirect(url("import", id=self.importer.id))
        return render("import/choose-mappings.html", context)


class ImportPerformTask(ImportTask):
    status = "Performing import"

    def __init__(self, handler, importer):
        super(ImportPerformTask, self).__init__(importer)
        self.handler = handler

    def do(self):
        yield TaskProgress("Planning ID changes needed")
        self.handler.calc_id_mappings()

        yield TaskProgress("Applying ID changes")
        self.handler.apply_mappings()

        yield TaskProgress("Storing imported data")
        self.handler.store_data()

        yield TaskProgress("Import complete", complete=True)


class ExploratourImportHandler(object):
    def __init__(self, root):
        # The root of the XML document holding the import.
        self.root = root

        # Mapping from record id to record
        self.records = {}

        # Mapping from collection id to collection
        self.collections = {}

        # IDs of records which exist and are identical to those in export
        self.record_identical = set()

        # IDs of records which exist and are identical to those in export
        self.record_conflicts = set()

        self.record_conflict_resolution = None

        # IDs of records in the export which are new
        self.record_new = set()

        self.coll_identical = set()
        self.coll_conflicts = set()
        self.coll_new = set()

        self.coll_conflict_resolution = None

        self.media_paths = {}

        self.media_roots = {}

        # Mapping from root name in import to root name to use.
        self.media_root_mappings = {}

    def calc_id_mappings(self):
        if self.record_conflict_resolution == 'overwrite':
            self.records_to_skip = self.record_identical
            self.record_id_map = {}
        elif self.record_conflict_resolution == 'newid':
            self.records_to_skip = self.record_identical
            self.calc_record_id_mappings(False)
        elif self.record_conflict_resolution == 'allnewid':
            self.records_to_skip = set()
            self.calc_record_id_mappings(True)
        elif self.record_conflict_resolution == 'skip':
            self.records_to_skip = self.record_identical
            self.record_id_map = {}
        else:
            raise ValidationError("Unknown record ID conflict resolution: %r" %
                    self.record_conflict_resolution)

        if self.coll_conflict_resolution == 'overwrite':
            self.colls_to_skip = self.coll_identical
            self.coll_id_map = {}
        elif self.coll_conflict_resolution == 'newid':
            self.colls_to_skip = self.coll_identical
            self.calc_coll_id_mappings(False)
        elif self.coll_conflict_resolution == 'allnewid':
            self.colls_to_skip = {}
            self.calc_coll_id_mappings(True)
        elif self.coll_conflict_resolution == 'skip':
            self.colls_to_skip = self.coll_identical
            self.coll_id_map = {}
        else:
            raise ValidationError("Unknown collection ID conflict resolution: %r" %
                    self.coll_conflict_resolution)

    def calc_record_id_mappings(self, remap_all):
        id_map = {}
        for id in self.record_conflicts:
            id_map[id] = Record.objects._alloc_id()
        if remap_all:
            for id in self.record_identical:
                id_map[id] = Record.objects._alloc_id()
        self.record_id_map = id_map

    def calc_coll_id_mappings(self, remap_all):
        id_map = {}
        for id in self.coll_conflicts:
            id_map[id] = Collection.objects._alloc_id()
        if remap_all:
            for id in self.coll_identical:
                id_map[id] = Collection.objects._alloc_id()
        self.coll_id_map = id_map

    def apply_mappings(self):
        for coll in self.collections.itervalues():
            coll.apply_mappings(self.record_id_map, self.coll_id_map,
                                self.media_root_mappings)

        for record in self.records.itervalues():
            record.apply_mappings(self.record_id_map, self.coll_id_map,
                                  self.media_root_mappings)

    def store_data(self):
        for coll_id, coll in self.collections.iteritems():
            if coll_id in self.colls_to_skip:
                print "skipping collection %s" % coll.id
                continue
            print "setting collection %s: %s" % (coll.id, coll)
            Collection.objects.set(coll)

        for record_id, record in self.records.iteritems():
            if record_id in self.records_to_skip:
                print "skipping record %s" % record.id
                continue
            print "setting record %s: %s" % (record.id, record)
            Record.objects.set(record)

        Collection.objects.flush()
        Record.objects.flush()

    def update_media_root_mappings(self, media_root_mappings):
        if self.media_root_mappings != media_root_mappings:
            self.media_root_mappings = media_root_mappings
            self.calc_media_roots()

    def calc_media_roots(self):
        self.media_roots = {}
        for media_path, media in self.media_paths.iteritems():
            assert media_path.startswith('/')
            head_tail = media_path[1:].split('/', 1)
            if len(head_tail) == 1:
                head, tail = head_tail, ''
            else:
                head, tail = head_tail
            newhead = self.media_root_mappings.get(head, head)
            path = mapper._map_path('/' + '/'.join((newhead, tail)))
            if path is None:
                exists = False
            else:
                exists = os.path.isfile(path)
            info = self.media_roots.get(head, None)
            if info is None:
                info = dict(tail=tail, existing=0, missing=0,
                            known=mapper.known_root(newhead),
                            newroot=newhead,
                           )
                self.media_roots[head] = info 
            else:
                tail = tail.split('/')
                common_tail = info['tail'].split('/')
                for i, (a, b) in enumerate(zip(tail, common_tail)):
                    if a != b:
                        break
                info['tail'] = '/'.join(common_tail[:i])
            if exists:
                info['existing'] += 1
            else:
                info['missing'] += 1

    def probe(self):
        items = sum(len(item) for item in self.root)
        for num, item in enumerate(itertools.chain.from_iterable(item for item in self.root)):
            yield TaskProgress("Probing XML file, element %d of %d" % (num + 1, items))
            if item.tag == 'record':
                record = Record(root=item)
                self.records[record.id] = record
                self.media_paths.update((m.src, m) for m in record.media(mimetype=None))
                try:
                    old_record = Record.objects.get(record.id)
                except KeyError:
                    self.record_new.add(record.id)
                else:
                    if old_record.mtime == record.mtime and \
                       old_record.xml.strip() == record.xml.strip():
                        self.record_identical.add(record.id)
                    else:
                        self.record_conflicts.add(record.id)

            elif item.tag == 'collection':
                coll = Collection.fromxml(root=item)
                self.collections[coll.id] = coll

                try:
                    old_coll = Collection.objects.get(coll.id)
                except KeyError:
                    self.coll_new.add(coll.id)
                else:
                    if old_coll == coll:
                        self.coll_identical.add(coll.id)
                    else:
                        self.coll_conflicts.add(coll.id)

        self.calc_media_roots()


################### OLD CODE

def do_import(ctx):
    tree = etree.parse(ctx.fileobj.file)
    root = tree.getroot()
    if root.tag != 'records':
        return ctx.set_error('File format not understood - expected root tag '
                             'to be records, got %s' % root.tag)

    for item in root:
        if item.tag != 'record':
            return ctx.set_error('Expected a record, got %s' % item.tag)

        record = Record(root=item)
        record.id = ctx.idprefix + record.id
        record.collections = [ctx.collname]
        Record.objects.set(record)
    Record.objects.flush()
    Collection.objects.flush()
