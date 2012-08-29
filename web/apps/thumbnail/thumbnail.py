import config
import cherrypy
try:
    from PIL import Image
except ImportError:
    import Image
import hashlib
import threading
import mimetypes
import os
import re
import StringIO
from apps.shortcuts import locked

safename_re = re.compile(r'[^a-z0-9_-]')

def get_format(imgpath):
    format = os.path.splitext(imgpath)[1].lower()
    if format in ('.jpg', '.jpeg'):
        return 'jpeg'
    else:
        return 'png'

class ThumbCache(object):
    """A cache for thumbnails.

    """
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.thumb_sizes = {}
        self.mutex = threading.Lock()

    def _thumb_path(self, imgpath, width, height, format):
        """Get the path that a thumbnail should be stored in.

        """
        if width is None:
            return imgpath
        else:
            sizekey = "%dx%d" % (width, height)
        hash = hashlib.sha1(imgpath).hexdigest()
        thumbdir = os.path.join(self.cache_path, sizekey, hash[:1], hash[:2])
        try:
            os.makedirs(thumbdir)
        except OSError:
            pass
        thumbpath = os.path.join(thumbdir, hash + '.' + format)
        return thumbpath

    def _set_cached_size(self, key, size):
        if len(self.thumb_sizes) > 10000:
            self.thumb_sizes = {}
        self.thumb_sizes[key] = size

    def cache_uptodate(self, imgpath, thumbpath):
        """Check if the cache for an image is up to date.

        Raises OSError if the image can't be opened.

        """
        img_mtime = os.stat(imgpath).st_mtime
        try:
            thumb_mtime = os.stat(thumbpath).st_mtime
        except OSError:
            return False
        return img_mtime < thumb_mtime

    @locked
    def get_size(self, imgpath, width, height):
        """Get the size of a thumbnail of a file of given max dimension.

        """
        if imgpath is None:
            return None
        key = (imgpath, width, height)
        size = self.thumb_sizes.get(key, None)
        if size is not None:
            return size

        format = get_format(imgpath)
        thumbpath = self._thumb_path(imgpath, width, height, format)

        if self.cache_uptodate(imgpath, thumbpath):
            size = Image.open(thumbpath).size
            self._set_cached_size(key, size)
            return size

        img = Image.open(imgpath)
        if width is not None:
            self._make_thumbnail(img, width, height)

            tmppath = thumbpath[:-4] + '_tmp.' + format
            img.save(tmppath, format.upper())
            os.rename(tmppath, thumbpath)

        size = img.size
        self._set_cached_size(key, size)
        return size

    @staticmethod
    def _make_thumbnail(img, width, height):
        img.thumbnail((width, height), Image.ANTIALIAS)

    @locked
    def get_data(self, imgpath, width, height):
        """Get the data from a thumbnail.

        """
        key = (imgpath, width, height)
        format = get_format(imgpath)
        thumb_mimetype =  {'jpeg': 'image/jpeg', 'png': 'image/png'}[format]
        thumbpath = self._thumb_path(imgpath, width, height, format)

        if self.cache_uptodate(imgpath, thumbpath):
            fd = open(thumbpath, "rb")
            try:
                return fd.read(), thumb_mimetype
            finally:
                fd.close()

        img = Image.open(imgpath)
        if width is None:
            out = StringIO.StringIO()
            img.save(out, format.upper())
            out = out.getvalue()
            return out, thumb_mimetype
        self._make_thumbnail(img, width, height)
        self._set_cached_size(key, img.size)

        out = StringIO.StringIO()
        img.save(out, format.upper())
        out = out.getvalue()

        tmppath = thumbpath[:-4] + '_tmp.' + format
        fd = open(tmppath, "wb")
        try:
            fd.write(out)
        finally:
            fd.close()
        os.rename(tmppath, thumbpath)

        return out, thumb_mimetype

thumbcache = ThumbCache(config.thumbcachedir)

def thumbtype(public_path):
    """Get the type of thumbnail for a given file.

    Returns:
     - '' if the file doesn't exist, or is inaccessible.
     - 'icon' if the thumbnail is an icon.
     - 'text' if the thumbnail is a snippet of text.
     - 'image' if the thumbnail is an image.

    """
    if public_path is None:
        return ''
    from apps.mediainfo.views import mapper
    localpath = mapper._map_path(public_path)
    if localpath is None:
        return ''
    if not os.path.exists(localpath):
        return ''

    type, encoding = mimetypes.guess_type(localpath)

    if type is None:
        return 'icon'

    # Check if we can open it as an image.
    if type.startswith('image'):
        try:
            img = Image.open(localpath)
            img.load()
            return 'image'
        except IOError, e:
            pass
    elif type == 'text/plain':
        return 'text'

    return 'icon'

def mimetype(public_path):
    type, encoding = mimetypes.guess_type(public_path)
    if type is None or encoding is not None:
        return 'application/octet-stream'
    return type

def thumbiconurl(public_path):
    """Get the URL of an icon for filename.

    """
    return mimetypeurl(mimetype(public_path))

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
    return cherrypy.url('/'.join(('', 'static', 'icons', 'thumbs', iconname)))

def thumbsize(public_path, width, height):
    """Get the size of a thumbnail for the given maximum dimensions.

    """
    from apps.mediainfo.views import mapper
    try:
        return thumbcache.get_size(mapper._map_path(public_path), width, height)
    except OSError:
        return None

def imgsize(public_path):
    """Get the size of a image.

    """
    from apps.mediainfo.views import mapper
    try:
        return thumbcache.get_size(mapper._map_path(public_path), None, None)
    except OSError:
        return None
