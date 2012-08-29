from apps.shortcuts import get_user
import cherrypy

class UserController(object):
    def lastdate(self, **params):
        user = get_user()
        if cherrypy.request.method == "GET":
            return user.get_info('lastdate', '')
        elif cherrypy.request.method == "POST":
            lastdate = cherrypy.request.params.get('lastdate')
            if lastdate:
                user.set_info('lastdate', lastdate)
            return '' 
        raise cherrypy.HTTPError(404)

