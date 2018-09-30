# The objects which are stored in exploratour

import copy
from lxml import etree
try:
    from simplejson import json
except ImportError:
    import json
from apps.fields import fields
from apps.record.errors import ValidationError
from apps.thumbnail.thumbnail import thumbsize
import cgi
import utils.parsedate

inner_html = fields.inner_html
fileicon_class = fields.fileicon_class

import re
def safeid(value):
    def repl(x):
        return '%' + hex(ord(x.groups()[0]))[2:]
    return re.sub('([^\w\s-])', repl, value)

class LazyXmlObject(object):
    """An XML object, which lazily converts itself between a parsed
    representation, and a serialised XML representation.

    """
    def __init__(self, roottag, xml, root):
        assert xml is None or root is None
        if xml is None and root is None:
            xml = u'<%s></%s>' % (roottag, roottag)
        self.__xml = xml
        self.__root = root

    @property
    def root(self):
        if self.__root is None:
            self.__root = etree.fromstring(self.__xml)
            self.__xml = None
        return self.__root
    @root.setter
    def root(self, value):
        self.__root = value
        self.__xml = None

    @property
    def xml(self):
        if self.__xml is None:
            self.__xml = etree.tounicode(self.__root)
            self.__root = None
        return self.__xml
    @xml.setter
    def xml(self, value):
        self.__xml = value
        self.__root = None

    @property
    def id(self):
        thisid = self.root.get(u'id')
        if thisid is None:
            return None
        return unicode(thisid)
    @id.setter
    def id(self, value):
        if value is None:
            del self.id
            return
        assert isinstance(value, unicode)
        self.root.set(u'id', value)
    @id.deleter
    def id(self):
        if 'id' in self.root.attrib:
            del self.root.attrib['id']

    @property
    def mtime(self):
        thismtime = self.root.get(u'mtime')
        if thismtime is None:
            return None
        return float(thismtime)
    @mtime.setter
    def mtime(self, value):
        if value is None:
            del self.mtime
            return
        assert isinstance(value, float)
        self.root.set(u'mtime', repr(value))
    @mtime.deleter
    def mtime(self):
        if 'mtime' in self.root.attrib:
            del self.root.attrib['mtime']


class ParsedRecord(object):
    def __init__(self, id, mtime, contents, coll_ids):
        assert id is None or isinstance(id, unicode), repr(id)
        assert mtime is None or isinstance(mtime, float), repr(mtime)
        self.id = id
        self.mtime = mtime
        self.contents = contents
        self.coll_ids = coll_ids

    def get_elt(self):
        root = etree.Element(u'record')
        if self.id is not None:
            root.set('id', self.id)
        if self.mtime is not None:
            root.set('mtime', repr(self.mtime))
        for item in self.contents:
            subelt = item.get_elt(2)
            root.append(subelt)

        for coll_id in self.coll_ids:
            assert isinstance(coll_id, unicode)
            elt = etree.SubElement(root, u'collection')
            elt.set(u'name', coll_id)

        return root

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        self.id = record_id_map.get(self.id, self.id)
        for item in self.contents:
            item.apply_mappings(record_id_map, coll_id_map, media_root_mappings)
        self.coll_ids = [coll_id_map.get(coll_id, coll_id)
                         for coll_id in self.coll_ids]

    def __str__(self):
        return "ParsedRecord(id=%r, mtime=%r, contents=%r, coll_ids=%r)" % \
                (self.id, self.mtime, self.contents, self.coll_ids)


