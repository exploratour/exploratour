from apps.bgprocess import pool
from apps.lockto.utils import get_lockto_coll
from apps.record.errors import ValidationError
from apps.search.reindex import Reindexer
from apps.store.models import Collection, Record
from apps.store.search import Collection as SearchCollection
from apps.fields.fields import unflatten_name, field_item_types
from apps.templates.render import render
from apps.shortcuts import getparam, getintparam, getorderparam, getparamlist, jsonresp, redirect, url
from apps.search.models import SearchParams, Search
import cherrypy
from utils import highlight
import math
from restpose.query import And, Or

# Active reindex task, or None
reindexer_id = [None]

class SearchController(object):
    def search(self, **params):
        stash = {}
        context = dict(stash=stash)
        params = SearchParams(stash)
        search = Search(params)
        if not search.validate():
            # If the search doesn't validate, always go to the search entry
            # page.
            params.action = 'entry'
        search.add_to_context(context)
        context['showfull'] = int(getparam('showfull', '0', stash))

        if params.action == 'search':
            return render("search.html", context)
        elif params.action == 'select':
            return render("search_select.html", context)

        elif params.action.startswith('createcoll'):
            if cherrypy.request.method != "POST":
                return render("search_createcoll.html", context)
            subact = params.action[11:]

            parents = []
            for num in getorderparam('parent_order'):
                parent = getparam('parent%d' % num)
                if parent is None or parent == '':
                    continue
                if subact == ('del_parent_%d' % num):
                    continue
                parents.append(unicode(parent))
            if subact == 'add_parent':
                parents.append(u'')
            context['parents'] = tuple(enumerate(parents))
            context['allowable_parents'] = set(
                c.id for c in Collection.objects
            )
            context['collections'] = Collection.objects

            if subact == 'do':
                newtitle = getparam('create_colltitle', '')
                if len(newtitle) == 0:
                    context['error'] = "Cannot create collection with no title"
                    return render("search_createcoll.html", context)

                coll = Collection.find_by_title(newtitle)
                if len(coll) != 0:
                    context['error'] = "Collection with title %s already exists" % newtitle
                    return render("search_createcoll.html", context)

                coll = Collection(None, None, newtitle)
                Collection.objects.set(coll)
                # Have to set the collection before setting the parents, to get
                # an ID for the parents to refer back to.
                coll.set_parents(filter(lambda x: x != '', parents))
                Collection.objects.set(coll)
                Record.objects.flush()
                Collection.objects.flush()

                for record in search.query:
                    record = record.object
                    record.collections = record.collections + [coll.id]
                    Record.objects.set(record)
                Record.objects.flush()
                Collection.objects.flush()

                redirect(url("coll-view", id=coll.id))
            else:
                return render("search_createcoll.html", context)

        elif params.action == 'addtocoll':
            context['all_collections'] = Collection.objects
            if cherrypy.request.method != "POST":
                return render("search_addtocoll.html", context)

            newid = getparam('addto_collid', '')
            if len(newid) == 0:
                context['error'] = "Pick a collection to add to"
                return render("search_addtocoll.html", context)

            coll = Collection.objects.get(newid)
            for record in search.query:
                record = record.object
                record.collections = record.collections + [coll.id]
                Record.objects.set(record)
            Record.objects.flush()
            Collection.objects.flush()

            redirect(url("coll-view", id=coll.id))

            return render("search_addtocoll.html", context)

        elif params.action == 'removefromcoll':
            context['all_collections'] = Collection.objects
            if cherrypy.request.method != "POST":
                return render("search_removefromcoll.html", context)

            newid = getparam('removefrom_collid', '')
            if len(newid) == 0:
                context['error'] = "Pick a collection to remove from"
                return render("search_removefromcoll.html", context)

            coll = Collection.objects.get(newid)
            for record in search.query:
                record = record.object
                record.collections = tuple(filter(lambda x: x != coll.id,
                                                  record.collections))
                Record.objects.set(record)
            Record.objects.flush()
            Collection.objects.flush()

            redirect(url("coll-view", id=coll.id))

            return render("search_removefromcoll.html", context)

        else:
            context['all_collections'] = Collection.objects
            return render("search_entry.html", context)

    def ac(self, **params):
        """Autocomplete API.

        """
        field = params['field']
        term = params['term']
        colls = params['colls'].split(",")
        # FIXME - allow restricting search to a set of collections

        if field == '*':
            return jsonresp([])

        fieldname, fieldtype = field.rsplit('_', 1)
        fieldconfigs = SearchCollection.config['types'] \
            .get('record', {}) \
            .get('fields', {})

        if '*' in colls:
            target = SearchCollection.all()
        else:
            target = SearchCollection.field.coll.is_or_is_descendant(colls)

        return jsonresp(
            field_item_types[fieldtype]
            .autocomplete(target, fieldconfigs,
                          fieldname, term)
        )

    def reindex(self, **params):
        stash = {}
        if cherrypy.request.method == "POST":
            progress = pool.get_progress(reindexer_id[0])
            if progress.complete:
                reindexer_id[0] = pool.add_task(Reindexer())
                redirect(url("reindex"))

        context = dict(progress = pool.get_progress(reindexer_id[0]))
        return render("reindex.html", context)
