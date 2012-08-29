
from apps.store.models import Record, Template, Collection
from apps.lockto.utils import get_lockto_collid

class Context(object):
    @staticmethod
    def all_collection_ids():
        return [c.title for c in Collection.objects]

    @staticmethod
    def locked_collection_ids():
        lockto = get_lockto_collid()
        if lockto is None:
            return [c.title for c in Collection.objects]
        lockcoll = Collection.objects.get(lockto)
        result = [c.title for c in lockcoll.descendent_objs]
        result.append(lockcoll.title)
        return result

autocomplete_context = Context()