class Record(LazyXmlObject):
    def __init__(self, xml=None, root=None):
        LazyXmlObject.__init__(self, "record", xml, root)

    def inner_elements(self):
        for elt in self.root:
            if elt.tag != u'collection':
                yield elt

    @property
    def inner_xml(self):
        xml = []
        for elt in self.inner_elements():
            xml.append(etree.tounicode(elt).strip())
        return u'\n'.join(xml)
    @inner_xml.setter
    def inner_xml(self, value):
        assert isinstance(value, unicode)
        #print "WAS", self.id, self.collections
        newxml = u'<record>%s</record>' % (value.strip(),)
        newroot = etree.fromstring(newxml)
        if self.id is not None:
            newroot.set(u'id', self.id)
        if self.mtime is not None:
            newroot.set(u'mtime', repr(self.mtime))
        for collection in self.collections:
            #print collection
            elt = etree.SubElement(newroot, u'collection')
            elt.set(u'name', collection)
        self.root = newroot
        #print "SET TO", self.id, self.collections

    @property
    def title(self):
        """Get a title for the record.

        """
        summary = []
        for item in self.walkfields():
            if item.closing or item.tag != 'field':
                continue
            if not hasattr(item, 'summary'):
                continue
            text = item.summary
            if text:
                text = text.strip()
            if text:
                if item.type == 'title':
                    # If we have an unambiguous title field, just return it.
                    return text
                summary.append(text)

        summary = (' '.join(summary)).strip()
        if len(summary) > 40:
            summary = summary[:40] + '...'
        if summary == '':
            summary = "Record %s" % self.id
        return summary

    def summary(self, maxlen=40):
        summary = []
        for item in self.walkfields():
            if item.closing or item.tag != 'field':
                continue
            if item.type == 'title':
                continue
            if not hasattr(item, 'summary'):
                continue
            text = item.summary
            if text:
                text = text.strip()
            if text:
                summary.append(text)

        summary = (' '.join(summary)).strip()
        if len(summary) > maxlen:
            summary = summary[:maxlen] + '...'
        if summary == '':
            summary = "Record %s" % self.id
        return summary

    def walkfields(self, startcount=1):
        """Iterate through the fields in the record.

        """
        count = int(startcount)
        names = []
        stack = []
        for event, elt in etree.iterwalk(self.root, events=("start", "end")):
            tag = elt.tag
            if tag in (u'field', u'group'):
                try:
                    if event == 'start':
                        names.append(elt.get('name') or '')
                        item = fields.RecordItem_from_element(elt, tag, names, count, False)
                        stack.append(count);
                    elif event == 'end':
                        item = fields.RecordItem_from_element(elt, tag, names, stack.pop(), True)
                        names.pop()
                except ValidationError:
                    continue
                if item is not None:
                    yield item
                    count += 1

    def parse(self):
        contents = fields.build_from_elt(elt for elt in self.root
                                       if elt.tag in ('field', 'group'))
        return ParsedRecord(self.id, self.mtime, contents, self.collections)

    def fieldnums(self):
        return ','.join("%d" % field.count for field in self.walkfields()
                        if field.count is not None)

    @property
    def collections(self):
        return [unicode(coll.get(u'name'))
                for coll in self.root.iter(u'collection')]
    @collections.setter
    def collections(self, collections):
        collections = set(collections)
        collection_objs = []
        for collid in collections:
            try:
                collection_objs.append(Collection.objects.get(collid))
            except KeyError:
                pass
        collection_objs.sort(key = lambda x: (x.title, x.id))
        #for collection_obj in collection_objs:
        #    print repr((collection_obj.title, collection_obj.id))

        for elt in self.root.findall(u'collection'):
            self.root.remove(elt)
        for collection_obj in collection_objs:
            collection = collection_obj.id
            assert isinstance(collection, unicode)
            elt = etree.SubElement(self.root, u'collection')
            elt.set(u'name', collection)

    @property
    def collection_objs(self):
        result = []
        for collid in self.collections:
            result.append(Collection.objects.get(collid))
        return result

    @property
    def ancestor_collections(self):
        seen = set()
        result = []
        for coll in self.collections:
            seen.add(coll)
            result.append(coll)

        for coll in self.collections:
            try:
                for acoll in Collection.objects.get(coll).ancestors:
                    if acoll not in seen:
                        seen.add(acoll)
                        result.append(acoll)
            except KeyError:
                pass # Can get KeyError if some of the ancestors don't exist - this would need to be fixed, but failing here would make it impossible for the user to fix it.
        return result

    def media(self, mimetype):
        result = []
        files_seen = set()
        for field in self.walkfields():
            if field.closing:
                continue
            for media in field.media():
                if media.mimetype is None:
                    continue
                if mimetype is not None and \
                   media.mimetype != mimetype and \
                   media.mimetype.split('/', 1)[0] != mimetype:
                    continue
                if media.src in files_seen:
                    continue
                files_seen.add(media.src)
                result.append(media)
        return result

    def searchdocs(self):
        def add_first_date(doc):
            first_date = None
            for fieldname, vals in doc.iteritems():
                if fieldname.endswith('_date') and len(vals) > 0:
                    for val in vals:
                        date, err = utils.parsedate.parse_date(val)
                    if date is None:
                        continue
                    if first_date is None or date.start < first_date:
                        first_date = date.start
            if first_date is not None:
                doc['date'] = str(first_date)

        maindoc = dict(
            type = 'record',
            id = safeid(self.id),
            mtime = self.mtime,
            coll = self.collections,
            title = self.title,
            text = [],
        )

        subsidiary_docs = []

        for field in self.walkfields():
            if field.closing:
                continue
            flat = field.flatten()
            if flat is None:
                continue
            for item in flat:
                if isinstance(item, dict):
                    item['id'] = safeid(self.id) + '_' + safeid(item['id'])
                    item['parent'] = safeid(self.id)
                    subsidiary_docs.append(item)
                    continue
                flatfield, flatval = item
                vals = maindoc.setdefault(flatfield, [])
                vals.append(flatval)
                maindoc['text'].append(unicode(flatval))
        add_first_date(maindoc)

        base_media = dict(
            coll = self.collections,
            title = self.title,
            mtime = self.mtime,
            text = maindoc.get('text', []),
        )
        for item in subsidiary_docs:
            item.update(base_media)
            yield item

        # FIXME - make document searchable by the titles of each ancestor
        # collection.

        yield maindoc

    def position_in(self, coll):
        """Get the ids of the previous and next records according to the named
        collection.

        """
        from apps.store.search import Collection as SearchCollection
        q = SearchCollection.doc_type('record').field.coll.is_in(coll.id)
        for name, asc in coll.autoorder.ordering:
            asc = {'+': True, '-': False}[asc]
            q = q.order_by(name, asc)
        r = [(r.data['id'][0], r.rank) for r in q.fromdoc('record', self.id, -1, 3)]
        if len(r) == 0:
            return dict(pos=0, size=0)

        if r[0][0] == self.id:
            index = 0
        elif len(r) == 1:
            return dict(pos=0, size=0)
        else:
            index = 1

        rank = r[index][1]
        result = dict(pos=rank + 1, size=len(q))
        if index > 0:
            result['prev'] = r[index - 1][0]
        if index + 1 < len(r):
            result['next'] = r[index + 1][0]
        return result

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        parsed = self.parse()
        parsed.apply_mappings(record_id_map, coll_id_map, media_root_mappings)
        self.root = parsed.get_elt()


