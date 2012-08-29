
import config
import os
import dircache
import lxml.etree as etree
from apps.store.models import Record, Collection
from apps.thumbnail.thumbnail import mimetype
from apps import shortcuts
from apps.importer.context import ImportContext

def parse_bamboo_date(text):
    # FIXME
    return text

def start_import(params):
    ctx = ImportContext()

    fileobj = params.get('file', None)
    if fileobj is None or not fileobj.filename:
        return ctx.set_error('No file supplied')

    title = unicode(params.get('collection', u''))
    if not title:
        return ctx.set_error('No collection specified') 

    colls = Collection.find_by_title(title)
    if len(colls) == 0:
        return ctx.set_error('Collection specified not found') 
    if len(colls) > 1:
        return ctx.set_error('Collection name specified maps to multiple collections') 
    coll = colls[0]

    type_mapping = {
        u'title': u'title',
        u'note': u'text',
        u'clip': u'text',
        u'caption': u'text',
        u'text': u'text',
        u'medium': u'tag',
        u'keywords': u'tag',
        u'date': u'date',
        u'img': u'file',
        u'imgthumb': u'file',
        u'musref': u'file',
        u'film': u'file',
        u'sound': u'file',
        u'collection': u'group',
        u'collection/person': u'tag',
        u'collection/date': u'date',
        u'collection/form': u'date',
        u'collection/location': u'location',
        u'collection/ethnicgroup': u'tag',
        u'collection/note': u'tag',
        u'collection/refnum': u'tag',
        u'production': u'group',
        u'production/person': u'tag',
        u'production/date': u'date',
        u'production/location': u'location',
        u'production/form': u'tag',
        u'production/note': u'text',
        u'production/refnum': u'tag',
        u'production/ethnicgroup': u'tag',
        u'acquirer': u'group',
        u'acquirer/date': u'date',
        u'acquirer/person': u'tag',
        u'acquirer/form': u'tag',
        u'acquirer/refnum': u'tag',
        u'acquirer/note': u'tag',
        u'size': u'number',
        u'person': u'tag',
        u'ethnicgroup': u'tag',
        u'location': u'location',

        u'refnext': u'refnext',
        u'refprev': u'refprev',
        u'seealso': u'seealso',
    }

    # HACK!
    known_locations = {}
#    for line in open('locations.txt').readlines():
#        line = line.strip()
#        line = line.split(':', 1)
#        if len(line) < 2: continue
#        if not line[1]:
#            continue
#        known_locations[line[0].strip()] = line[1].strip()
#
#    for k in sorted(known_locations):
#        print k, known_locations[k]

    ctx.setup(fileobj=fileobj, collid=coll.id,
              type_mapping=type_mapping, known_locations=known_locations)

    # FIXME - do this in a background thread.
    do_import(ctx)
    return ctx

def guess_path_case(path):
    """Try and find a path which exists which differs from the given path only in case.

    """
    orig_path = path
    end_components = []
    while not os.path.exists(path):
        path, tail = os.path.split(path)
        if tail == '': break
        end_components.insert(0, tail)
        if os.path.exists(path): break
    for component in end_components:
        items = {}
        for item in dircache.listdir(path):
            items.setdefault(item.lower(), []).append(item)
        guess = items.get(component.lower())
        if guess is None:
            print "Unable to find %r" % orig_path
            return orig_path
        path = os.path.join(path, guess[0])
    print "Corrected %s to %s" % (orig_path, path)
    return path

