
import config
import os
import lxml.etree as etree
from apps.importer.context import ImportContext
from apps.store.models import Record, Collection
from apps.thumbnail.thumbnail import mimetype
from apps import shortcuts

def start_import(params):
    ctx = ImportContext()

    fileobj = params.get('file', None)
    if fileobj is None or not fileobj.filename:
        return ctx.set_error('No file supplied')

    collname = unicode(params.get('collection', u''))
    if not collname:
        return ctx.set_error('No collection specified') 

    try:
        coll = Collection.objects.get(collname)
    except KeyError:
        return ctx.set_error('Collection specified not found') 

    ctx.setup(fileobj=fileobj, collname=collname,
              idprefix=collname.lower().replace(' ', '_') + '_',
             )

    # FIXME - do this in a background thread.
    do_import(ctx)
    return ctx

def do_import(ctx):

    newroot = '/home/louise/Desktop/data/Cornwall'

    def re_root_path(path):
        path = os.path.join(newroot, os.path.basename(path))
        return path

    tree = etree.parse(ctx.fileobj.file)
    root = tree.getroot()
    if root.tag != 'records':
        return ctx.set_error('File format not understood - expected root tag '
                             'to be records, got %s' % root.tag)

    for item in root:
        if item.tag != 'record':
            return ctx.set_error('Expected a record, got %s' % item.tag)

        record = Record(root=item)
        record.id = ctx.idprefix + record.id
        record.collections = [ctx.collname]
        Record.objects.set(record)
    Record.objects.flush()
    Collection.objects.flush()