class AutoOrder(object):
    """A list of fields and directions to order by automatically."""
    def __init__(self, ordering):
        if isinstance(ordering, AutoOrder):
            self.ordering = list(ordering.ordering)
        else:
            self.ordering = list(ordering)

    @staticmethod
    def fromxml(root):
        ordering = []
        if root is None:
            return AutoOrder(ordering)
        for elt in root:
            if elt.tag == u'field':
                dir = elt.get(u'dir')
                name = unicode(elt.get(u'name'))
                ordering.append((name, dir))
        return AutoOrder(ordering)

    def toxml(self, rootname):
        root = etree.Element(rootname)
        for name, dir in self.ordering:
            root.append(etree.Element(u"field", name=name, dir=dir))
        return root

    def __cmp__(self, other):
        return cmp(self.ordering, other.ordering)


class CollectionPage(object):
    """Extra page for a Collection."""


    _datatype_pattern = etree.XPath("descendant-or-self::*[@data-type]")

    def __init__(self, id, title, contents, tab_position):
        """ id - The id of the tab. (text, used in urls, unique to a collection)
        title - The title of the tab (ie, the text used in the tab)
        contents - The contents of the tab.  A unicode string, containing html
        markup.
        tab_position - None if not a tab.  Otherwise, a number indicating the
        position; lowest number tab will be displayed leftmost.
        """
        self.id = id
        self.title = title
        self.contents = contents
        self.tab_position = tab_position

    @staticmethod
    def fromxml(elt):
        id = unicode(elt.get(u'id'))
        title = unicode(elt.get(u'title'))
        contents = inner_html(elt)
        tab_position = elt.get(u'tabpos')
        if tab_position is not None:
            tab_position = int(tab_position)
        return CollectionPage(id, title, contents, tab_position)

    def toxml(self, rootname):
        val = u'<%s>%s</%s>' % (rootname, self.contents, rootname)
        elt = etree.fromstring(val)
        elt.set(u'id', self.id)
        if self.tab_position is not None:
            elt.set(u'tabpos', str(self.tab_position))
        return elt

    def display_content(self, url_fn):
        """Get the HTML to use to display the field contents.

        :param url_fn: A function which creates a url for a view.

        """
        doc = self.toxml(u'page')
        for elt in self._datatype_pattern(doc):
            attrib = elt.attrib
            data_type = attrib.get('data-type', None)
            display = attrib.get('data-display', None)
            if data_type == 'file':
                src = attrib.get('data-src', None)

                if src:
                    if display == 'full':
                        attrib['src'] = url_fn('media', path=src)
                    else:
                        tsize = {
                            'thumb': (256, 256),
                            'inline': (800, 600),
                        }.get(display, (800, 600))
                        tsize = thumbsize(src, *tsize)
                        if tsize is None:
                            tsize = (0, 0)
                        attrib['src'] = url_fn('thumbnail', path=src,
                                               width=tsize[0], height=tsize[1])
                        attrib['width'] = unicode(tsize[0])
                        attrib['height'] = unicode(tsize[1])
                alt = attrib.get('data-alt', None)
                if alt:
                    attrib['alt'] = alt
                title = attrib.get('data-title', None)
                if title:
                    attrib['title'] = title

            elif data_type == 'link':
                linktype = attrib.get('data-linktype', '')
                target = attrib.get('data-target', '')
                mimetype = attrib.get('data-mimetype', '')
                classes = list(filter(None, attrib.get('class', '').split(' ')))

                if display == 'icon':
                    classes.append('exp_linkicon')
                    if linktype == 'file':
                        classes.append(fileicon_class(mimetype))
                    elif linktype in ['search', 'url', 'record', 'collection']:
                        classes.append('exp_' + linktype)
                    else:
                        classes.append('exp_unknown')
                else:
                    classes.append('exp_linktext')
                attrib['class'] = ' '.join(classes)

                if linktype == 'file':
                    attrib['href'] = url_fn("media", path=target)
                    attrib['target'] = '_blank'
                elif linktype == 'search':
                    args = cgi.parse_qs(target)
                    args['act'] = 'search'
                    attrib['href'] = url_fn('search', **args)
                elif linktype == 'url':
                    attrib['href'] = target
                elif linktype == 'record':
                    attrib['href'] = url_fn('record-view', id=target)
                elif linktype == 'collection':
                    attrib['href'] = url_fn('coll-view', id=target)

        return inner_html(doc)

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        FIXME

    def __repr__(self):
        return "<CollectionPage %r>" % self.id