def do_import(ctx):
    referenced_media = []

    def mklink(linktype, display, target, mimetype=None):
        """Make an embedded link"""
        newelt = etree.Element('a')
        newelt.set('data-type', 'link')
        newelt.set('data-linktype', linktype)
        newelt.set('data-display', display)
        newelt.set('data-target', target)
        if mimetype is not None:
            newelt.set('data-mimetype', mimetype)
        return newelt

    def get_media(val):
        path = os.path.join(config.BAMBOO_MEDIA_PATH, val)
        if not os.path.exists(path):
            path = guess_path_case(path)
        if not os.path.exists(path):
            print "Missing file:", path
        mtype = mimetype(path)
        referenced_media.append((os.path.join(config.BAMBOO_MEDIA_URL, val), path))
        return path, mtype

    def parse_text_content(item):
        #print "TEXT:%r" % item.text
        #print "TAIL:%r" % item.tail
        if item.text:
            text = item.text.replace('&', '&amp;') \
                .replace('<', '&lt;') \
                .replace('>', '&gt;') # Yuck - need proper fix
            if len(stack[-1]) == 0:
                if stack[-1].text:
                    stack[-1].text += text
                else:
                    stack[-1].text = text
            else:
                if stack[-1][-1].tail:
                    stack[-1][-1].tail += text
                else:
                    stack[-1][-1].tail = text
        if item.tail:
            tail = item.tail.replace('&', '&amp;') \
                .replace('<', '&lt;') \
                .replace('>', '&gt;') # Yuck - need proper fix
            if len(stack[-1]) == 0:
                if stack[-1].tail:
                    stack[-1].tail += tail
                else:
                    stack[-1].tail = tail
            else:
                if stack[-1][-1].tail:
                    stack[-1][-1].tail += tail
                else:
                    stack[-1][-1].tail = tail

        for elt in item:
            if elt.tag in ():
                newelt = etree.Element(elt.tag)
            elif elt.tag == 'newline':
                newelt = etree.Element('br')
            elif elt.tag in ('img', 'imgthumb', ):
                # Embedded images, or thumbnails
                newelt = etree.Element('img')
                path, mtype = get_media(elt.text)
                display_type = {'img': 'inline',
                                'imgthumb': 'thumb',
                               }[elt.tag]

                newelt.set('data-type', 'file')
                if mtype is not None:
                    newelt.set('data-mimetype', mtype)
                newelt.set('data-src', path)
                newelt.set('data-display', display_type)
                newelt.set('data-alt', u'')
                newelt.set('data-title', u'')
                stack[-1].append(newelt)
                continue

            elif elt.tag in ('imglink', 'film', 'sound'):
                # Embedded links to files
                path, mtype = get_media(elt.text)
                newelt = mklink("file", "icon", path, mtype)
                stack[-1].append(newelt)
                continue


            # FIXME - the following fields probably isn't handled very usefully.
            elif elt.tag in (u'muscode'):
                newelt = etree.Element('span')
                newelt.set('style', 'muscode')
                newelt.text = elt.text

            elif elt.tag == u'refnext':
                newelt = mklink("record", "icon", elt.text.strip())
                newelt.text = "[NEXT]"
                stack[-1].append(newelt)
                continue
            elif elt.tag == u'refprev':
                newelt = mklink("record", "icon", elt.text.strip())
                newelt.text = "[PREV]"
                stack[-1].append(newelt)
                continue
            elif elt.tag in (u'musref'):
                newelt = mklink("record", "icon", elt.text.strip())
                newelt.text = '[Record %s]' % elt.text
                stack[-1].append(newelt)
                continue

            elif elt.tag in (u'caption'):
                newelt = etree.Element('div')
                newelt.set('style', 'caption')
                subelt = etree.Element('b')
                subelt.text = 'Caption:'
                newelt.append(subelt)
                
            elif elt.tag in (u'clip'):
                newelt = etree.Element('div')
                newelt.set('style', 'clip')
                subelt = etree.Element('b')
                subelt.text = 'Clip:'
                newelt.append(subelt)

            else:
                print "Unknown input tag type", etree.tostring(elt)
                abort()

            stack[-1].append(newelt)
            stack.append(newelt)
            parse_text_content(elt)
        stack.pop()

    def append_field(name, type):
        elt = etree.Element('field')
        elt.set(u'name', unicode(name))
        elt.set(u'type', unicode(type))
        stack[-1].append(elt)
        return elt

    tree = etree.parse(ctx.fileobj.file)
    for item in tree.getroot():
        record = Record()
        stack = [record.root]

        def parse_level(item, prefix=u''):
            for field in item:
                if field.tag == u'id':
                    record.id = unicode(field.text)
                    continue

                ftype = ctx.type_mapping.get(prefix + field.tag)

                if ftype == u'title':
                    elt = append_field(unicode(field.tag), u'title')
                    elt.text = field.text
                elif ftype == u'text':
                    elt = append_field(unicode(field.tag), u'text')
                    stack[-1].append(elt)
                    stack.append(elt)
                    parse_text_content(field)
                elif ftype == u'tag':
                    elt = append_field(unicode(field.tag), u'tag')
                    elt.text = field.text
                elif ftype == u'number':
                    elt = append_field(unicode(field.tag), u'number')
                    elt.text = field.text
                elif ftype == u'date':
                    elt = append_field(unicode(field.tag), u'date')
                    elt.text = parse_bamboo_date(field.text)
                elif ftype == u'file':
                    elt = append_field(unicode(field.tag), u'file')
                    path, mtype = get_media(field.text)
                    if mtype is not None:
                        elt.set('mimetype', mtype)
                    elt.set('src', path)
                    elt.set('display', {
                        'img': 'inline',
                        'imgthumb': 'thumb',
                        'sound': 'inline',
                        'film': 'inline',
                    }[field.tag])
                    elt.set('alt', '')
                    elt.set('title', '')

                elif ftype == u'location':
                    elt = append_field(unicode(field.tag), u'location')
                    elt.text = field.text
                    latlong = ctx.known_locations.get(field.text, None)
                    if latlong is not None:
                        elt.set('latlong', latlong)
                elif ftype == u'group':
                    elt = etree.Element('group')
                    elt.set(u'name', unicode(field.tag))
                    stack[-1].append(elt)
                    stack.append(elt)
                    parse_level(field, prefix + field.tag + u'/')

                # Bamboo reference types - each needs special handling
                elif ftype == u'seealso':
                    elt = append_field(unicode(field.tag), u'tag')
                    elt.text = field.text
                elif ftype == u'musref':
                    elt = append_field(unicode(field.tag), u'link')
                    elt.text = "Ref"
                    elt.set(u'linktype', u'record')
                    elt.set(u'target', field.text)
                elif ftype == u'refnext':
                    # Note - when these are fixed, we must also handle refnext
                    # and refprev inside text fields.
                    elt = append_field(unicode(field.tag), u'link')
                    elt.text = "Next"
                    elt.set(u'linktype', u'record')
                    elt.set(u'target', field.text)
                elif ftype == u'refprev':
                    elt = append_field(unicode(field.tag), u'link')
                    elt.text = "Previous"
                    elt.set(u'linktype', u'record')
                    elt.set(u'target', field.text)
                else:
                    print "Unknown field: %s" % (prefix + field.tag)
                    print etree.tostring(field)
                    abort()
            stack.pop()
        parse_level(item)

        record.collections = [ctx.collid]
        Record.objects.set(record)

    Record.objects.flush()
    Collection.objects.flush()

    return
    # Download the referenced media
    import urllib
    for url, path in referenced_media:
        if os.path.exists(path):
            continue
        print "Downloading %r to %r" % (url, path)
        fd_in = urllib.urlopen(url)
        file_contents = fd_in.read()
        fd_in.close()
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        fd_out = open(path + '.new', 'wb')
        fd_out.write(file_contents)
        fd_out.close()
        os.rename(path + '.new', path)
