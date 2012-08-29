from apps.shortcuts import getparamlist, getparam
from apps.search.models import fields_from_search

exporters = {}
class ExporterMeta(type):
    def __new__(cls, name, bases, attrs):
        newcls = super(ExporterMeta, cls).__new__(cls, name, bases, attrs)
        fmt = attrs.get('fmt')
        if fmt is not None:
            exporters[fmt] = newcls
        return newcls

class Exporter(object):
    __metaclass__ = ExporterMeta

    @staticmethod
    def get(fmt):
        return exporters[fmt]

    @staticmethod
    def fmts(params):
        fmts = [(-exporter.priority, fmt, exporter.description)
                for (fmt, exporter) in exporters.items()
                if exporter.is_valid(params)]
        fmts.sort()
        return tuple(map(lambda info: tuple(info[1:]), fmts))

    def __init__(self):
        self.objs = []

    @classmethod
    def is_valid(cls, params):
        """Check if the exporter is valid for the given parameters."""
        return True

    def add(self, obj):
        self.objs.append(obj)

    def add_to_context(self, context, search, stash, params):
        """Add to the context for setting params for this exporter.

        """
        pass

class FieldSpecificExporter(Exporter):
    """An exporter which takes a list of fields.

    """
    def read_params(self, stash, params):
        self.fields = getparamlist('f', None, stash, params)
        self.forder = getparam("forder", 'record', stash, params)

    @property
    def custom_order(self):
        return self.forder == 'custom'

    def add_to_context(self, context, search, stash, params):
        super(FieldSpecificExporter, self) \
            .add_to_context(context, search, stash, params)

        relevant_fields = tuple(('%s_%s' % (field, type), field, type, count)
                                for field, types in fields_from_search(search)
                                for type, count in types)
        if self.fields is None:
            fields = tuple(x[0] for x in relevant_fields)
        else:
            fields = tuple(self.fields)
            relfield_keys = tuple(map(lambda x: x[0], relevant_fields))
            def key(x):
                try:
                    return fields.index(x[0])
                except ValueError:
                    return len(fields) + relfield_keys.index(x[0])
            relevant_fields = tuple(sorted(relevant_fields, key=key))

        context.update(dict(
                            selected_fields = fields,
                            relevant_fields = relevant_fields,
                            forder = self.forder,
                           ))
