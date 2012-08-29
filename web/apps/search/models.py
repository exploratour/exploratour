from apps.lockto.utils import get_lockto_coll
from apps.fields.fields import unflatten_name, field_item_types
from apps.record.errors import ValidationError
from apps.shortcuts import getparam, getintparam, getparamlist, url
from apps.store.models import Collection
from apps.store.search import Collection as SearchCollection
import math
from restpose.query import And, Or
from restpose.errors import RestPoseError
import restkit
from utils import highlight

class SearchParams(object):
    """The parameters describing a search to be performed.

    """
    def __init__(self, stash=None, params=None):
        """Read the form parameters describing a search.

        Updates stash as appropriate, and returns an object with parameters as
        attributes.

        """
        self.stash = stash

        # First, get the search action.
        # No stash, since we don't want to repeat it.
        self.action = getparam('act', 'entry', params=params)
        if self.action in ('search', 'select'):
            # Except, we do stash the search and select actions.
            stash['act'] = [self.action]
            self.search_in_progress = True
        else:
            self.search_in_progress = False

        # Get the types to be searched.
        ttypes = getparam('ttypes', 'record', stash, params=params)
        if self.action == 'select':
            ttypes = 'record'
        self.ttypes = list(sorted(set(ttypes.split(','))))
        stash['ttypes'] = self.ttypes

        # Get the collections to search.
        self.colls = getparamlist('collid', [], stash, params=params)
        if len(self.colls) == 0:
            self.colls.append(u'*')
            stash['collid'] = self.colls

        # Handle modifications to the list of collections.
        if self.action == 'add_collection':
            self.colls.append(u'*')
            stash['collid'] = self.colls
            self.action = 'entry'
        if self.action.startswith('del_collection_'):
            num = int(self.action[len('del_collection_'):])
            del self.colls[num]
            stash['collid'] = self.colls
            self.action = 'entry'

        # Get the basic query.  This is for queries entered by users in a
        # single input box.
        self.q = getparam('q', None, stash, params=params)

        # Get the numbers of the components of the filter query.
        # First get the numbers of the components of the query.
        self.qsnums = filter(None, getparam('qs', '', stash, params=params).split(','))
        if len(self.qsnums) < 1:
            self.qsnums = [1]
        else:
            self.qsnums = list(map(lambda x: int(x), self.qsnums))
        # Handle modifications to the list of components of the filter query.
        if self.action == 'add_field':
            self.qsnums.append(max(self.qsnums) + 1)
            self.action = 'entry'
        if self.action.startswith('del_field_'):
            num = int(self.action[len('del_field_'):])
            del self.qsnums[num - 1]
            self.action = 'entry'
        # Stash the numbers of the components of the filter query.
        stash['qs'] = [','.join(map(lambda x: str(x), self.qsnums))]

        # Read the components of the query.
        self.fields = []
        for num in self.qsnums:
            prefix = 'q%d' % num
            param = getparam(prefix + 'f', None, stash, params=params)
            if param is None or param == u'':
                continue
            values = getparamlist(prefix + 'm', None, stash, params=params)

            if param == u'*':
                values = filter(lambda x: not((x is None) or (unicode(x).strip() in (u'', u'*'))), values)
                self.fields.append((num, u'*', u'*', values))
            else:
                field, type = param.rsplit('_', 1)
                field = unflatten_name(field)
                self.fields.append((num, type, field, values))

        # Get the order to return results in.
        order = getparam('order', 'score', stash, params=params)
        if order == 'score':
            self.order = 'score'
            self.order_asc = False
            self.order_field = None
        else:
            if order[0] in '+-':
                self.order = order
                self.order_asc = (self.order[0] == '+')
                self.order_field = self.order[1:]
            else:
                self.order = '+' + order
                self.order_asc = True
                self.order_field = self.order

        # Get the offsets within the search results.
        self.hpp = getintparam('hpp', 100, stash, params=params)
        self.startrank = getintparam('startrank', None, stash, params=params)
        self.rank = getintparam('rank', None, stash, params=params)

        # Ensure that the offsets are integers, aligned to pages.
        if self.startrank is None:
            if self.rank is None:
                self.startrank = self.rank = 0
            else:
                self.rank = int(self.rank)
                self.startrank = int(self.rank / self.hpp) * self.hpp
        else:
            self.startrank = int(int(self.startrank) / self.hpp) * self.hpp
            if self.rank is None:
                self.rank = self.startrank
            else:
                self.rank = int(self.rank)


