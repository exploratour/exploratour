# Global configuration settings.

import os
import sys

# Generic settings
configdir = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
topdir = os.path.dirname(configdir)
if configdir.endswith('library.zip'):
    # Running from a frozen executable; put data in code dir.
    configdir = os.path.dirname(configdir)
    toprealdir = configdir
else:
    toprealdir = topdir
datadir = os.path.join(toprealdir, 'data')
logdir = os.path.join(datadir, 'logs')
storedir = os.path.join(datadir, 'store')
thumbcachedir = os.path.join(datadir, 'thumbnails')
tmpdir = os.path.join(datadir, 'tmp')
serversdir = os.path.join(configdir, "servers")

search_collection = 'exploratour'
search_url = 'http://127.0.0.1:7777'

# Settings related to the web interface
staticdir = os.path.join(topdir, 'web', 'static')
templatedir = os.path.join(topdir, 'web', 'templates')
STATIC_ASSETS_URL = '/static/'

# Hack for importing bamboo data
BAMBOO_MEDIA_PATH = os.path.join(topdir, 'media', 'naga')
BAMBOO_MEDIA_URL = 'http://bamdemo.lemurconsulting.com/bamdemo/db/naga/media/'

default_media_roots = {
    'media': os.path.join(topdir, 'media'),
}
if sys.platform == 'win32':
    default_media_roots.update({
        'c': 'c://',
        'd': 'd://',
        'e': 'e://',
        'f': 'f://',
        'g': 'g://',
    })
else:
    home = os.environ.get('HOME')
    default_media_roots.update({'home': home})

try:
    from local_config import *
except ImportError:
    pass
