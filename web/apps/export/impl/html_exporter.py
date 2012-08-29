from apps.export.impl.base import Exporter
from apps.mediainfo.views import mapper as media_mapper
from apps.mediainfo.views import _local_is_hidden, isotime
from apps.record.calutils import calendar_items
from apps.search.models import SearchParams, Search
from apps.shortcuts import slugify, getparam
from apps.store.models import Record, Collection
from apps.store.search import Collection as SearchCollection
from apps.thumbnail.thumbnail import thumbtype, thumbsize, imgsize, thumbcache, get_format, mimetype
import apps.templates.render
import config
import datetime
from lxml import etree
import copy
import jinja2
import math
import os
import re
import zipfile

safename_re = re.compile(r'[^a-z0-9_-]')

def tupleify(val):
    if isinstance(val, basestring):
        return (val,)
    elif hasattr(val, '__iter__'):
        return tuple(val)
    return (val,)


def get_args(kwargs):
    # First read the old args
    newkwargs = dict(
        (k, v[3:]) for (k, v) in kwargs.iteritems()
        if v is not None and k.startswith('old')
    )
    # Apply neither new nor old args
    for (k, v) in kwargs.iteritems():
        if k.startswith('new') or k.startswith('old'):
            continue
        if v is None:
            try:
                del newkwargs[k]
            except KeyError: pass
        else:
            newkwargs[k] = v
    # Apply new args
    for (k, v) in kwargs.iteritems():
        if k[:3] != 'new':
            continue
        k = k[3:]
        if v is None:
            try:
                del newkwargs[k]
            except KeyError: pass
        else:
            newkwargs[k] = v
    return newkwargs