class Collection(object):
    def __init__(self, id, mtime, title,
                 autoorder=None, parents=None, children=None,
                 pages=None):
        """Create a new collection.

        """
        if mtime is not None:
            assert isinstance(mtime, float)
        if autoorder is None:
            autoorder = []
        if parents is None:
            parents = ()
        if children is None:
            children = ()
        if pages is None:
            pages = {}
        self.id = id
        self.title = title
        self.mtime = mtime
        self.autoorder = AutoOrder(autoorder)
        self._calced_ancestors = False
        self._parents = parents
        self._children = children
        self._pages = pages
        self._cached_queries = {}
        self._field_types = None

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        self.id = coll_id_map.get(self.id, self.id)
        self._calced_ancestors = False
        self._parents = [coll_id_map.get(cid, cid) for cid in self._parents]
        self._children = [coll_id_map.get(cid, cid) for cid in self._children]
        for page in self._pages:
            page.apply_mappings(record_id_map, coll_id_map, media_root_mappings)
        self._cached_queries = {}

    def __cmp__(self, other):
        if self is None:
            if other is None:
                return 1
            return 0
        if other is None:
            return -1
        return cmp(self.id, other.id) or \
               cmp(self.title, other.title) or \
               cmp(self.mtime, other.mtime) or \
               cmp(self.autoorder, other.autoorder) or \
               cmp(tuple(sorted(self._parents)), tuple(sorted(other._parents))) or \
               cmp(tuple(sorted(self._children)), tuple(sorted(other._children))) or \
               cmp(self._pages, other._pages)

    def __str__(self):
        return 'Collection(id=%r, title=%r, mtime=%r, autoorder=%r, _parents=%r, _children=%r, _pages=%r)' % (
            self.id,
            self.title,
            self.mtime,
            self.autoorder,
            self._parents,
            self._children,
            self._pages,
        )

    @staticmethod
    def find_by_title(title):
        """Return all collections with the given title."""
        result = []
        for coll in Collection.objects:
            if coll.title == title:
                result.append(coll)
        return result

    @staticmethod
    def fromxml(root):
        id = unicode(root.get(u'id'))
        mtime = root.get(u'mtime')
        if mtime is not None:
            mtime = float(mtime)
        title = root.get(u'title')
        if title is None:
            title = id
        autoorder = AutoOrder.fromxml(root.find(u"autoorder"))
        parents, children = Collection.relations_fromxml(root.find(u"relations"))
        pages = Collection.pages_fromxml(root.find(u"pages"))
        res = Collection(id, mtime, title, autoorder, parents, children, pages)
        return res

    @staticmethod
    def pages_fromxml(root):
        pages = {}
        if root is None:
            return pages
        for elt in root:
            if elt.tag == u'page':
                page = CollectionPage.fromxml(elt)
                pages[page.id] = page
        return pages
 
    def pages_toxml(self, rootname):
        root = etree.Element(rootname)
        pages = self._pages.items()
        pages.sort()
        for _, page in pages:
            root.append(page.toxml(u'page'))
        return root

    @staticmethod
    def relations_fromxml(root):
        parents = set()
        children = set()
        if root is None:
            return parents, children
        for elt in root:
            if elt.tag == u'parent':
                id = unicode(elt.get(u'id'))
                parents.add(id)
            if elt.tag == u'child':
                id = unicode(elt.get(u'id'))
                children.add(id)
        return parents, children
 
    def relations_toxml(self, rootname):
        root = etree.Element(rootname)
        for cid in self._parents:
            root.append(etree.Element(u"parent", id=cid))
        for cid in self._children:
            root.append(etree.Element(u"child", id=cid))
        return root

    @property
    def root(self):
        root = etree.Element('collection')
        root.set(u'id', self.id)
        root.set(u'title', self.title)
        if self.mtime is not None:
            root.set(u'mtime', repr(self.mtime))
        root.append(self.autoorder.toxml(u"autoorder"))
        root.append(self.relations_toxml(u"relations"))
        root.append(self.pages_toxml(u"pages"))
        return root

    def leading_tabs(self):
        """List of extra tabs to put at start of tab list."""
        tabs = []
        for page in self._pages.values():
            if page.tab_position is not None:
                tabs.append((page.tab_position, page))
        tabs.sort()
        return [page for (tabpos, page) in tabs]

    def page(self, id):
        """Get the page with a given ID.
        
        Returns None if no such page.
        
        """
        return self._pages.get(id)

    @property
    def parents(self):
        return self._parents

    @property
    def parent_objs(self):
        return [Collection.objects.get(id) for id in self._parents]

    @property
    def has_children(self):
        return len(self._children) != 0

    @property
    def children(self):
        result = []
        for id in self._children:
            try:
                result.append(Collection.objects.get(id))
            except KeyError:
                pass
        return result

    @property
    def children_objs(self):
        result = []
        for id in self._children:
            try:
                result.append(Collection.objects.get(id))
            except KeyError:
                pass
        return result

    @property
    def ancestors(self):
        if not self._calced_ancestors:
            seen = set()
            self._ancestors = self.get_ancestors(seen)
            self._calced_ancestors = True
        return self._ancestors

    @property
    def ancestor_objs(self):
        return [Collection.objects.get(id) for id in self.ancestors]

    @property
    def descendents(self):
        seen = set()
        return self.get_descendents(seen)

    @property
    def descendent_objs(self):
        result = []
        for id in self.descendents:
            try:
                result.append(Collection.objects.get(id))
            except KeyError:
                pass
        return result

    def set_parents(self, parents):
        from apps.store.search import Collection as SearchCollection
        hier = SearchCollection.taxonomy('coll_hierarchy')
        hier.add_category(self.id)
        changed = False
        new_parents = set()
        for parent in parents:
            if parent == self.id or parent == '':
                continue
            new_parents.add(parent)

        # Remove the collection from old parents which are no longer parents
        for parent in self._parents:
            if parent in new_parents:
                continue
            try:
                pcoll = Collection.objects.get(parent)
            except KeyError:
                continue # Can get KeyError if some of the ancestors don't exist - this would need to be fixed, but failing here would make it impossible for the user to fix it.
            pcoll._remove_child(self.id)
            Collection.objects.set(pcoll)
            hier.remove_parent(self.id, parent)
            changed = True

        for parent in new_parents:
            if parent in self._parents:
                continue
            pcoll = Collection.objects.get(parent)
            pcoll._add_child(self.id)
            Collection.objects.set(pcoll)
            hier.add_parent(self.id, parent)
            changed = True

        self._parents = tuple(sorted(new_parents))
        if changed:
            self._calced_ancestors = False

        return changed

    def _get_query(self, type, incsubs):
        key = (type, incsubs)
        q = self._cached_queries.get(key, None)
        if False and q is not None:
            # FIXME re-enable this cache, but make it persist only for the
            # duration of a single request.
            return q
        from apps.store.search import Collection as SearchCollection
        q = SearchCollection.doc_type(type)
        if incsubs:
            q = q.field.coll.is_or_is_descendant(self.id)
        else:
            q = q.field.coll.is_in(self.id)
        for name, asc in self.autoorder.ordering:
            asc = {'+': True, '-': False}[asc]
            q = q.order_by(name, asc)
        q = q.check_at_least(-1)
        self._cached_queries[key] = q
        return q

    def items_from_search(self, type='record', incsubs=False):
        return self._get_query(type, incsubs)

    def item_count(self, type='record', incsubs=False):
        return self._get_query(type, incsubs).matches_estimated

    def _remove_child(self, child_id):
        """Remove an entry from the children list for the collection.

        Doesn't ensure that the parent list for the child is updated.

        """
        self._children = tuple(filter(lambda id: id != child_id, self._children))

    def _add_child(self, child_id):
        """Add an entry to the children list for the collection.

        Doesn't ensure that the parent list for the child is updated.

        """
        new_children = set(self._children)
        new_children.add(child_id)
        self._children = tuple(sorted(new_children))

    def get_ancestors(self, seen):
        if self.id in seen:
            return ()
        seen.add(self.id)
        in_result = set()
        new_ancestors = []
        for parent in set(self._parents):
            if parent == self.id:
                continue

            if parent not in in_result:
                in_result.add(parent)
                new_ancestors.append(parent)

        for parent in set(self._parents):
            if parent == self.id:
                continue

            try:
                pcoll = Collection.objects.get(parent)
            except KeyError:
                continue

            for ancestor in pcoll.get_ancestors(seen):
                if ancestor == self.id:
                    continue
                if ancestor not in in_result:
                    in_result.add(ancestor)
                    new_ancestors.append(ancestor)

        return tuple(new_ancestors)

    def get_descendents(self, seen):
        if self.id in seen:
            return ()
        seen.add(self.id)

        new_descendents = set()
        for child in set(self._children):
            if child == self.id:
                continue
            new_descendents.add(child)

            try:
                ccoll = Collection.objects.get(child)
            except KeyError:
                continue
            for descendent in ccoll.get_descendents(seen):
                if descendent == self.id:
                    continue
                new_descendents.add(descendent)

        return tuple(sorted(new_descendents))

    def searchdocs(self):
        yield dict(
            type = 'coll',
            id = safeid(self.id),
            mtime = self.mtime,
            coll = self.id,
            title = self.title,
        )

    def field_types(self):
        if self._field_types is None:
            from apps.store.search import Collection as SearchCollection
            q = SearchCollection.field.coll.is_in(self.id)
            q = q.check_at_least(-1)[:0].calc_facet_count('_meta')
            fields = {}
            for name, count in q.info[0]['counts']:
                if not name.startswith('F'):
                    continue
                if '_' not in name:
                    continue
                name, type = name[1:].rsplit('_')
                fields.setdefault(name, []).append((type, count))
            self._field_types = fields.items()
            self._field_types.sort()
        return self._field_types

