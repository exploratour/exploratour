import cherrypy

def get_lockto_collid():
    """Get the id of the collection we're locked to.

    """
    val = cherrypy.response.cookie.get('lockto')
    if val is not None:
        if val.value == '':
            return None
        return val.value.decode('utf8')

    val = cherrypy.request.cookie.get('lockto')
    if val is None or val.value == '':
        return None
    return val.value.decode('utf8')

def get_lockto_coll():
    """Get the collection we're locked to.

    """
    collid = get_lockto_collid()
    if collid is None:
        return None
    from apps.store.models import Collection
    try:
        return Collection.objects.get(collid)
    except KeyError:
        # Collection we're locked to has been deleted!
        unset_lockto_collid()
        return None

def set_lockto_collid(id):
    """Lock to a collection.

    """
    cherrypy.response.cookie['lockto'] = id.encode('utf8')
    cherrypy.response.cookie['lockto']['path'] = '/'
    cherrypy.response.cookie['lockto']['version'] = '1'

def unset_lockto_collid():
    """Remove the lock to a collection.

    """
    cherrypy.response.cookie['lockto'] = ''
    cherrypy.response.cookie['lockto']['path'] = '/'
    cherrypy.response.cookie['lockto']['version'] = '1'
    cherrypy.response.cookie['lockto']['expires'] = 0
