from apps.lockto.utils import get_lockto_coll, set_lockto_collid, unset_lockto_collid
from apps.store.models import Record, Collection, Template
from apps.store.search import Collection as SearchCollection
from apps.search.models import SearchParams, Search
from apps.shortcuts import (get_or_404, gonext, redirect, url,
                            json, queryparams)
from apps.shortcuts import getparam, getorderparam
from apps.templates.render import render

from calutils import calendar_items
import cherrypy
import copy
from lxml import etree
from apps.record.errors import ValidationError
from apps.record.parse_forms import RecordValidator, record_from_simple_request
import math

def handle_create_collection(params):
    newcoll_title = params.get('newcoll_title', u'').strip()
    if newcoll_title:
        if params.get('create'):
            id = create_collection(newcoll_title, ())
            remcoll = None
        else:
            remcoll = newcoll_title
        return json.loads(params.get('params')), remcoll
    return params, None

def record_from_request(id):
    params = cherrypy.request.params
    context = {}

    params, remcoll = handle_create_collection(params)
    validator = RecordValidator(params, remcoll)
    if validator.invalid_collections:
        return dict(invalid_collections=validator.invalid_collections)

    ok = True
    try:
        # FIXME - check csrf token
        record = validator.validate()
    except ValidationError, e:
        context['error'] = e.errormsg
        ok = False
        orig_record = get_or_404(Record, id)
        record = dict(inner_xml=params.get('inner_xml', None),
                      collections=validator.collections,
                      fieldnums=orig_record.fieldnums,
                      walkfields=orig_record.walkfields,
                      id=id,
                     )

    if ok and params.get('save', '') != '':
        Record.objects.set(record)
        Record.objects.flush()
        gonext()
        tmplid = params.get('tmplid', '')
        redirect(url("record-view", id=record.id, tmplid=tmplid))

    context['record'] = record

    return context

def tmpl_from_request(id, params):
    context = {}

    params, remcoll = handle_create_collection(params)
    validator = RecordValidator(params, remcoll)
    if validator.invalid_collections:
        return dict(invalid_collections=validator.invalid_collections)

    newid = params.get('newid')
    ok = True
    try:
        # FIXME - check csrf token
        record = validator.validate()
        tmpl = Template(newid, None, record)
    except ValidationError, e:
        context['error'] = e.errormsg
        ok = False
        orig_tmpl = get_or_404(Template, id)
        record = dict(inner_xml=params.get('inner_xml', None),
                      collections=validator.collections,
                      fieldnums=orig_tmpl.record.fieldnums,
                      walkfields=orig_tmpl.record.walkfields,
                     )
        tmpl = dict(record=record,
                    id=newid,
                   )

    if ok and params.get('save', '') != '':
        if not tmpl.id:
            context['error'] = "You must set an ID for the template"
        else:
            Template.objects.set(tmpl)
            Template.objects.flush()
            gonext()
            redirect(url("tmpl-view", id=tmpl.id))

    context['tmpl'] = tmpl

    return context

def coll_order_from_request():
    order = []
    ordering = []

    # Read collection order from request.
    for num in getorderparam('order'):
        field = getparam('field%d' % num)
        dir = getparam('dir%d' % num)
        if field is None or '_' not in field or dir is None:
            continue
        if getparam('del%d' % num) == '1':
            continue
        order.append((len(order), field, dir))
        ordering.append((field, dir))
    if getparam('add') == '1':
        order.append((len(order), '', ''))

    return order, ordering

def coll_parents_from_request():
    parents = []

    for num in getorderparam('order'):
        parent = getparam('parent%d' % num)
        if parent is None or parent == '':
            continue
        if getparam('del%d' % num) == '1':
            continue
        parents.append(unicode(parent))
    if getparam('add') == '1':
        parents.append(u'')

    return parents

def missing_collection(params, context):
    invalid_collections = context['invalid_collections']
    # Only do one missing collection at a time:
    invalid_collection = invalid_collections[0]
    context = dict(invalid_collection=invalid_collection,
                   path=cherrypy.request.path_info)
    return render("missing-collection.html", context)

