# Interface to search system.

import config
import restpose
from apps.shortcuts import locked
import threading
from apps.store.models import Record, Collection, Template
import pprint

class Indexer(object):
    """Class which marshalls updates into search documents, and sends them for
    indexing.

    All methods are synchronised, so may be called by multiple threads at a time.

    """
    def __init__(self):
        self.mutex = threading.Lock()
        self.coll = restpose.Server(config.search_url).collection(config.search_collection)

    @locked
    def close(self):
        if self.coll is not None:
            # self.coll.close()
            self.coll = None

    @locked
    def flush(self):
        errors = self.coll.checkpoint().wait().errors
        if errors:
            print "Indexing errors:"
            pprint.pprint(errors)

    @locked
    def set(self, item):
        docs = []
        rdoc = None
        for doc in item.searchdocs():
            #print "Adding", doc['type'], doc['id'], doc['coll'], doc.keys()
            self.coll.add_doc(doc)

    @locked
    def remove(self, item):
        hier = self.coll.taxonomy('coll_hierarchy')
        for doc in item.searchdocs():
            #print "Deleting", doc['type'], doc['id']
            self.coll.delete_doc(doc_type=doc['type'], doc_id=doc['id'])
            if doc['type'] == 'coll':
                hier.remove_category(doc['id'])

indexer = Indexer()

def SearchClient():
    return Collection

def realise_objects(wanted, needed):
    to_get = {}
    for item in needed:
        to_get.setdefault(item.data['type'][0], []).append(item)

    for type, items in to_get.iteritems():
        if type == 'record':
            model = Record
        elif type == 'coll':
            model = Collection
        elif type == 'tmpl':
            model = Template
        else:
            continue
        #objs = model.objects.in_bulk([int(item.data['id'][0]) for item in items])
        ids = (item.data['id'][0] for item in items)
        objs = dict((id, model.objects.get(id)) for id in ids)
        for item in items:
            item.object = objs[item.data['id'][0]]

Collection = restpose.Server(config.search_url) \
    .collection(config.search_collection) \
    .set_realiser(realise_objects)

def set_config():
    Collection.checkpoint().wait()
    config = Collection.config
    patterns = [
        # FIXME - add an _error type.

        # Fields of date type
        ('*_date', {
            'slot': 'y*',
            'store_field': "*_date",
            'type': "date",
        }),

        # Text fields (stripped of markup)
        ("*_text", {
            "group":"t*",
            "slot":"t*",
            "processor":"stem_en",
            "store_field":"*_text",
            "type":"text"
        }),

        # Summary text for links
        ("*_link", {
            "group":"l*",
            "slot":"l*",
            "processor":"stem_en",
            "store_field":"*_link",
            "type":"text"
        }),

        # Title fields
        ("*_title", {
            "group":"e*",
            "slot":"e*",
            "processor":"stem_en",
            "store_field":"*_title",
            "type":"text"
        }),

        # Number fields
        ("*_number", {
            "slot":"n*",
            "store_field":"*_number",
            "type":"double"
        }),

        # File fields (the title / alt text / content of text files)
        ("*_file", {
            "group":"i*",
            "slot":"i*",
            "processor":"stem_en",
            "store_field":"*_file",
            "type":"text"
        }),

        # Tag fields
        ("*_tag", {
            "group":"g*",
            "slot":"g*",
            "max_length":100,
            "store_field":"*_tag",
            "too_long_action":"hash",
            "lowercase":True,
            "type":"exact"
        }),

        # Location fields (the text part - handled like a tag)
        ("*_location", {
            "group":"g*",
            "slot":"g*",
            "max_length":100,
            "store_field":"*_location",
            "too_long_action":"hash",
            "lowercase":True,
            "type":"exact"
        }),

        # FIXME - location fields have form *_latlong; need a pattern for them.

        # The collection that an item is in.
        ('coll', {
            'group': "C",
            'max_length': 32,
            'slot': 2,
            'store_field': "coll",
            'taxonomy': "coll_hierarchy",
            'too_long_action': "hash",
            'type': "cat",
        }),

        # Modification times.
        ('mtime', {
            'slot': 3,
            'store_field': "mtime",
            'type': "timestamp",
        }),

        # Titles of items.
        ('title', {
            'group': 't',
            'slot': 4,
            'store_field': "title",
            'type': "text",
        }),

        # For media items, the ID of the record holding the item.
        ('parent', {
            'group': 'P',
            'max_length': 100,
            'store_field': "parent",
            'too_long_action': 'hash',
            'type': "exact",
        }),

        # The ID of a media item (the path or url).
        ('fileid', {
            'group': 'F',
            'max_length': 100,
            'store_field': "fileid",
            'too_long_action': 'hash',
            'type': "exact",
        }),

        # The mimetype of a media item
        ('mimetype', {
            'group': 'T',
            'slot': 5,
            'max_length': 100,
            'store_field': "mimetype",
            'too_long_action': 'hash',
            'type': "exact",
        }),

        # The alt text of a media item
        ('filealt', {
            'group': 'A',
            'store_field': "filealt",
            'type': "text",
        }),

        # The title text of a media item
        ('filetitle', {
            'group': 'A',
            'store_field': "filetitle",
            'type': "text",
        }),

        # All dates held in a record.
        ('date', {
            'slot': 6,
            'store_field': "date",
            'type': "date",
        }),

        # The text of a record.
        ("text", {
            "group":"t",
            "processor":"stem_en",
            "store_field":"text",
            "type":"text"
        }),

        ('id', {
            'max_length': 100,
            'store_field': "id",
            'too_long_action': 'hash',
            'type': "id",
        }),

        # The meta field to use (supports things like searches for which fields
        # exist.)
        ("_meta", {
            "group":"#",
            "slot":0,
            "type":"meta"
        }),

        # The type of a record.
        ("type", {
            "group":"!",
            "slot": 1,
            "store_field":"type",
            "type":"exact"
        }),

        ("*", {
            "group":"u",
            "store_field":"*",
            "type":"text"
        }),

    ]
    config['default_type']['patterns'] = patterns

    Collection.config = config

set_config()
