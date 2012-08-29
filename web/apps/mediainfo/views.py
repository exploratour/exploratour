from apps.thumbnail.thumbnail import mimetype, thumbtype, mimetypeurl
from apps.templates.render import render
from apps.store.search import Collection as SearchCollection
from apps.record.views import add_search_to_context
import cherrypy
from cherrypy.lib.static import serve_file
import datetime
import os
from apps.shortcuts import url, get_user, get_settings, jsonresp
import config
import copy

def isotime(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).isoformat()

class FsMapper(object):
    @property
    def _roots(self):
        return get_settings().get_roots()

    def known_root(self, root):
        """Return True iff the root supplied is known."""
        return root in self._roots

    def _map_path(self, public_path):
        """Map a public path to a path on the local filesystem.

        Returns None if no mapping found.

        """
        if len(public_path) == 0 or public_path[0] != '/':
            return None
        public_path = public_path[1:].split('/', 1)

        media_root = self._roots.get(public_path[0], None)
        if media_root is None:
            return None

        if len(public_path) == 1:
            result = media_root
        else:
            result = os.path.join(media_root, public_path[1])
        return result

    def is_hidden(self, public_path):
        """Check if a public path is a hidden path.

        """
        path = self._map_path(public_path)
        if path is None:
            return True
        return _local_is_hidden(path)

    def get_file_info(self, public_path):
        path = self._map_path(public_path)
        if path is None:
            raise cherrypy.HTTPError(404)

        filename = os.path.basename(public_path)
        mtype = mimetype(filename)

        type = thumbtype(path)
        turl = None
        summary = None
        if type == 'icon':
            turl = mimetypeurl(mtype)
        elif type == 'text':
            turl = mimetypeurl(mtype)
            fd = open(path)
            try:
                summary = fd.read(100) + '...'
            except IOError:
                pass
        else:
            turl = url("thumbnail", path=public_path)

        return dict(name=filename,
                    mimetype=mtype,
                    type=type,
                    thumburl=turl,
                    src=public_path,
                    summary=summary,
                    url=url("media", path=public_path),
                    size=os.path.getsize(path),
                    mtime=isotime(os.path.getmtime(path)),
                    hidden=_local_is_hidden(path),
                )

    def get_dir_info(self, public_path):
        path = self._map_path(public_path)
        if path is None:
            return {}

        return dict(name=os.path.basename(public_path),
                    mtime=isotime(os.path.getmtime(path)),
                    hidden=_local_is_hidden(path),
                )

    def exists(self, public_path):
        path = self._map_path(public_path)
        if path is None:
            return None
        return os.path.exists(path)

    def isfile(self, public_path):
        path = self._map_path(public_path)
        if path is None:
            return None
        return os.path.isfile(path)

    def isdir(self, public_path):
        if public_path == '/' :
            return '/'
        path = self._map_path(public_path)
        if path is None:
            return None
        return os.path.isdir(path)

    def listdir(self, public_path):
        if public_path == '/' :
            return tuple(sorted(self._roots.keys()))

        path = self._map_path(public_path)
        if path is None:
            []
        result = os.listdir(path)
        return result

mapper = FsMapper()

def _local_is_hidden(path):
    if os.name == 'nt':
        import win32file
        if win32file.GetFileAttributes(path) & win32file.FILE_ATTRIBUTE_HIDDEN:
            return True
    if os.path.basename(path).startswith('.'):
        return True
    return False

class MediaController(object):
    def media(self, path=''):
        if not path.startswith('/'):
            path = '/' + path
        mapped = mapper._map_path(path)
        if mapped is None:
            raise cherrypy.HTTPError(404)
        return serve_file(mapped)

    def mediapreview(self, path, **params):
        try:
            context = dict(path=path, info=mapper.get_file_info(path))
        except OSError:
            raise cherrypy.HTTPError(404)

        add_search_to_context(context)

        q = SearchCollection.doc_type('record').field.fileid == path
        records = []
        for r in q[:100]:
            records.append(r.object)
        # FIXME - handle more than 100 records matching
        
        context['records'] = records

        return render("media-view.html", context)

    def mediainfo(self, path='', mimepattern=None, hidden=0, exactpath=0):
        """Return information on the media at a given path.

        `path` is treated as a path prefix: information on all files in the
        specified directory which begin with the specified prefix is returned.

        Returned information is:
         - `path`: The value of path supplied (useful to tie the response to a
           request in an async environment).
         - `sep`: The path separator to use.
         - `dirpath`: The path of the directory holding `path`, with a
           separator at the end.
         - `parent`: The path of the parent directory of this path.
         - `dirs`: A list of the directories in dirpath with the appropriate
           prefix.  Entries in this are dicts containing:
            - `name`: The filename.
            - `mtime`: The modification time of the file
            - `hidden`: True iff the file is hidden.
         - `files`: A list of the files in dirpath with the appropriate
           prefix.  Entries in this are dicts containing:
            - `name`: The filename.
            - `type`: The type of the file.
            - `mtime`: The modification time of the file
            - `hidden`: True iff the file is hidden.

        If the path which would be contained in `dirpath` is not a directory,
        this will instead return a 404 error.

        """
        if exactpath:
            hidden=False
        if mimepattern:
            mimepattern = mimepattern.split('/', 1)
            if len(mimepattern) == 1 or mimepattern[1] == '*':
                mimepattern = [mimepattern[0], None]

        tmp = path.rsplit('/', 1)
        if len(tmp) == 1:
            tmp = (tmp[0], '')
        dirpath, fileprefix = tmp
        parentpath = dirpath.rsplit('/', 1)
        if len(parentpath) == 1:
            parentpath = ''
        else:
            parentpath = parentpath[0]
        if not parentpath.endswith('/'):
            parentpath += '/'
        if not dirpath.endswith('/'):
            dirpath += '/'

        files = []
        dirs = []
        if mapper.isdir(dirpath):
            user = get_user()
            user.set_info('media_lastdir', dirpath)
            user.objects.flush()
            for name in mapper.listdir(dirpath):
                if exactpath:
                    if name != fileprefix:
                        continue
                else:
                    if not name.startswith(fileprefix):
                        continue
                subpath = '/'.join((dirpath.rstrip('/'), name))
                if not hidden and mapper.is_hidden(subpath):
                    continue
                if mapper.isdir(subpath):
                    dirs.append(mapper.get_dir_info(subpath))
                elif mapper.isfile(subpath):
                    info = mapper.get_file_info(subpath)
                    if mimepattern is not None:
                        infomime = info['mimetype']
                        if infomime is None:
                            continue
                        infomime = infomime.split('/', 1)
                        if len(infomime) == 1:
                            infomime = [infomime[0], None]
                        if infomime[0] != mimepattern[0]:
                            continue
                        if mimepattern[1] is not None and \
                           infomime[1] != mimepattern[1]:
                            continue
                    files.append(info)
            dirs.sort(key=lambda x:x.get('name'))
            files.sort(key=lambda x:x.get('name'))

        response = dict(path=path, sep='/',
                        dirpath=dirpath,
                        parent=parentpath,
                        dirs=dirs, files=files)

        return jsonresp(response)
