import config
import cherrypy
from apps.mediainfo.views import mapper
try:
    from PIL import Image
except ImportError:
    import Image
import StringIO
from apps.shortcuts import redirect, url
import os
from apps.thumbnail.thumbnail import thumbcache
import re
from cherrypy.lib.static import serve_file
import hashlib
import threading
from apps.shortcuts import locked

tile_re = re.compile('TileGroup(\d+)/(\d+)-(\d+)-(\d+).jpg')

class TileCache(object):
    """A cache for image tiles.

    """
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.mutex = threading.Lock()
        self.lastimg = None
        self.lastimgpath = None

    def _tile_path(self, imgpath, group, z, x, y):
        hash = hashlib.sha1(imgpath).hexdigest()
        tiledir = os.path.join(self.cache_path, "tiles", hash[:1], hash[:2],
                                "%s_%s" % (hash, str(group)))
        try:
            os.makedirs(tiledir)
        except OSError:
            pass
        return os.path.join(tiledir, "%d_%d_%d.jpg" % (z, x, y))

    def _get_img(self, imgpath):
        if imgpath == self.lastimgpath:
            return self.lastimg
        img = Image.open(imgpath)
        self.lastimg = img
        self.lastimgpath = imgpath
        return img

    @locked
    def get_cached_path(self, imgpath, group, z, x, y):
        tile_path = self._tile_path(imgpath, group, z, x, y)
        if os.path.exists(tile_path):
            return tile_path
        return None

    @locked
    def get_data(self, imgpath, group, z, x, y):
        tile_path = self._tile_path(imgpath, group, z, x, y)
        try:
            fd = open(tile_path, "rb")
            try:
                return fd.read()
            finally:
                fd.close()
        except IOError:
            pass

        img = self._get_img(imgpath)
        maxd = max(img.size)
        levels = 0
        while maxd > 256:
            maxd = int(maxd / 2)
            levels += 1
        zoom_factor = 2 ** (levels - z)
        boxsize = 256 * zoom_factor

        region = [x * boxsize,
                  y * boxsize,
                  (x + 1) * boxsize,
                  (y + 1) * boxsize]

        target = [256, 256]

        if region[2] > img.size[0]:
            overshoot = region[2] - img.size[0]
            target[0] = int(float(target[0]) * (boxsize - overshoot) / boxsize)
            region[2] = img.size[0]

        if region[3] > img.size[1]:
            overshoot = region[3] - img.size[1]
            target[1] = int(float(target[1]) * (boxsize - overshoot) / boxsize)
            region[3] = img.size[1]

        img = img.transform(tuple(target), Image.EXTENT, region, Image.BICUBIC)


        out = StringIO.StringIO()
        img.save(out, "JPEG")
        out = out.getvalue()

        tmppath = tile_path[:-4] + '_tmp.jpg'
        try:
            fd = open(tmppath, "wb")
            fd.write(out)
        finally:
            fd.close()
        os.rename(tmppath, tile_path)

        return out

tilecache = TileCache(config.thumbcachedir)

class ThumbnailController(object):
    def thumbnail(self, path, width=64, height=64):
        if not mapper.exists(path):
            redirect(url("/static/icons/thumbs/missing.png"))

        width = int(width)
        height = int(height)

        # Note - the path supplied is supplied as a query parameter, not as
        # part of the path info in the URL, because otherwise cherrypy strips
        # out any double slashes, making it impossible to tell if the path
        # starts with a drivename (on windows) or with an absolute path which
        # should have a / inserted before it (on unix).
        try:
            data, ctype = thumbcache.get_data(mapper._map_path(path), width, height)
            cherrypy.response.headers['Content-Type']= ctype
            return data
        except IOError:
            redirect(url("/static/icons/thumbs/broken.png"))

    def tile(self, path, tile):
        if not mapper.exists(path):
            raise cherrypy.HTTPError(404)

        mo = tile_re.match(tile)
        if not mo:
            raise cherrypy.HTTPError(404)

        group, z, x, y = map(lambda x: int(x), mo.groups())
        cached_path = tilecache.get_cached_path(mapper._map_path(path), group, z, x, y)
        if cached_path is not None:
            return serve_file(cached_path)

        data = tilecache.get_data(mapper._map_path(path), group, z, x, y)
        cherrypy.response.headers['Content-Type'] = 'image/jpeg'
        return data
