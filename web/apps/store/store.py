# Threadsafe interface to the store of objects.

import config
import models
import os
import search
from apps.shortcuts import locked
import time
import threading
import xmlstore


class Store(object):
    def __init__(self, name, factory):
        """Initialise a Store.

         - `name` is the directory name that the store is put into.
         - `factory` is a factory function which should construct an instance
           of one of the objects in the store, given the Element.

        """
        self.path = os.path.join(config.storedir, name)
        self.factory = factory
        self.mutex = threading.Lock()
        self.items = None
        self.open()
        self.cache = {}

    @locked
    def open(self):
        assert self.items is None
        self.items = xmlstore.XmlStore(self.path)
        try:
            self.next_id = int(self.items.get_meta(u'next_id'))
        except KeyError:
            self.next_id = 1

    @locked
    def close(self):
        self.items.set_meta(u'next_id', unicode(self.next_id))
        self.items.close()
        self.items = None
        self.next_id = None

    @locked
    def flush(self):
        self._flush()
        self.cache = {}

    def _flush(self):
        self.items.set_meta(u'next_id', unicode(self.next_id))
        self.items.flush()
        search.indexer.flush()

    @locked
    def __len__(self):
        """Count the number of items.

        """
        return len(self.items)

    def _get_cached(self, id):
        try:
            return self.cache[id]
        except KeyError:
            pass

        if len(self.cache) > 1000:
            # Very simple expire policy!
            self.cache = {}

        item = self.factory(self.items.get(id))
        self.cache[id] = item
        return item

    def __iter__(self):
        """Iterate over all the items, in sorted order of their IDs.

        """
        self.mutex.acquire()
        try:
            for id in self.items:
                try:
                    item = self._get_cached(id)
                except KeyError:
                    # This can happen if an item is deleted after starting
                    # iteration.
                    continue
                self.mutex.release()
                yield item
                self.mutex.acquire()
        finally:
            if self.mutex.locked():
                self.mutex.release()

    @locked
    def get(self, id):
        """Get the item with the specified ID, or raise KeyError.

        """
        assert isinstance(id, unicode)
        return self._get_cached(id)

    @locked
    def set(self, item):
        """Store an item.

        Allocates an ID, and updates the item to contain it, if one isn't
        already set.

        """
        if item.id is None:
            item.id = self._alloc_id()
        assert item.id != u''
        item.mtime = time.time()
        try:
            del self.cache[item.id]
        except KeyError: pass

        self.pre_save(item)
        self.items.set(item.root)
        search.indexer.set(item)

        self.cache[item.id] = item

    def pre_save(self, item):
        """Hook for performing actions just before a save.

        """
        pass

    @locked
    def reindex(self, item):
        """Regenerate the record for this item in the search index.

        """
        assert item.id is not None and item.id != u''
        search.indexer.set(item)

    @locked
    def remove(self, id):
        """Remove the item with the specified ID, or raise KeyError.

        """
        assert isinstance(id, unicode)
        try:
            del self.cache[id]
        except KeyError: pass

        item = self.factory(self.items.get(id))
        search.indexer.remove(item)
        self.items.remove(id)

    def _alloc_id(self):
        """Allocate a new unique ID.

        """
        while True:
            newid = unicode(self.next_id)
            self.next_id += 1
            try:
                self.items.get(newid)
            except KeyError:
                return newid

def flat_fields(item):
    result = set()
    for flatdoc in item.flatten():
        if flatdoc.get('type') != 'r':
            continue
        result.update(flatdoc.keys())
    return result

models.Record.objects = \
    Store("records", lambda x: models.Record(root=x))
models.Collection.objects = \
    Store("collections", lambda x: models.Collection.fromxml(x))
models.Template.objects = \
    Store("templates", lambda x: models.Template.fromxml(x))
models.User.objects = \
    Store("users", lambda x: models.User(root=x))
models.Settings.objects = \
    Store("settings", lambda x: models.Settings(root=x))


def flush():
    """Flush all data to stores.

    """
    models.Record.objects.flush()
    models.Collection.objects.flush()
    models.Template.objects.flush()
    models.User.objects.flush()
    models.Settings.objects.flush()

def close():
    """Close all stores, flushing first.

    """
    models.Record.objects.close()
    models.Collection.objects.close()
    models.Template.objects.close()
    models.User.objects.close()
    models.Settings.objects.close()