class Search(object):
    """A search to be performed.

    """
    def __init__(self, params, url_fn=url):
        """Initialise the set of results.

        """
        #: The parameters used for the search.
        self.params = params

        #: Function used for making urls.  (Different one used for exports.)
        self.url_fn = url_fn

        #: Flag, True if query is empty, set when building the query.
        self._empty = True

        #: Words used (positively) in the query, for highlighting.
        self._words = []

        #: The query being performed.
        self._query = None

        #: Cached description of the whole query being performed.
        self._query_desc = None

        #: The base query being performed, unrestricted by document type.
        self._base_query = None

        #: Cached query for the collections being searched.
        self._coll_query = None

        #: Cached description of the collections being searched.
        self._coll_desc = None

        #: Cached query for the fields being searched.
        self._field_query = None

        #: Cached description of the fields being searched.
        self._field_desc = None

        #: Cached query restricted by collection lock.
        self._lockedto_query = None

        #: The types of objects matching the search (and their counts).
        self._matching_types = None

        #: The collections related to the search results.
        self._relevant_colls = None

        #: A list of result objects for the current page.
        self._resultlist = None

        #: Flag - true if previous and next result objects have been built.
        self._built_prevnext_result = False

        #: Cache of fields in the collections being searched.
        self._relevant_fields = None

        #: Highlighter used for building summaries.
        self._highlighter = highlight.Highlighter()

        self._restrict_coll = None

        self.error = None

        # The auto action runs a query if there is one, or goes to the search
        # entry page if there isn't.
        if self.params.action == 'auto':
            if self.empty:
                self.params.action = 'entry'
            else:
                self.params.action = 'search'
            self.params.stash['act'] = [self.params.action]

    def restrict_to_collection(self, collid):
        """Restrict the results of a search to those in a collection.

        """
        self._restrict_coll = collid

    def add_to_context(self, context):
        context['search'] = self
        if self.error is not None:
            context['error'] = str(self.error)

    def validate(self):
        """Check that the search parameters are valid."""
        try:
            list(self.base_query[:0])
            return True
        except ValidationError, e:
            self.error = e
            return False
        except RestPoseError, e:
            self.error = e
            return False
        except restkit.ResourceError, e:
            self.error = e
            return False
        except restkit.RequestError, e:
            self.error = e
            return False

    @property
    def hpp(self):
        """Hits per page"""
        return self.params.hpp

    @property
    def startrank(self):
        """Rank at the start of the current page."""
        return self.params.startrank

    @property
    def rank(self):
        """Rank of the current search result."""
        return self.params.rank

    @property
    def order(self):
        """Order of search results."""
        return self.params.order

    @property
    def resultlist(self):
        """Return a list of results for the query.

        Returns the results in the current page only.

        """
        if self._resultlist is None:
            self._build_resultlist()
        return self._resultlist

    @property
    def resultids(self):
        """Return a list of ids of items matching the query.

        Returns the results in the current page only.

        """
        if self._resultlist is None:
            self._build_resultlist()
        return self._resultids

    @property
    def needs_pagination(self):
        """Return True if the search has sufficient results to require
        pagination.

        """
        if self.params.startrank != 0:
            return True
        if self._resultlist is None:
            self._build_resultlist()
        return self._has_next_page

    @property
    def page_endrank(self):
        """The rank of the last result on the page.

        """
        return self.params.startrank + len(self.resultids) - 1

    @property
    def match_count(self):
        """The number of matching results.

        """
        if self._resultlist is None:
            self._build_resultlist()
        return self._match_count

    @property
    def prev_page_url(self):
        """Return URL of the previous page, or '' if on first page.

        """
        if self.params.startrank == 0:
            return ''
        return self.url_fn("search",
                           newstartrank=self.params.startrank - self.params.hpp,
                           **self.params.stash)

    @property
    def next_page_url(self):
        """Return URL of the next page, or '' if on last page.

        """
        if self._resultlist is None:
            self._build_resultlist()
        print "Search.next_page_url(): %r" % ((
        self.params.startrank,
        self.params.hpp,
        self.params.stash
        ),)
        if self._has_next_page:
            return self.url_fn("search",
                               newstartrank=self.params.startrank + self.params.hpp,
                               **self.params.stash)
        return ''

    @property
    def pagination_links(self):
        """A list of pagination links.

        Each item is a 3-tuple of (url, number, current):

         - url is the url of the link target
         - number is the page number of the link
         - current is a flag, True iff the page is the current page.

        """
        result = []
        pages = int(self.match_count / self.hpp) + 1
        slop = int(math.ceil(self.params.hpp * 1.25)) - self.params.hpp
        if self.match_count % self.params.hpp <= slop:
            pages -= 1
        for num in range(pages):
            result.append((self.url_fn("search",
                                       newstartrank = num * self.hpp,
                                       **self.params.stash),
                           num + 1,
                           num * self.hpp == self.startrank))
        return result

    def _build_resultobj(self, item):
        summary = []
        title = item.data.get('title', [''])[0]
        for k, v in item.data.iteritems():
            if k in ('mtime', 'type', ):
                continue
            for bit in v:
                bit = unicode(bit)
                if bit != title:
                    summary.append(bit.strip())
        summary = u' '.join(summary)
        item.summary = self._highlighter.makeSample(summary, self.words,
                                                    maxlen=300,
                                                    hl=[u'<b>', u'</b>'])
        return item

    def _build_resultlist(self):
        max_hpp = int(math.ceil(self.params.hpp * 1.25))
        search = self.query[self.params.startrank:
                            self.params.startrank + max_hpp] \
                .check_at_least(-1)
        self._match_count = search.matches_estimated
        if search.has_more:
            # If there are still more results after the slop, slice to remove
            # the slop.
            search=search[:self.params.hpp]
            self._has_next_page = True
        else:
            self._has_next_page = False

        resultlist = []
        resultids = []
        for item in search:
            resultids.append(item.data['id'][0])
            resultlist.append(self._build_resultobj(item))

        self._resultlist = resultlist
        self._resultids = resultids

    @property
    def prev_result(self):
        """Return a result object for the previous result, or None."""
        self._build_prevnext_result()
        return self._prev_result

    @property
    def next_result(self):
        """Return a result object for the next result, or None."""
        self._build_prevnext_result()
        return self._next_result

    def _build_prevnext_result(self):
        """Build result objects for the previous and next results.

        """
        if self._built_prevnext_result:
            return
        if self.params.rank > 0:
            search = self.query[self.params.rank - 1:
                                self.params.rank + 2] \
                     .check_at_least(-1)
            self._prev_result = self._build_resultobj(search[0])
            if len(search) > 2:
                self._next_result = self._build_resultobj(search[2])
            else:
                self._next_result = None
        else:
            search = self.query[self.params.rank:
                                self.params.rank + 2] \
                     .check_at_least(-1)
            self._prev_result = None
            if len(search) > 1:
                self._next_result = self._build_resultobj(search[1])
            else:
                self._next_result = None

        self._built_prevnext_result = True

    @property
    def relevant_collections(self):
        """A dict of the collections referred to by search results.

        (values are their counts).

        """
        if self._relevant_colls is None:
            self._relevant_colls = dict(self.base_query
                                        .calc_facet_count('coll')
                                        .check_at_least(-1)
                                        .info[0]['counts'])
        return self._relevant_colls

    @property
    def matching_types(self):
        """A dict of the matching types (values are their counts).

        """
        if self._matching_types is None:
            self._matching_types = dict(self.base_query
                                        .calc_facet_count('type')
                                        .check_at_least(-1)
                                        .info[0]['counts'])
        return self._matching_types

    @property
    def empty(self):
        """Boolean, True iff no query was supplied."""
        if self._base_query is None:
            self._build_base_query()
        return self._empty

    @property
    def words(self):
        """A list of words used in the query, for use in highlighting."""
        if self._base_query is None:
            self._build_base_query()
        return self._words

    @property
    def query(self):
        """The query being performed, including restrictions by return type.

        This query is based on the parameters, except that the range of
        documents to return has not been restricted.

        """
        if self._query is None:
            assert len(self.params.ttypes) == 1
            type_filter = \
                SearchCollection.field('type') == self.params.ttypes[0]
            self._query = self.base_query.filter(type_filter)
            if self.params.order_field:
                self._query = self._query.order_by(self.params.order_field, self.params.order_asc)
        return self._query

    @property
    def query_desc(self):
        """A string describing the query."""
        if self._base_query is None:
            self._build_base_query()
        return self._query_desc

    @property
    def base_query(self):
        """The base query being performed; without restricting by return type.

        """
        if self._base_query is None:
            self._build_base_query()
        return self._base_query

    @property
    def locked_out_result_count(self):
        """The number of results which are excluded from query due to the lock.

        """
        self.base_query
        if self._lockedto_excluded_count is None:
            assert len(self.params.ttypes) == 1
            type_filter = \
                SearchCollection.field('type') == self.params.ttypes[0]
            self._lockedto_excluded_count = \
                self._lockedto_excluded_query.filter(type_filter) \
                .check_at_least(-1)[:0].matches_estimated
        return self._lockedto_excluded_count

    @property
    def coll_query(self):
        """A query matching items in the set of collections being searched.

        """
        if self._coll_query is None:
            self._build_coll_query()
        return self._coll_query

    @property
    def coll_desc(self):
        """A string describing the set of collections."""
        if self._coll_query is None:
            self._build_coll_query()
        return self._coll_desc

    @property
    def field_query(self):
        """A query matching the fielded part of the search.

        """
        if self._field_desc is None:
            self._build_field_query()
        return self._field_query

    @property
    def field_desc(self):
        """A string describing the fielded part of the search.

        """
        if self._field_desc is None:
            self._build_field_query()
        return self._field_desc

    @property
    def relevant_fields(self):
        if self._relevant_fields is None:
            q = self.coll_query
            lockedto = get_lockto_coll()
            if lockedto is not None:
                q = q.filter(SearchCollection.field.coll
                             .is_or_is_descendant(lockedto.id))
            if self._restrict_coll is not None:
                q = q.filter(SearchCollection.field.coll
                             .is_or_is_descendant(self._restrict_coll))
            self._relevant_fields = fields_from_search(q)
        return self._relevant_fields

    def _build_base_query(self):
        """Build the query (and description).

        """
        desc = []

        # Get base query.
        if self.params.q is None:
            q = SearchCollection.all()
            desc.append('Searched')
        else:
            desc.append('Searched for "%s"' % self.params.q)
            q = SearchCollection.field.text.text(self.params.q, op="or")
            self._empty = False

        # Get fielded query.
        if self.field_query is not None:
            desc.append(' where ')
            desc.extend(self.field_desc)
            q = q & self.field_query

        # Restrict to the relevant collections
        q = q.filter(self.coll_query)
        desc.append(' in ' + self.coll_desc)

        if self._restrict_coll is not None:
            q = q.filter(SearchCollection.field.coll
                         .is_or_is_descendant(self._restrict_coll))

        # Restrict to the locked collection.
        lockedto = get_lockto_coll()
        if lockedto is None:
            self._lockedto_excluded_query = None
            self._lockedto_excluded_count = 0
        else:
            lockedto_coll_q = SearchCollection.field.coll \
                              .is_or_is_descendant(lockedto.id)
            self._lockedto_excluded_query = q - lockedto_coll_q
            self._lockedto_excluded_count = None
            q = q.filter(lockedto_coll_q)

        self._base_query = q
        self._query_desc = ''.join(desc)

    @staticmethod
    def single_coll_query(coll):
        if coll == '-*':
            coll_q = SearchCollection.all() - SearchCollection.field.coll.nonempty()
            desc = 'no collection'
        else:
            coll_obj = Collection.objects.get(coll)
            if len(coll_obj.children) > 0:
                desc = 'collection %s (and sub-collections)' % \
                        (coll_obj.title)
            else:
                desc = 'collection %s' % coll_obj.title
            coll_q = SearchCollection.field.coll.is_or_is_descendant(coll)

        return coll_q, desc

    def _build_coll_query(self):
        """Build the collection query (and description).

        """
        desc = []
        if '*' in self.params.colls:
            coll_q = SearchCollection.all()
            coll_list = list(Collection.objects)
            desc.append('all collections')
        elif len(self.params.colls) == 1:
            coll_q, subdesc = self.single_coll_query(self.params.colls[0])
            desc.append(subdesc)
        else:
            coll_list = []
            collfilters = []
            desc.append('collections ')
            for num, coll in enumerate(self.params.colls):
                if coll == '-*':
                    coll_q = SearchCollection.all() - SearchCollection.field.coll.nonempty()
                    desc.append("[no collection]")
                else:
                    coll_obj = Collection.objects.get(coll)
                    desc.append(coll_obj.title)
                    coll_list.append(coll_obj)
                if num == len(self.params.colls) - 1:
                    desc.append(" ")
                elif num == len(self.params.colls) - 2:
                    desc.append(" and ")
                else:
                    desc.append(", ")

                collfilters.append(SearchCollection.field.coll
                                   .is_or_is_descendant(coll))
            for coll_obj in coll_list:
                if len(coll_obj.children) != 0:
                    desc.append(" (and their children)")
                    break
            coll_q = Or(*collfilters)

        self._coll_query = coll_q
        self._coll_desc = ''.join(desc)

    def _add_words(self, text):
        """Add words used in the query from a piece of text.

        These words will be returned by the "words" property.

        """
        self._words.extend(filter(None, map(lambda x: x.strip(), text.split())))

    def _build_field_query(self):
        """Build the field query (and description).

        """
        desc = []
        f = {}
        for num, type, field, values in self.params.fields:
            fqs = []
            if field == u'*':
                # A search across all fields
                if len(values) == 0:
                    desc.append('any content exists')
                else:
                    desc.append('any field matches ' + ' or '.join(values))
                for value in values:
                    self._add_words(value)
                    newfq = SearchCollection.field.text.text(value, op="or")
                    fqs.append(newfq)
            else:
                # A search across a specific field
                if values is None:
                    values = ()
                for value in values:
                    self._add_words(value)
                    newfq, newdesc = field_item_types[type] \
                        .search_from_params(SearchCollection, field, value)
                    desc.append(newdesc)
                    fqs.append(newfq)
            if len(fqs) == 1:
                f[num] = fqs[0]
            elif len(fqs) > 1:
                f[num] = Or(fqs)

        # For now, we just combine all fields with And.
        # In future, we should allow users to control how they want fields to be
        # combined.
        self._field_desc = ', '.join(desc)
        if len(f) == 0:
            self._field_query = None
        else:
            self._field_query = And(*(f.values()))

def fields_from_search(search):
    """Calculate the fields which are used in records matching a search.

    Note: assumes any lockto collection has already been applied to the search.

    Returns a list of (field, types) tuples, where types is a list of (type,
    count) tuples.

    """
    try:
        search = search.check_at_least(-1)[:0].calc_facet_count('_meta')
        fields = {}
        for name, count in search.info[0]['counts']:
            if not name.startswith('F'):
                continue
            if '_' not in name:
                continue
            name, type = name[1:].rsplit('_', 1)
            if type == 'error':
                continue
            fields.setdefault(name, []).append((type, count))
        fields = list(fields.items())
        fields.sort()
        return fields
    except RestPoseError, e:
        return []
    except restkit.ResourceError, e:
        return []
    except restkit.RequestError, e:
        return []