class Template(object):
    def __init__(self, id, mtime, root):
        """Create a new template.

        """
        assert isinstance(id, unicode)
        if mtime is not None:
            assert isinstance(mtime, float)
        assert isinstance(root, Record)
        self.id = id
        self.mtime = mtime
        self.record = copy.deepcopy(root)

    @property
    def inner_xml(self):
        return self.record.inner_xml

    def walkfields(self, startcount=1):
        return self.record.walkfields(startcount)

    def fieldnums(self):
        return self.record.fieldnums()

    @property
    def collections(self):
        return [unicode(coll.get(u'name'))
                for coll in self.root.iter(u'collection')]

    @property
    def collection_objs(self):
        result = []
        for collid in self.collections:
            try:
                result.append(Collection.objects.get(collid))
            except KeyError:
                pass
        return result

    @staticmethod
    def fromxml(root):
        mtime = root.get(u'mtime')
        if mtime is not None:
            mtime = float(mtime)
        return Template(unicode(root.get(u'id')),
                        mtime,
                        Record(root = root[0]))

    @property
    def root(self):
        root = etree.Element('template')
        root.set(u'id', self.id)
        root.set(u'mtime', repr(self.mtime))
        root.append(copy.deepcopy(self.record.root))
        return root

    def searchdocs(self):
        # Currently, don't make templates searchable
        return ()

    def position_in(self, coll):
        return None

