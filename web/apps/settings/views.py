from apps.shortcuts import get_settings, redirect, url
from apps.store.models import Settings
from apps.templates.render import render
import cherrypy
import config

class SettingsController(object):
    def roots(self, **params):
        error = None
        if cherrypy.request.method == "POST":
            num = 0
            roots_dict = {}
            roots = []
            dupe_names = set()
            while True:
                name = params.get('rn%d' % num)
                path = params.get('rp%d' % num)
                num += 1
                if name is None or path is None:
                    break
                if name == '':
                    if path != '':
                        error = u'No name specified for path "%s"' % path
                else:
                    if path == '':
                        error = u'Empty path specified for name "%s"' % name
                if name == '' and path == '':
                    continue
                if name != '' and name in roots_dict:
                    dupe_names.add(name)
                path = path.strip()
                roots_dict[name] = path
                roots.append((num - 1, (name, path)))
            if dupe_names:
                if len(dupe_names) == 1:
                    error = u"Duplicated name: \"%s\"" % tuple(dupe_names)[0]
                else:
                    error = u"Duplicated names: \"%s\"" % u'\", \"'.join(sorted(dupe_names))
            if error is None:
                settings = get_settings()
                settings.set_roots(roots_dict)
                Settings.objects.set(settings)
                Settings.objects.flush()
                redirect(url("settings-roots"))
        else:
            roots_dict = get_settings().get_roots()
            if not roots_dict:
                roots_dict = config.default_media_roots
            roots = tuple(enumerate(sorted(roots_dict.items())))
        context = dict(
            error = error,
            roots = roots,
        )
        return render("settings/roots.html", context)
