
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

    oldroot = 'file:///G:/data/BURMA_~1/'
    newroot = '/home/louise/Desktop/data/burma_photos'

    def re_root_path(path):
        if path.startswith(oldroot):
            path = path[len(oldroot):]
        path = os.path.join(newroot, path)
        return path

    def append_field(name, type):
        elt = etree.Element('field')
        elt.set(u'name', unicode(name))
        elt.set(u'type', unicode(type))
        record.root.append(elt)
        return elt

    tree = etree.parse(ctx.fileobj.file)
    root = tree.getroot()
    if root.tag != 'CatalogType':
        return ctx.set_error('File format not understood - expected root tag '
                             'to be CatalogType, got %s' % root.tag)
    itemlist = tree.find('MediaItemList')
    if itemlist is None:
        return ctx.set_error('File format not understood - no MediaItemList '
                             'found in file')

    for item in itemlist:
        if item.tag != 'MediaItem':
            continue

        record = Record()

        id = item.find('AssetProperties/UniqueID')
        if id is not None:
            record.id = ctx.idprefix + id.text.strip()

        annotations = item.find('AnnotationFields')
        if annotations is not None:
            notes = {}
            for annotation in annotations:
                text = unicode(annotation.text).strip()
                if text:
                    notes[unicode(annotation.tag).lower()] = unicode(text)
            if u'headline' in notes:
                elt = append_field(u'title', u'title')
                elt.text = notes[u'headline']
                del notes[u'headline']
            for field in sorted(notes.keys()):
                elt = append_field(field, u'text')
                elt.text = notes[field]

        path = item.find('AssetProperties/Filepath')
        if path is not None:
            path = re_root_path(path.text)
            elt = append_field(u'image', u'file')
            elt.set('src', path)
            elt.set('mimetype', 'image/jpeg')
            elt.set('display', 'inline')

        record.collections = [ctx.collname]
        Record.objects.set(record)
    Record.objects.flush()
    Collection.objects.flush()
