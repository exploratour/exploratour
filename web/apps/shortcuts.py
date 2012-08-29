import cherrypy
import config
try:
    from simplejson import json
except ImportError:
    import json
import routes
import urllib
import re

def redirect(url, status=None):
    """Raise a redirect to the specified address.

    """
    raise cherrypy.HTTPRedirect(url, status)

def require_method(*allowed_methods):
    allowed_methods = list(allowed_methods)
    if "GET" in allowed_methods:
        if "HEAD" not in allowed_methods:
            allowed_methods.append("HEAD")
    allowed_methods.sort()
    if cherrypy.request.method not in allowed_methods:
        cherrypy.response.headers['Allow'] = ", ".join(allowed_methods)
        raise cherrypy.HTTPError(405)

def gonext():
    """Redirect to the url specified by the "next" parameter, if there is one.

    """
    next = cherrypy.request.params.get('next', '')
    if next != '':
        redirect(next)

def url(*args, **kwargs):
    """Get the url for a given route.

    """
    if len(args) == 0 and len(kwargs) == 0:
        return cherrypy.url()
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
    if len(args) > 0 and args[0] == 'static':
        return config.STATIC_ASSETS_URL + '/'.join(args[1:])
    return cherrypy.url(routes.url_for(*args, **newkwargs))

def queryparams(*args, **kwargs):
    """Encode a set of arguments as query parameters.

    """
    args = dict(args)
    args.update(kwargs)
    return urllib.urlencode(args)

def get_or_404(cls, id):
    try:
        return cls.objects.get(unicode(id))
    except KeyError:
        raise cherrypy.NotFound

def locked(fn):
    """Decorator to ensure that the mutex is locked while calling a method.

    The method's object must have a mutex in a property named "mutex".

    """
    def locked_method(self, *args, **kwargs):
        self.mutex.acquire()
        try:
            return fn(self, *args, **kwargs)
        finally:
            self.mutex.release()
    return locked_method

def get_user():
    from apps.store.models import User
    try:
        user = User.objects.get(u'_')
    except KeyError:
        user = User(None)
        user.id = u'_'
        User.objects.set(user)
    return user

def get_settings():
    from apps.store.models import Settings
    try:
        settings = Settings.objects.get(u'_')
    except KeyError:
        settings = Settings(None)
        settings.id = u'_'
        settings.set_roots(config.default_media_roots)
        Settings.objects.set(settings)
    return settings

def listify(val):
    """Convert a value, as found in cherrypy parameters, into a list.

    """
    if isinstance(val, basestring):
        return [val]
    if hasattr(val, '__iter__'):
        return list(val)
    return [val]

def listify_values(params):
    """Return a copy of a dict with values which were strings converted to
    lists.

    """
    return dict((k, listify(v)) for (k, v) in params.iteritems())

def getparam(name, default=None, stash=None, params=None):
    """Get a query parameter, in a nice standardised way, with some special
    handling for old and new values.

    The query parameter is always returned as a single item, or None if not
    supplied.  If supplied multiple times, one of the values is returned.

    """
    v = getparamlist(name, stash=stash, params=params)
    if len(v) > 0: return v[0]
    return default

def getintparam(name, default=None, stash=None, params=None):
    """Get a query parameter, in a nice standardised way, with some special
    handling for old and new values.

    The query parameter is always returned as a single integer item, or None if
    not supplied.  If supplied multiple times, one of the values is returned.

    """
    v = getparamlist(name, stash=stash, params=params)
    if len(v) > 0: return int(v[0])
    return default

def getparamlist(name, default=[], stash=None, params=None):
    """Get a query parameter, in a nice standardised way, with some special
    handling for old and new values.

    Returns a list of values.

    """
    if params is None:
        params = cherrypy.request.params
    v = params.get("new" + name, None)
    if v is None:
        v = params.get(name, None)
    if v is None:
        v = params.get("old" + name, None)

    if v is None:
        return default

    v = listify(v)
    if stash is not None:
        stash[str(name)] = v
    return v

def getorderparam(name):
    """Get the sequence of numbers stored in a parameter.

    The parameter should contain the numbers separated by commas.
    If invalid entries are found, raises an HTTP 400 error.

    """
    for num in cherrypy.request.params.get(name, '').split(','):
        if num.strip() == '':
            continue
        try:
            yield int(num)
        except ValueError:
            raise cherrypy.HTTPError(400)

def jsonresp(value):
    """Return a json formatted value, and set appropriate headers.

    """
    body = (json.dumps(value),)
    cherrypy.response.headers['Content-Type'] = 'application/json'
    return body

def slugify(value):
    import unicodedata
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s\.-]', '_', value).strip().lower())
    return re.sub('[-\s]+', '-', value)