def create_collection(title, parents):
    coll = Collection(None, None, title)
    Collection.objects.set(coll)
    if parents is not None:
        coll.set_parents(filter(lambda x: x != '', parents))
        # No descendents, so no need to reindex them to set the parents
        Collection.objects.set(coll)
    Collection.objects.flush()
    return coll.id

class RecordController(object):
    def create(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            context.update(record_from_request(None))
            if context.get('invalid_collections'):
                return missing_collection(params, context)

        if cherrypy.request.method == "GET":
            tmplid = params.get('tmplid', '')
            if tmplid == '':
                context['record'] = Record()
            else:
                context['record'] = get_or_404(Template, tmplid)

        return render("record-new.html", context)

    def edit(self, id, **params):
        context = {}

        ret = self._check_delete(id, 'record-edit')
        if ret is not None:
            return ret

        if cherrypy.request.method == "POST":
            context.update(record_from_request(id))
            if context.get('invalid_collections'):
                return missing_collection(params, context)
        elif cherrypy.request.method == "GET":
            context['record'] = get_or_404(Record, id)
        else:
            assert False

        return render("record-edit.html", context)

    def edit_fragment(self, **params):
        context = dict(record=record_from_simple_request(params))
        return render("record-edit-fragment.html", context)

    def copy(self, id, **params):
        record = copy.deepcopy(get_or_404(Record, id))
        del record.id
        Record.objects.set(record)
        Record.objects.flush()
        redirect(url("record-edit", id=record.id,
                     tmplid=params.get('tmplid', ''),
                     copyof=record.title))

    def delete(self, id, **params):
        ret = self._check_delete(id, 'record-delete')
        if ret is not None:
            return ret
        redirect(url("record-view", id=id, tmplid=params.get('tmplid')))

    def _check_delete(self, id, page):
        params = cherrypy.request.params
        if params.get('delete', '') != '':
            record = get_or_404(Record, id)
            context = dict(record=record, page=page)
            return render("record-delete-confirm.html", context)

        if cherrypy.request.method == "POST":
            if params.get('delete_conf', '') != '':
                record = get_or_404(Record, id)
                #print "Old collections", record.collections
                record.collections = ()
                # Set the record, to remove the collections 
                Record.objects.set(record)
                Record.objects.remove(id)
                Record.objects.flush()
                Collection.objects.flush()
                gonext()
                redirect(url("search", act='search'))

    def view(self, id, tmplid=None, **params):
        record = get_or_404(Record, id)
        context = dict(record=record, tmplid=tmplid)
        add_search_to_context(context)
        return render("record-view.html", context)

    def unframed(self, id, tmplid=None):
        record = get_or_404(Record, id)
        context = dict(record=record, tmplid=tmplid)
        return render("record-view-unframed.html", context)

    def gallery(self, id, show=None, offset=None):
        record = get_or_404(Record, id)
        images = record.media('image')
        if offset is None:
            offset = 0
            if show is not None:
                for num, image in enumerate(images):
                    if image.src == show:
                        offset = num
                        break
        else:
            offset = int(offset)
        context = dict(record=record, images=images, offset=offset)
        return render("record-gallery.html", context)

def add_search_to_context(context):
    stash = {}
    context['stash'] = stash
    params = SearchParams(stash)
    if params.search_in_progress:
        search = Search(params)
        search.add_to_context(context)

class TemplateController(object):
    def create(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            context.update(tmpl_from_request(id, params))
            if context.get('invalid_collections'):
                return missing_collection(params, context)

        elif cherrypy.request.method == "GET":
            context['tmpl'] = Template(u'', None, Record())
        else:
            assert False

        return render("tmpl-new.html", context)

    def edit(self, id, **params):
        context = {}

        ret = self._check_delete(id, 'tmpl-edit')
        if ret is not None:
            return ret

        if cherrypy.request.method == "POST":
            context.update(tmpl_from_request(id, params))
            if context.get('invalid_collections'):
                return missing_collection(params, context)
        elif cherrypy.request.method == "GET":
            context['tmpl'] = get_or_404(Template, id)
        else:
            assert False

        return render("tmpl-edit.html", context)

    def delete(self, id, **params):
        ret = self._check_delete(id, 'tmpl-delete')
        if ret is not None:
            return ret
        redirect(url("tmpl-view", id=id))

    def _check_delete(self, id, page):
        params = cherrypy.request.params
        if params.get('delete', '') != '':
            tmpl = get_or_404(Template, id)
            context = dict(tmpl=tmpl, page=page)
            return render("tmpl-delete-confirm.html", context)

        if cherrypy.request.method == "POST":
            if params.get('delete_conf', '') != '':
                try:
                    Template.objects.remove(id)
                    Template.objects.flush()
                except KeyError:
                    raise cherrypy.HTTPError(404)
                gonext()
                redirect(url("tmpls-list"))

    def view(self, id, **params):
        tmpl = get_or_404(Template, id)
        context = dict(tmpl=tmpl)
        add_search_to_context(context)
        return render("tmpl-view.html", context)

class CollectionController(object):
    def create(self, **params):
        context = {}

        if cherrypy.request.method == "POST":
            # FIXME - check csrf token
            title = params.get('newcoll_title', u'').strip()
            parents = coll_parents_from_request()
            if getparam('create'):
                if title:
                    id = create_collection(title, parents)
                    gonext()
                    redirect(url("colls-list", id=id))
                else:
                    context['error'] = "You must set a title for the collection"
        else:
            parents = []

        allowable_parents = set(
            c.id for c in Collection.objects
        )

        context.update(dict(
            parents = tuple(enumerate(parents)),
            allowable_parents = sorted(allowable_parents),
            collections = Collection.objects,
        ))

        return render("coll-new.html", context)

    def delete(self, id, **params):
        coll = get_or_404(Collection, id)
        if cherrypy.request.method == "POST":
            # FIXME - check csrf token
            if id:
                if params.get('delete_conf', '') == '':
                    redirect(url("colls-list"))

                coll = get_or_404(Collection, id)

                # Remove the collection's parents
                coll.set_parents(())
                Collection.objects.set(coll)

                # Remove the collection from its childrens parent lists.
                child_colls = coll.children
                for child in child_colls:
                    cparents = set(child.parents)
                    cparents.remove(id)
                    child.set_parents(cparents)
                    Collection.objects.set(child)

                # Iterate through the records in the collection, and remove the
                # collection from them.
                SearchCollection.checkpoint().wait()
                for record in SearchCollection.doc_type('record') \
                   .field.coll.is_in(id)[:]:
                    try:
                        record = record.object
                    except KeyError:
                        # Record is already gone - can't update it.
                        # (This shouldn't happen, but do this check for
                        # robustness.)
                        continue
                    record.collections = filter(lambda x: x != id, record.collections)
                    Record.objects.set(record)

                Collection.objects.remove(id)
                Record.objects.flush()
                Collection.objects.flush()
                gonext()
                redirect(url("colls-list", id=coll.id))
        elif cherrypy.request.method == "GET":
            context = dict(coll=coll)
            return render("coll-delete-confirm.html", context)

        raise cherrypy.HTTPError(404)

    def view(self, id, **params):
        coll = get_or_404(Collection, id)

        def types_in_collection(collid):
            q = SearchCollection.field.coll.is_or_is_descendant(collid)
            q = q.calc_occur('!', '').check_at_least(-1)
            q = q.calc_facet_count('date', result_limit=2)
            q = q[:0]
            return dict(q.info[0]['counts']), q.info[1]

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

        tabs = []

        # FIXME - do a faceted search to check which type tabs to show.
        types_available, dates_available = types_in_collection(id)

        for page in coll.leading_tabs():
            tabs.append("x" + page.id)

        if coll.parents:
            tabs.append('parents')
        #if 'r' in types_available:
        tabs.append("records")
        if coll.children:
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

        context = dict(
            stash = stash,
            tab = tab,
            tabs = tabs,
            startrank = startrank,
            hpp = hpp,
            coll = coll,
            order = order,
            incsubs = incsubs,
            reverse = reverse,
            showfull = int(getparam('showfull', '1', stash, params)),
        )

        if tab == 'records':
            context.update(items_of_type('record', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'images':
            context.update(items_of_type('image', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'video':
            context.update(items_of_type('video', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'audio':
            context.update(items_of_type('audio', lambda x: x, order, incsubs, reverse, hpp))
        if tab == 'media':
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

        if params.get('lockto', None) == 'set':
            set_lockto_collid(id)

        elif params.get('lockto', None) == 'unset':
            unset_lockto_collid()

        return render("coll-view.html", context)

    def reorder(self, id, **params):
        if getparam('cancel') == '1':
            redirect(url("coll-view", id=id))
        coll = get_or_404(Collection, id)

        context = {}
        if cherrypy.request.method == "POST":
            # FIXME - check csrf token

            order, ordering = coll_order_from_request()

            if getparam('submit') == '1':
                # save order
                coll.autoorder.ordering = ordering
                Collection.objects.set(coll)
                Collection.objects.flush()
                redirect(url("coll-view", id=id))
        else:
            order = []
            for field, dir in coll.autoorder.ordering:
                order.append((len(order), field, dir))

        if not order:
            order.append((0, '', ''))

        context['coll'] = coll
        context['collorder'] = order
        return render("coll-reorder.html", context)

    def reparent(self, id, **params):
        if getparam('cancel') == '1':
            redirect(url("coll-view", id=id))
        coll = get_or_404(Collection, id)

        if cherrypy.request.method == "POST":
            # FIXME - check csrf token

            title = getparam('title')
            parents = coll_parents_from_request()

            if getparam('submit') == '1':
                # Save parents
                changed = coll.set_parents(filter(lambda x: x != '', parents))
                if coll.title != title:
                    coll.title = title
                Collection.objects.set(coll)
                Collection.objects.flush()
                Record.objects.flush()
                redirect(url("coll-view", id=id))
        else:
            title = coll.title
            parents = []
            for parent in coll.parents:
                parents.append(parent)
        if not parents:
            parents.append('')

        not_allowed = set(coll.ancestors) - set(coll.parents)
        not_allowed.add(id)

        allowable_parents = set(
            c.id for c in Collection.objects
            if c.id != id and id not in c.ancestors
        )

        context = dict(
            title = title,
            coll = coll,
            parents = tuple(enumerate(parents)),
            allowable_parents = sorted(allowable_parents),
            collections = Collection.objects,
        )

        return render("coll-reparent.html", context)

class TemplatesController(object):
    def list(self, **params):
        context = dict(templates=Template.objects)
        return render("tmpls-list.html", context)

    def pick(self):
        context = dict(templates = Template.objects)
        return render("tmpls-pick.html", context)

class CollGroup(object):
    def __init__(self, id, title, collids=[]):
        self.id = id
        self.title = title
        self.collids = collids

    def collections(self):
        return map(lambda collid: Collection.objects.get(collid), self.collids)

class CollectionsController(object):

    def list(self, **params):
        coll = get_lockto_coll()
        if coll is not None:
            redirect(url("coll-view", id=coll.id))
        groups = [CollGroup(coll.id, coll.title, [coll.id])
                  for coll in Collection.objects if not coll.parents]
        groupid = getparam('groupid', '')
        filtered_groups = filter(lambda group: group.id == groupid, groups)
        if len(filtered_groups) > 0:
            currgroup = filtered_groups[0]
        elif len(groups) > 0:
            currgroup = groups[0]
        else:
            currgroup = None
        context = dict(groups=groups, currgroup=currgroup)
        return render("colls-list.html", context)
