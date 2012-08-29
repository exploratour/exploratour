import cherrypy
import config
import jinja2
import os
import urllib
import apps.autocomplete.views
from apps.lockto.utils import get_lockto_coll
from apps.shortcuts import url, get_user, json, listify_values
from apps.thumbnail.thumbnail import thumbtype, thumbiconurl, thumbsize, imgsize
import datetime


loader = jinja2.FileSystemLoader([config.templatedir], encoding='utf-8')
extensions = ['jinja2.ext.with_']
myenv = jinja2.Environment(loader=loader, extensions=extensions,
                           trim_blocks=True, autoescape=True,
                           line_statement_prefix="#")
myenv.globals['thumbtype'] = thumbtype
myenv.globals['thumbiconurl'] = thumbiconurl
myenv.globals['thumbsize'] = thumbsize
myenv.globals['imgsize'] = imgsize
myenv.globals['url'] = url
myenv.globals['STATIC_ASSETS_URL'] = config.STATIC_ASSETS_URL
myenv.globals['MEDIA_BASE_URL'] = '/media?path='
myenv.globals['ac'] = apps.autocomplete.views.autocomplete_context

myenv.globals['lockedto'] = get_lockto_coll

def qparams(params):
    """Format some parameters suitably for putting into a query string."""
    return urllib.urlencode(params, doseq=True)
myenv.globals['qparams'] = qparams

def jsval(value):
    """Format a value as json, and encode suitably for inserting into a script
    element.

    """
    assert not isinstance(value, jinja2.runtime.Undefined)
    value = json.dumps(value, indent=None)
    value = value.replace('<', '<"+"')
    return jinja2.utils.Markup(value)
myenv.filters['jsval'] = jsval

def jsvalattr(value):
    """Format a value as json, for use in an attribute value.

    """
    assert not isinstance(value, jinja2.runtime.Undefined)
    return json.dumps(value, indent=None, separators=(',', ':'))
myenv.filters['jsvalattr'] = jsvalattr

def fmtdatestamp(value, fmt="%Y%m%d"):
    return datetime.datetime.fromtimestamp(float(value)).strftime(fmt)
myenv.filters['fmtdatestamp'] = fmtdatestamp

def fmtdate(value):
    year, month, day = int(value[:4]), int(value[4:6]), int(value[6:8])
    return datetime.date(2000, month, day).strftime("%d %b ") + str(year)
myenv.filters['fmtdate'] = fmtdate

def titlefirst(value):
    """Put the first letter into uppercase.

    """
    if len(value) < 1:
        return value.upper()
    else:
        return value[0].upper() + value[1:]
myenv.filters['titlefirst'] = titlefirst

def basename(value):
    """Convert a path to the basename of the path.

    """
    return os.path.basename(value)
myenv.filters['basename'] = basename

myenv.filters['listify_values'] = listify_values

def render(template_name, context={}):
    """Render the template named in `template`.

    - `context` may be used to provide variables to the template.

    """
    template = myenv.get_template(template_name)
    context['user'] = get_user()
    context['path'] = cherrypy.request.path_info
    context['params'] = cherrypy.request.params
    return template.render(context)
