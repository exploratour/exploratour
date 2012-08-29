#!/usr/bin/env python
from apps.store.models import Record, Template, Collection
import apps.store.store # Import this to initialise the stores.
import apps.store.search
from apps.bgprocess import TaskProgress
import config
import restpose
import time

def restpose_ratelimit():
    """Wait for restpose not to have too many things to do."""
    try:
        # do some simple rate-limiting
        while True:
            taskstatus = restpose.Server(config.search_url).status['tasks']
            if (
                taskstatus['indexing']['queues'][config.search_collection]['size'] < 50 and
                taskstatus['processing']['queues'][config.search_collection]['size'] < 50
            ):
                break
            time.sleep(0.1)
    except KeyError:
        pass

class Reindexer(object):
    """Reindex everything.

    """
    def perform(self):
        yield TaskProgress("Started reindex")

        search_coll = apps.store.search.Collection
        search_coll.delete()
        apps.store.search.set_config()

        count = dict(c=0, r=0, t=0)
        yield TaskProgress("Setting collection hierarchy")
        hier = search_coll.taxonomy('coll_hierarchy')
        for coll in Collection.objects:
            hier.add_category(coll.id)
            for parent_id in coll.parents:
                hier.add_parent(coll.id, parent_id)

        for collection in Collection.objects:
            yield TaskProgress("Reindexing collection %s" % collection.id)
            Collection.objects.reindex(collection)
            count['c'] += 1
            restpose_ratelimit()

        for record in Record.objects:
            yield TaskProgress("Reindexing record %s" % record.id)
            Record.objects.reindex(record)
            count['r'] += 1
            restpose_ratelimit()

        for template in Template.objects:
            yield TaskProgress("Reindexing template %s" % template.id)
            Template.objects.reindex(template)
            count['t'] += 1
            restpose_ratelimit()

        #print apps.store.search.indexer.client.schema.serialise()
        yield TaskProgress("Flushing")
        apps.store.search.indexer.flush()
        yield TaskProgress("Reindex complete - indexed %(r)d records in %(c)d collections, and %(t)d templates" % count, complete=True)