class User(LazyXmlObject):
    def __init__(self, xml=None, root=None):
        LazyXmlObject.__init__(self, "user", xml, root)

    def get_info(self, name, default=None):
        """Get a piece of info about the user.

        """
        info = self.root.find("info")
        if info is None:
            return default
        return info.get(name, default)

    def set_info(self, name, value):
        """Set a piece of info about the user.

        """
        info = self.root.find("info")
        if info is None:
            info = etree.SubElement(self.root, "info")
        info.set(name, value)

    def searchdocs(self):
        # Currently, don't make users searchable
        return ()

class Settings(LazyXmlObject):
    def __init__(self, xml=None, root=None):
        LazyXmlObject.__init__(self, "settings", xml, root)

    def get_roots(self):
        """Get the root mappings (from name to path).

        """
        roots = self.root.find("roots")
        if roots is None:
            return {}
        result = {}
        for root in roots:
            if root.tag == 'root':
                name = root.get('name', None)
                path = root.get('path', None)
                if name and path:
                    result[name] = path
        return result

    def set_roots(self, roots):
        """Set the root mappings.

        """
        roots_elt = self.root.find("roots")
        if roots_elt is None:
            roots_elt = etree.SubElement(self.root, "roots")
        else:
            roots_elt.clear()
        for name, path in roots.items():
            root_elt = etree.SubElement(roots_elt, "root")
            root_elt.set('name', name)
            root_elt.set('path', path)
            roots_elt.append(root_elt)

    def searchdocs(self):
        return ()
