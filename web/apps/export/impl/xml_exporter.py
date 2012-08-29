from apps.export.impl.base import Exporter
from apps.store.models import Collection
import copy
from lxml import etree
import os

class XmlExporter(Exporter):
    fmt = 'xml'
    description = "Raw XML format"
    priority = 10

    def read_params(self, stash, params):
        pass

    @property
    def headers(self):
        return {
            'Content-Type': 'application/xml; charset="utf-8"',
            'Content-Disposition': 'attachment; filename=export.xml',
        }

    @property
    def resultpath(self):
        return self.outpath

    def export(self, tempdir):
        self.outpath = os.path.join(tempdir, 'export.xml')
        collection_ids = set()
        result = etree.XML(u'<container/>')
        records = etree.XML(u'<records/>')
        result.append(records)
        count = 1
        size = len(self.objs)
        while len(self.objs) > 0:
            yield "Formatting record %d of %d" % (count, size)
            count += 1
            r = self.objs.pop(0)
            newroot = copy.deepcopy(r.root)
            if newroot.tail is None:
                newroot.tail = '\n'
            else:
                newroot.tail += '\n'
            records.append(newroot)
            collection_ids.update(r.collections)
        collections = etree.XML(u'<collections/>')
        result.append(collections)
        for collid in sorted(collection_ids):
            try:
                coll = Collection.objects.get(collid)
            except KeyError:
                continue
            newroot = copy.deepcopy(coll.root)
            if newroot.tail is None:
                newroot.tail = '\n'
            else:
                newroot.tail += '\n'
            collections.append(newroot)

        yield "Building complete document"
        etree.ElementTree(result).write(self.outpath,
                                        encoding='utf-8', xml_declaration=True)