class HtmlExporter(Exporter):
    fmt = 'html'
    description = "Static HTML archive, for publishing on web"
    priority = 20

    def __init__(self):
        self.cache = {}
        super(HtmlExporter, self).__init__()

    @classmethod
    def is_valid(cls, params):
        """Check if the exporter is valid for the given parameters."""
        collid = getparam('coll', None, None, params)
        if collid is None:
            return False
        return True

    def read_params(self, stash, params):
        self.collid = getparam('coll', None, stash, params)
        self.incmedia = getparam('incmedia', 'include', stash, params)
        self.mediabase = getparam('mediabase', '', stash, params)

        self.frontpage = None
        if self.collid:
            types_available, dates_available = self.types_in_collection(self.collid)
            coll = Collection.objects.get(self.collid)
            if coll is not None:
                allowed_ancestors = self.allowed_ancestors(coll)
                maintab = self.coll_maintab(coll, types_available, dates_available,
                                            allowed_ancestors)
                if not coll.has_children:
                    subs = 'coll'
                else:
                    subs = 'all'
                self.frontpage = 'coll/%s/%s/detail/%s/index.html' % \
                    (self.collid, maintab, subs)


    @property
    def headers(self):
        return {
            'Content-Type': 'application/zip',
            'Content-Disposition': 'attachment; filename=export.zip',
        }

    def add_to_context(self, context, search, stash, params):
        super(HtmlExporter, self) \
            .add_to_context(context, search, stash, params)
        context.update(dict(
                            incmedia = self.incmedia,
                            mediabase = self.mediabase,
                           ))

    @property
    def resultpath(self):
        return self.outpath

    def copyfile(self, sourcepath, zippath):
        """Copy a file from the filesystem to the zipfile.

        :param sourcepath: The path in the filesystem to the file to copy.

        :param zippath: The path to the file within the zip.  This excludes
        the top directory, which all files are placed within.

        """
        #print "copying %s -> %s" % (sourcepath, zippath)
        self.zfd.write(sourcepath, '/'.join((self.topdir, zippath)))

    def addfile(self, zippath, contents, mtime=None, compress=True):
        """Add a file to the zipfile.

        :param zippath: The path to the file within the zip.  This excludes
        the top directory, which all files are placed within.

        :param contents: The contents of the file, as bytes or as a string; a
        string will be encoded using UTF8.

        :param mtime: The modification time of the file, or None for "now".
        This is expected to be a datetime object, or at least something with
        the same .year, .month, etc properties, or a float representing a unix
        timestamp.  Timestamps with a year earlier than 1980 cannot be
        represented, and are converted to the start of 1980.

        :param compress: Whether to compress the file stored in the archive.

        """
        #print "adding:", zippath
        if mtime is None:
            mtime = datetime.datetime.now()
        elif isinstance(mtime, float):
            mtime = datetime.datetime.fromtimestamp(mtime)
        if mtime.year < 1980:
            mtime = datetime.datetime(1980, 1, 1)
        mtime_tuple = (
            mtime.year,
            mtime.month,
            mtime.day,
            mtime.hour,
            mtime.minute,
            mtime.second,
            # Ignore subsecond resolution, since the standard zipfile format
            # doesn't represent this.
        )
        fileinfo = zipfile.ZipInfo('%s/%s' % (self.topdir, zippath),
                                   mtime_tuple)
        fileinfo.create_system = 3 # Claim to be created by a UNIX system
        fileinfo.external_attr = 0666 << 16L # Read+write unix permissions

        if compress:
            compress_type = zipfile.ZIP_DEFLATED
        else:
            compress_type = zipfile.ZIP_STORED

        if isinstance(contents, unicode):
            contents = contents.encode('utf8')

        self.zfd.writestr(fileinfo, contents, compress_type)

    def thumbiconurl(self, public_path):
        def mimetypeurl(type):
            """Get the URL of an icon for a mimetype.

            """
            if type is None:
                iconname = 'unknown.png'
            else:
                iconname = safename_re.sub('_', type.lower()) + '.png'
                iconfile = os.path.join(config.staticdir, 'icons', 'thumbs', iconname)
                if not os.path.exists(iconfile):
                    iconname = safename_re.sub('_', type.split('/')[0].lower()) + '.png'
                    iconfile = os.path.join(config.staticdir, 'icons', 'thumbs', iconname)
                if not os.path.exists(iconfile):
                    iconname = 'unknown.png'
            return self.url('static', 'icons', 'thumbs', iconname)
        return mimetypeurl(mimetype(public_path))

    def get_file_info(self, public_path):
        path = media_mapper._map_path(public_path)
        if path is None:
            return None

        filename = os.path.basename(public_path)
        mtype = mimetype(filename)

        type = thumbtype(path)
        summary = None
        if type == 'text':
            fd = open(path)
            try:
                summary = fd.read(100) + '...'
            except IOError:
                pass

        return dict(name=filename,
                    mimetype=mtype,
                    type=type,
                    thumburl=None, # unused
                    src=public_path,
                    summary=summary,
                    url=self.url("media", path=public_path),
                    size=os.path.getsize(path),
                    mtime=isotime(os.path.getmtime(path)),
                    hidden=_local_is_hidden(path),
                )


    def url(self, *args, **kwargs):
        if len(args) == 0 and len(kwargs) == 0:
            return '.'
        kwargs = get_args(kwargs)
        page = args[0]
        return self.top_relpath + self.lookup_path(page, args[1:], kwargs)

    def get_zippath(self, rawpath):
        """Generate a path for a file in a zip, given a path which may have
        bits which need escaping to be valid in a zip.

        """
        pathparts = rawpath.split('/')
        for i in xrange(len(pathparts)):
            fullpath = (i + 1 == len(pathparts))
            key = u'/'.join(pathparts[:i+1])
            zippath = self.rawpaths.get(key, None)
            if zippath is not None:
                continue

            # Generate new unique slug for the filename at this level
            zippath = self.rawpaths.get(u'/'.join(pathparts[:i]), '')
            if zippath != '':
                zippath += '/'
            if fullpath:
                path = pathparts[i].rsplit(u'.', 1)
                if len(path) == 2:
                    path, ext = path
                else:
                    path, ext = path[0], u''
                zippath += slugify(path)
                ext = u'.' + slugify(ext)
            else:
                zippath += slugify(pathparts[i])
                ext = u''
            if zippath + ext in self.zippaths:
                j = 1
                while True:
                    tmp = '%s_%d' % (zippath, j)
                    if tmp + ext not in self.zippaths:
                        zippath = tmp
                        break
                    j += 1
            zippath = zippath + ext

            self.zippaths.add(zippath)
            self.rawpaths[key] = zippath 
        return zippath

    def lookup_path(self, name, args, kwargs):
        """Lookup a path for a named page with given arguments.

        This is the single point where all paths used in the zip file are
        defined; it is the equivalent of the URL mapping for the web interface.

        """
        return self.get_zippath(self.lookup_path_internal(name, args, kwargs))

    def lookup_path_internal(self, name, args, kwargs):
        #print name, args, kwargs
        kwargs = get_args(kwargs)
        if name == 'static':
            static = u'/'.join(args)
            if '..' in static.split('/') or static.startswith('/'):
                print "error: invalid static %r" % static
                return u'404.html'
            self.gen_static.add(static)
            return u'static/' + static
        if name == 'record-view':
            return u'record/%s.html' % kwargs['id']
        if name == 'media':
            path = kwargs['path']
            self.gen_media.add(path)
            return u'media%s' % path
        if name == 'mediapreview':
            path = kwargs['path']
            self.gen_media.add(path)
            htmlpath = path + '.html'
            return u'mediaview%s' % htmlpath
        if name == 'thumbnail':
            path = kwargs['path']
            width = kwargs['width']
            width = kwargs.get('width')
            height = kwargs.get('height')
            self.gen_thumbnails.add((path, width, height))
            fmt = get_format(path)
            if path.endswith(fmt):
                thumbpath = path
            else:
                thumbpath = path.rsplit('.', 1)[0] + '.' + fmt
            if width is None:
                return u'thumbnail/full/%s' % (thumbpath, )
            else:
                return u'thumbnail/%d/%d%s' % (width, height, thumbpath)
        if name == 'record-gallery':
            id = kwargs['id']
            offset = kwargs.get('offset', None)
            if offset is None:
                show = kwargs['show']
                offset = self.gallery_offset(id, show)
            self.gen_gallery.add((id, offset))
            return u'record/%s/gallery/%s.html' % (id, offset)
        if name == 'coll-view':
            collid = getparam('id', '', None, kwargs)
            tab = getparam('tab', None, None, kwargs)
            if tab is None:
                types_available, dates_available = self.types_in_collection(collid)
                coll = Collection.objects.get(collid)
                if coll is not None:
                    allowed_ancestors = self.allowed_ancestors(coll)
                    tab = self.coll_maintab(coll, types_available, dates_available,
                                            allowed_ancestors)
            if tab is None:
                tab = 'records'
            startrank = int(getparam('startrank', '0', None, kwargs))
            showfull = int(getparam('showfull', '0', None, kwargs))
            incsubs = int(getparam('incsubs', '0', None, kwargs))

            if tab not in ('records', 'images', 'video', 'audio', 'media'):
                startrank = 0
                showfull = 1
                incsubs = 1

            params = dict(id=collid, tab=tab, startrank=startrank,
                          incsubs=incsubs, showfull=showfull)
            key = tuple(sorted((k, tupleify(v)) for (k, v) in params.iteritems()))
            if key not in self.gen_colls:
                #print "ADDING", key
                #print '\n'.join(map(str, self.gen_colls))
                self.gen_colls.add(key)
                self.ungenerated_colls.add(key)
            if showfull:
                showfull = 'detail'
            else:
                showfull = 'list'
            if incsubs:
                incsubs = 'all'
            else:
                incsubs = 'coll'
            if startrank:
                startrank = 'from_%s' % startrank
            else:
                startrank = 'index'
            return u'coll/%s/%s/%s/%s/%s.html' % (collid, tab, showfull, incsubs, startrank)

        if name == 'search':
            try:
                del kwargs['act']
            except KeyError: pass

            if '*' in kwargs.get('collid', ()):
                del kwargs['collid']

            showfull = kwargs.get('showfull', ())
            if isinstance(showfull, int):
                pass
            elif len(showfull) > 0 and int(showfull[0]) == 0:
                showfull = 0
            else:
                showfull = 1
            kwargs['showfull'] = [showfull]

            startrank = kwargs.get('startrank', ())
            if isinstance(startrank, int):
                pass
            elif len(startrank) > 0:
                startrank = int(startrank[0])
            else:
                startrank = 0
            kwargs['startrank'] = [startrank]

            qs = kwargs.get('qs', ())
            newqs = []
            for qnum in qs:
                # If there aren't corresponding q%df items skip this one.
                qnum = int(qnum)
                qf = kwargs.get('q%df' % qnum)
                if qf is not None:
                    newqs.append(str(qnum))
            kwargs['qs'] = tuple(newqs)

            if not kwargs.get('ttypes'):
                kwargs['ttypes'] = ('record', )
            key = tuple(sorted((k, tupleify(v)) for (k, v) in kwargs.iteritems()))
            searchid = self.gen_searches.get(key, None)
            if searchid is None:
                searchid = self.gen_search_id(key)
                self.gen_searches[key] = searchid
                self.search_ids[searchid] = key
                self.ungenerated_searches.add(key)
            return u'search/%s.html' % (searchid, )

        if name == 'export-toppage':
            return u'index.html'

        print 'unhandled URL: ', repr(name), repr(args), repr(kwargs)
        return u'404.html'

    def gen_search_id(self, key):
        dictkey = dict(key)
        #print "Generating searchid for %r" % dictkey,
        searchid = []

        # First part of id is the collection
        collids = '_'.join(dictkey.get('collid', ()))
        if collids:
            searchid.append(collids)
        else:
            searchid.append('all')

        # Next part of id is the types
        ttypes = dictkey.get('ttypes')
        if ttypes is not None and len(ttypes) > 0:
            searchid.append('_'.join(sorted(ttypes)))
        else:
            searchid.append('all')

        # Next part of id is the search itself
        qs = dictkey.get('qs')
        if qs == ('1', ):
            # Add standard form of search
            q1f = dictkey.get('q1f')
            q1m = dictkey.get('q1m')
            if q1f and q1m:
                searchid.append(slugify(q1f[0].decode('utf8')).encode('utf8'))
                searchid.append(slugify(q1m[0].decode('utf8')).encode('utf8'))

        # Add showfull
        showfull = dictkey['showfull'][0]
        if showfull == 0:
            searchid.append('list')
        else:
            searchid.append('detail')

        # Add page id
        startrank = dictkey.get('startrank')
        if startrank is not None and len(startrank) > 0:
            startrank = int(startrank[0])
        else:
            startrank = 0
        if startrank == 0:
            searchid.append('index')
        else:
            searchid.append('from_%s' % startrank)

        searchid = '/'.join(searchid)

        if searchid is not None:
            # Check for any conflicting search (which could happen if we've
            # missed parameters).
            old = self.search_ids.get(searchid)
            if old is not None and old != key:
                searchid = None

        if searchid is None:
            # If we didn't generate an ID, generated a numeric ID.
            searchid = len(self.gen_searches) + 1

        #print "=%r" % searchid
        return searchid

    def setup_render(self):
        """Setup an environment for rendering.

        """
        self.loader = jinja2.FileSystemLoader(apps.templates.render.app_template_dirs(),
                                              encoding='utf-8')
        self.extensions = ['jinja2.ext.with_']
        myenv = jinja2.Environment(loader = self.loader,
                                   extensions = self.extensions,
                                   trim_blocks = True,
                                   autoescape = True,
                                   line_statement_prefix = "#")

        myenv.globals['thumbtype'] = thumbtype
        myenv.globals['thumbiconurl'] = self.thumbiconurl
        myenv.globals['thumbsize'] = thumbsize
        myenv.globals['imgsize'] = imgsize
        myenv.globals['url'] = self.url
        myenv.globals['lockedto'] = lambda : None

        myenv.filters = apps.templates.render.myenv.filters
        self.myenv = myenv

    def render(self, name, args, kwargs, template_name, context, mtime=None):
        """Render a template to a file.

        """
        filename = self.lookup_path(name, args, kwargs)
        self.top_relpath = '../' * filename.count('/')
        self.myenv.globals['STATIC_ASSETS_URL'] = self.top_relpath + 'static/'
        self.myenv.globals['MEDIA_BASE_URL'] = self.top_relpath + 'media?path='
        if self.frontpage:
            self.myenv.globals['FRONTPAGE_URL'] = self.top_relpath + self.frontpage
        template = self.myenv.get_template(template_name)
        content = template.render(context)
        self.addfile(filename, content, mtime)

    def write_record(self, record):
        context = dict(record=record)
        self.render('record-view', (), dict(id=record.id),
                    "export/html/record.html",
                    context, record.mtime)

    def gallery_offset(self, recordid, show):
        record = Record.objects.get(unicode(recordid))
        images = record.media('image')
        if show is not None:
            for num, image in enumerate(images):
                if image.src == show:
                    return num
        return 0

    def write_gallery(self, recordid, offset):
        record = Record.objects.get(unicode(recordid))
        images = record.media('image')
        context = dict(record=record, images=images, offset=offset)
        self.render('record-gallery', (), dict(id=recordid, offset=offset),
                    "export/html/record-gallery.html", context, record.mtime)

    def write_search(self, params):
        params = dict(params)
        stash = {}
        context = dict(stash=stash)
        searchparams = SearchParams(stash, params)
        search = Search(searchparams, url_fn=self.url)
        if self.collid is not None:
            search.restrict_to_collection(self.collid)
        search.add_to_context(context)
        context['showfull'] = int(getparam('showfull', '1', stash, params))
        self.render('search', (), params,
                    "export/html/search.html", context)

    def allowed_ancestors(self, coll):
        ancestor_objs = []
        for ancestor_obj in coll.ancestor_objs:
            if (self.collid == ancestor_obj.id or
                self.collid in ancestor_obj.ancestors):
                ancestor_objs.append(ancestor_obj)
        return ancestor_objs

    @staticmethod
    def types_in_collection(collid):
        q = SearchCollection.field.coll.is_or_is_descendant(collid)
        q = q.calc_occur('!', '').check_at_least(-1)
        q = q.calc_facet_count('date', result_limit=2)
        q = q[:0]
        return dict(q.info[0]['counts']), q.info[1]

    def coll_maintab(self, coll, types_available, dates_available,
                     allowed_ancestors):
        """Get the tab which should be the main tab for a collection.

        """
        tabs = self.tabs_for_collection(coll, types_available, dates_available, allowed_ancestors)
        if 'children' in tabs:
            return 'children'
        elif 'records' in tabs:
            return 'records'
        return tabs[0]

    def tabs_for_collection(self, coll, types_available, dates_available,
                            allowed_ancestors):
        cachekey = u'tabs_%s' % (coll.id)
        cached = self.cache.get(cachekey)
        if cached is not None:
            return cached
        tabs = []

        for page in coll.leading_tabs():
            tabs.append("x" + page.id)

        if allowed_ancestors:
            tabs.append('parents')
        #if 'r' in types_available:
        tabs.append("records")
        if coll.has_children:
            tabs.append('children')
        if 'image' in types_available:
            tabs.append("images")
        if 'video' in types_available:
            tabs.append("video")
        if 'audio' in types_available:
            tabs.append("audio")
        if 'media' in types_available:
            tabs.append("media")
        if dates_available['values_seen'] >= 1:
            tabs.append("calendar")
        tabs = tuple(tabs)
        self.cache[cachekey] = tabs
        return tabs

    def write_collection(self, params):
        params = dict(params)
        id = unicode(params['id'][0])
        del params['id']

        coll = Collection.objects.get(id)
        if coll is None:
            return
        if self.collid != id and self.collid not in coll.ancestors:
            return

        # Massive cut and paste follows
        def items_of_type(type, cons, order, incsubs, reverse, hpp):
            q = coll.items_from_search(type=type, incsubs=incsubs)

            if order != 'collection':
                q = q.order_by_multiple([])
                order_key = order
                if order.startswith('+'):
                    order_key, asc = order[1:], True
                elif order.startswith('-'):
                    order_key, asc = order[1:], False
                else:
                    order_key, asc = order, False
                q = q.order_by(order_key, asc)

            max_hpp = int(math.ceil(hpp * 1.25))
            items = q[startrank:startrank + max_hpp]
            if len(items) >= max_hpp:
                items = items[:hpp]
            return dict(coll_size=q.matches_estimated, items=items)

        stash = {}
        order = getparam('order', 'collection', stash, params)
        incsubs = int(getparam('incsubs', '1', stash, params))
        reverse = int(getparam('reverse', '0', stash, params))
        startrank = int(getparam('startrank', '0', stash, params))
        hpp = int(getparam('hpp', '100', stash, params))
        tab = getparam('tab', 'records', stash, params)

        # FIXME - do a faceted search to check which type tabs to show.
        types_available, dates_available = self.types_in_collection(id)
        allowed_ancestors = self.allowed_ancestors(coll)

        tabs = self.tabs_for_collection(coll, types_available, dates_available,
                                        allowed_ancestors)

        context = dict(
            stash = stash,
            tab = tab,
            tabs = tabs,
            startrank = startrank,
            coll = coll,
            incsubs = incsubs,
        )

        pagination_params = dict(
            hpp = hpp,
            order = order,
            reverse = reverse,
            showfull = int(getparam('showfull', '1', stash, params)),
        )

        if tab == 'parents':
            context['ancestor_objs'] = allowed_ancestors

        if tab == 'records':
            context.update(pagination_params)
            context.update(items_of_type('record', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'images':
            context.update(pagination_params)
            context.update(items_of_type('image', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'video':
            context.update(pagination_params)
            context.update(items_of_type('video', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'audio':
            context.update(pagination_params)
            context.update(items_of_type('audio', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'media':
            context.update(pagination_params)
            context.update(items_of_type('media', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'calendar':
            calstyle = getparam('calstyle', 'year', stash, params)
            if calstyle not in ('year', 'month', 'day'):
                calstyle = 'year'
            datefield = getparam('datefield', 'date', stash, params)

            startdate = getparam('startdate', '', stash, params)
            year = getparam('year', None, None, params)
            month = getparam('month', None, None, params)
            day = getparam('day', None, None, params)

            incsubs = True # FIXME - no UI to set at present
            context.update(calendar_items(id, incsubs, calstyle, startdate,
                                          year, month, day,
                                          datefield))
            stash['startdate'] = [context['startdate']]

        if tab == 'children':
            context['direct_records'] = items_of_type('record', lambda x: x, 'collection', 0, False, 10)

        if tab.startswith('x'):
            context['currpage'] = coll.page(tab[1:])

        params['id'] = id
        self.render('coll-view', (), params,
                    "export/html/coll-view.html", context)

    def make_media_view(self, mediafile):
        info = self.get_file_info(mediafile)
        assert info is not None # Should have already checked that file exists
            
        records = []
        q = SearchCollection.doc_type('record').field.fileid == mediafile
        for r in q[:100]:
            records.append(r.object)
        context = dict(info=info, records=records)
        self.render('mediapreview', (), dict(path=mediafile),
                    "export/html/media-view.html", context)

    def copy_media(self):
        make_copy = (self.incmedia == 'include')
        media_manifest = set()
        missing_media_manifest = set()

        size = len(self.gen_media)
        for count, mediafile in enumerate(sorted(self.gen_media), 1):
            yield "Handling media file %d of %d" % (count, size)
            media_path = media_mapper._map_path(mediafile)
            if media_path is None:
                missing_media_manifest.add(mediafile)
                continue
            if not os.path.exists(media_path):
                # FIXME - warn better.
                missing_media_manifest.add(mediafile)
                continue
            if make_copy:
                zippath = self.lookup_path('media', (), dict(path=mediafile))
                self.copyfile(media_path, zippath)
            media_manifest.add(mediafile)

            # Make media preview page
            self.make_media_view(mediafile)

        self.addfile('/manifests/media.txt',
                     '\n'.join(sorted(media_manifest)))
        self.addfile('/manifests/missing_media.txt',
                     '\n'.join(sorted(missing_media_manifest)))

    def make_thumbnails(self):
        count = 0
        size = len(self.gen_thumbnails)
        for path, width, height in sorted(self.gen_thumbnails):
            count += 1
            yield "Generating thumbnail %d of %d" % (count, size)
            media_path = media_mapper._map_path(path)
            if media_path is None:
                continue
            if not os.path.exists(media_path):
                # FIXME - warn better.
                continue
            thumbdata, thumbmime = thumbcache.get_data(media_path, width, height)
            assert width is not None
            zippath = self.lookup_path('thumbnail', (),
                dict(path=path, width=width, height=height))
            self.addfile(zippath, thumbdata)

    def export(self, tempdir):
        self.outpath = os.path.join(tempdir, 'export.zip')
        self.topdir = 'export' # Top directory name inside zip

        self.setup_render()

        # Map from raw paths to zippaths.
        self.rawpaths = {}

        # Used zippaths.
        self.zippaths = set()

        # Record IDs in the export
        self.record_ids = set()

        # Set of static resource files to copy.
        self.gen_static = set()

        # Set of media files to generate.
        # Key is the (externally visible) path to the media file.
        self.gen_media = set()

        # Set of record gallery pages to generate.
        # Key is tuple of (record-id, external media path).
        self.gen_gallery = set()

        # Registry of searches performed in export.
        self.gen_searches = {}

        # Mapping from search id to search (reverse of gen_searches)
        self.search_ids = {}

        # IDs of search pages which haven't been generated yet.
        self.ungenerated_searches = set()

        # Registry of thumbnails used in export.
        self.gen_thumbnails = set()

        # List of collections relevant to this export.
        self.gen_colls = set()
        self.ungenerated_colls = set()

        # Add some files which we always want
        for dirpath, dirnames, filenames in os.walk(config.staticdir):
            dirpath = dirpath[len(config.staticdir):].lstrip('/')
            for filename in filenames:
                if (filename.rsplit('.', 1)[-1] not in
                    (
                     'css', 'png', 'jpg', 'js', 'swf',
                    )):
                    continue
                fullpath = os.path.join(dirpath, filename)
                self.gen_static.add(fullpath)

        self.zfd = zipfile.ZipFile(self.outpath, "w", allowZip64=True)

        try:

            xmltree = etree.XML(u'<export/>')
            xmlrecords = etree.XML(u'<records/>')
            xmltree.append(xmlrecords)
            count = 0
            size = len(self.objs)
            while len(self.objs) > 0:
                count += 1
                yield "Formatting record %d of %d" % (count, size)
                record = self.objs.pop(0)
                self.write_record(record)
                self.record_ids.add(record.id)

                newroot = copy.deepcopy(record.root)
                if newroot.tail is None:
                    newroot.tail = '\n'
                else:
                    newroot.tail += '\n'
                xmlrecords.append(newroot)
                del newroot

            yield "Generating XML dump"
            xml_outpath = os.path.join(tempdir, 'export.xml')
            etree.ElementTree(xmltree).write(xml_outpath, encoding='utf-8',
                                               xml_declaration=True)
            del xmlrecords
            del xmltree
            self.copyfile(xml_outpath, '/manifests/data.xml')

            # Generate frontpage
            self.render('export-toppage', (), {},
                        'export/html/top-index.html', {})

            # Generate gallery pages
            count = 0
            size = len(self.gen_gallery)
            for recordid, offset in sorted(self.gen_gallery):
                count += 1
                yield "Generating gallery page %d of %d" % (count, size)
                self.write_gallery(recordid, offset)

            # Generate collection pages
            count = 0
            while len(self.ungenerated_colls) != 0:
                params = self.ungenerated_colls.pop()
                count += 1
                yield "Generating collection page %d; total known so far %d" % (
                    count, len(self.gen_colls))
                self.write_collection(params)

            # Generate search pages
            count = 0
            while len(self.ungenerated_searches) != 0:
                params = self.ungenerated_searches.pop()
                count += 1
                yield "Generating search page %d; total known so far %d" % (
                    count, len(self.gen_searches))
                self.write_search(params)

            # Copy the media files in.
            for item in self.copy_media():
                yield item

            # Make thumbnails.
            for item in self.make_thumbnails():
                yield item

            # Copy static files in.
            yield "Copying static files"
            for staticfile in sorted(self.gen_static):
                zippath = self.lookup_path('static', (staticfile, ), {})
                static_path = os.path.join(config.staticdir, staticfile)
                self.copyfile(static_path, zippath)

            # ZipFile always marks the files' attributes to be interpreted as
            # if they came from a Windows host. This interferes with some
            # software (namely unzip(1) from Info-Zip) from extracting
            # executables with the proper file attributes. So manually fix the
            # appropriate attributes on each of the ZipInfo's to specify the
            # host system as a UNIX.
            yield "Setting zipfile flags"
            for zinfo in self.zfd.filelist:
                zinfo.create_system = 3 # UNIX
        finally:
            self.zfd.close()
