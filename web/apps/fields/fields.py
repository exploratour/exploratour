from apps.lockto.utils import get_lockto_collid
from apps.record.sanitize_html import clean as clean_html
from apps.record.errors import ValidationError
from apps.shortcuts import getparam
from apps.thumbnail.thumbnail import thumbsize
import cgi
import cherrypy
import copy
from lxml import etree
import lxml.html
import mimetypes
from restpose import Field
import os
import utils.parsedate
try:
    from simplejson import json
except ImportError:
    import json


_datatype_pattern = etree.XPath("descendant-or-self::*[@data-type]")

inline_tags = lxml.html.defs.special_inline_tags.union(
    lxml.html.defs.font_style_tags)

def wrap_elt(elem, tag, attributes=None):
    """Wrap an lxml.etree element in something another tag."""
    if attributes is None:
        attributes = {}
    tail = elem.tail
    elem.tail = ''
    elemcopy = copy.deepcopy(elem)
    elem.clear()
    elem.tag = tag
    elem.attrib.clear()
    elem.attrib.update(attributes)
    elem.append(elemcopy)
    elem.tail = tail
    elem = elemcopy

def inner_html(elem):
    """Get the inner html for an element."""
    return (unicode(elem.text or u'')) + u''.join(
        unicode(lxml.html.tostring(child, encoding=unicode))
        for child in elem)

def flatten_name(names):
    """Return a flattened form of an element name.

    """
    return u':'.join(map(lambda x: x.replace('\\', '\\\\')
                                    .replace(':', '\\:'), names))

def unflatten_name(name):
    """Undo flattening of a name.

    """
    def unesc(s):
        r = []
        it = iter(s)
        for c in it:
            if c == ':':
                yield u''.join(r)
                r = []
                continue
            if c == '\\':
                c = it.next()
            r.append(c)
        yield u''.join(r)
    return tuple(unesc(name))

def existence_search(client, flat_name, names, value):
    """Create a search for existence or non existence of a field, if the value
    is * or -*.

    """
    if value == '':
        return (client.field(flat_name).exists(),
                '%s exists' % (':'.join(names), ))
    elif value == '*':
        return (client.field(flat_name).nonempty(),
                '%s is non-empty' % (':'.join(names), ))
    elif value == '-*':
        return (client.field(flat_name).empty(),
                '%s exists but is empty' % (':'.join(names), ))

    return None

def setelt(elt, attr, val):
    """Set an element parameter if it's Truthy."""
    if val:
        elt.set(attr, val)

def param_from_form(key, required=True, params=None):
    val = getparam(key, params=params)
    if required and val is None:
        raise ValidationError("Missing parameter %s" % key)
    return val

def pick_constructor(tag, type, closing):
    if tag == 'group':
        if closing:
            return ClosingGroupItem
        return GroupItem

    if tag == 'field':
        if closing:
            return None
        try:
            return field_item_types[type]
        except KeyError:
            raise ValidationError('Unknown field type: %s' % type)

    raise ValidationError('Unknown XML type: %s' % tag)

def fileicon_class(mimetype):
    if mimetype.startswith('image/'):
        return 'exp_image'
    elif mimetype.startswith('audio/'):
        return 'exp_audio'
    elif mimetype.startswith('video/'):
        return 'exp_video'
    elif mimetype in ('application/pdf',):
        return 'exp_document'
    else:
        return 'exp_unknown'

class MediaItem(object):
    def __init__(self, src, mimetype, alt, title, display, rotate):
        if not mimetype:
            mimetype = mimetypes.guess_type(src)[0]
            if not mimetype:
                mimetype = None

        self.src = src
        self.mimetype = mimetype
        self.alt = alt
        self.title = title
        self.display = display
        self.rotate = rotate

        self.size_calced = False

    @property
    def iconclass(self):
        return fileicon_class(self.mimetype)

    @property
    def path(self):
        from apps.mediainfo.views import mapper
        return mapper._map_path(self.src)

    def file_exists(self):
        path = self.path
        if path is None:
            return False
        return os.path.isfile(path)

    @property
    def size(self):
        from apps.thumbnail.thumbnail import imgsize
        if not self.size_calced:
            self._size = imgsize(self.src)
            self.size_calced = True
        return self._size

def RecordItem_from_element(elt, tag, names, count, closing):
    level = len(names) - 1
    cons = pick_constructor(tag, elt.get('type'), closing)
    if cons is None:
        return None
    result = cons()
    result.set_properties_from_elt(elt, names, level, count, closing)
    return result

def RecordItem_from_form(num, params=None):
    tag = param_from_form('t_%d' % num, params=params)
    type = param_from_form('ft_%d' % num, required=False, params=params)
    closing = bool(param_from_form('fc_%d' % num, required=False, params=params))
    result = pick_constructor(tag, type, closing)()
    result.set_properties_from_form(num, params=params)
    return result

class RecordItem(object):
    def set_properties_from_elt(self, elt, names, level, count, closing):
        self.closing = closing
        self.names = names
        self.level = level
        self.count = count
        self._name = elt.get('name') or ''

    def set_properties_from_form(self, num, params=None):
        self.closing = bool(param_from_form('fc_%d' % num, required=False,
                                            params=params))
        self.level = param_from_form('fl_%d' % num, params=params)
        self.count = num
        if self.closing:
            return
        self._name = param_from_form('fn_%d' % num, params=params)

    @property
    def name(self):
        return self._name or getattr(self, 'defname', '')

    @property
    def flatname(self):
        return flatten_name(list(self.names)[:-1] + [self.name])

    def get_elt(self):
        assert not self.closing
        elt = etree.Element(self.tag)
        setelt(elt, 'name', self._name)
        return elt

    def media(self):
        return ()

class ClosingItem(RecordItem):
    def set_properties_from_elt(self, elt, names, level, count, closing):
        RecordItem.set_properties_from_elt(self, elt, names, level, count, closing)
        self.closing = True

class ClosingGroupItem(ClosingItem):
    tag = 'group'

class GroupItem(RecordItem):
    tag = 'group'

    def flatten(self):
        return None


def apply_media_mappings(path, media_root_mappings):
    if path is None:
        return None
    if path[0] == '/':
        splitpath = path[1:].split('/', 1)
    else:
        splitpath = path.split('/', 1)
    if len(splitpath) == 1:
        root, tail = splitpath, None
    else:
        root, tail = splitpath
    root = media_root_mappings.get(root, root)
    if tail is None:
        return '/' + root
    return '/' + root + '/' + tail


def build_from_elt(root, indent=0):
    result = []
    for elt in root:
        if elt.tag == u'group':
            result.append(Group.build_from_elt(elt, indent+2))
        elif elt.tag == u'field':
            field_type = elt.get('type')
            try:
                cons = field_types[field_type]
            except KeyError:
                raise ValidationError('Unknown field type: %r' % field_type)
            result.append(cons.build_from_elt(elt))
        else:
            raise ValidationError('Unexpected XML tag: %s - expected "field" or "group"' % elt.tag)
    return result

def field_from_data(data, indent=0):
    field_type = data["type"]

    if field_type == u'group':
        g = Group(
            data["name"],
            map(lambda subdata: field_from_data(subdata, indent+2),
                data["contents"])
        )
        # ge = g.get_elt(indent + 2)
        # print "ge",etree.tostring(ge, encoding=unicode)
        # r = Group.build_from_elt(ge, indent)
        # print "r",etree.tostring(r.get_elt(), encoding=unicode)
        return g

    try:
        cons = field_types[field_type]
    except KeyError:
        raise ValidationError('Unknown field type: %r' % field_type)
    r =  cons(**data)
    return cons(**data)


class Group(object):
    """A group of fields.

    """
    def __init__(self, name, contents):
        self.name = name
        self.contents = contents

    @staticmethod
    def build_from_elt(elt, indent=0):
        return Group(elt.get(u'name') or '', build_from_elt(elt, indent))

    def get_elt(self, indent=0):
        elt = etree.Element("group")
        setelt(elt, 'name', self.name)
        elt.text = '\n' + ' ' * indent
        for num, item in enumerate(self.contents, 1):
            subelt = item.get_elt(indent + 2)
            if num < len(self.contents):
                subelt.tail = '\n' + ' ' * indent
            else:
                subelt.tail = '\n' + ' ' * (indent - 2)
            elt.append(subelt)
        return elt

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        for item in self.contents:
            item.apply_mappings(record_id_map, coll_id_map, media_root_mappings)

    def __str__(self):
        return "Group(%s)" % ', '.join(map(str, self.contents))

    def __repr__(self):
        return str(self)

    def to_json(self):
        result = {
            "type": u"group",
            "name": self.name,
            "contents": map(lambda field: field.to_json(), self.contents),
        }
        return result


class Field(object):
    """Base class of fields.

    """
    # Additional properties that the field has that are simply read from
    # attributes.
    _attrib_properties = ()

    # Extra properties that the field has that are displayed by str.
    _display_properties = ()

    def __init__(self, name, **kwargs):
        self.name = name
        for property in self._attrib_properties:
            setattr(self, property, kwargs[property])

    @classmethod
    def params_from_elt(cls, elt):
        name = elt.get(u'name') or ''
        kwargs = dict((property, elt.get(property) or '')
                      for property in cls._attrib_properties)
        return (name,), kwargs

    @classmethod
    def build_from_elt(cls, elt):
        args, kwargs = cls.params_from_elt(elt)
        return cls(*args, **kwargs)

    def get_elt(self, indent=0):
        elt = etree.Element("field")
        setelt(elt, 'name', self.name)
        setelt(elt, 'type', self.field_type)
        for prop in self._attrib_properties:
            setelt(elt, prop, getattr(self, prop))
        return elt

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        pass

    def __str__(self):
        props = ', '.join("%s=%r" % (prop, getattr(self, prop))
                          for prop in self._attrib_properties +
                              self._display_properties)
        if props:
            props= ', ' + props
        return "%s(type=%s, name=%s%s)" % \
                (self.__class__.__name__, self.field_type, self.name, props)

    def __repr__(self):
        return str(self)


class FlatTextField(Field):
    """A field which contains a value which is represented as text.

    """
    _display_properties = ('text',)

    def __init__(self, name, text, **kwargs):
        super(FlatTextField, self).__init__(name, **kwargs)
        self.text = text

    @classmethod
    def params_from_elt(cls, elt):
        args, kwargs = super(FlatTextField, cls).params_from_elt(elt)
        args = args + (elt.text, )
        return args, kwargs

    def get_elt(self, indent=0):
        elt = super(FlatTextField, self).get_elt(indent)
        elt.text = self.text
        return elt

    def to_json(self):
        result = {
            "type": self.field_type,
            "name": self.name,
            "text": self.text,
        }
        for prop in self._attrib_properties + self._display_properties:
            result[prop] = getattr(self, prop)
        return result


class DateField(FlatTextField):
    """A field representing a date.

    """
    field_type = 'date'
    defname = 'Date'


class TagField(FlatTextField):
    field_type = 'tag'
    defname = "Tags"


class LinkField(FlatTextField):
    field_type = 'link'
    defname = "Link"
    _attrib_properties = ('linktype', 'target')

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        if self.linktype == 'record':
            self.target = record_id_map.get(self.target, self.target)
        elif self.linktype == 'collection':
            self.target = coll_id_map.get(self.target, self.target)

class FileField(FlatTextField):
    field_type = 'file'
    defname = "File"
    _attrib_properties = ('mimetype', 'src', 'display', 'alt', 'title')
    _display_properties = ('areas',)

    def __init__(self, *args, **kwargs):
        super(FileField, self).__init__(*args, **kwargs)
        alt = self.alt or self.title
        title = self.title or self.alt
        self.alt, self.title = alt, title
        self.areas = kwargs['areas']

    @classmethod
    def params_from_elt(cls, elt):
        args, kwargs = super(FileField, cls).params_from_elt(elt)
        areas = elt.findall('area')
        kwargs['areas'] = [dict(x1=intfromelt(a, 'x1'),
                                y1=intfromelt(a, 'y1'),
                                x2=intfromelt(a, 'x2'),
                                y2=intfromelt(a, 'y2'),
                                src=a.get('src'),
                                title=a.get('title'))
                           for a in areas]
        return args, kwargs

    def get_elt(self, indent=0):
        elt = super(FileField, self).get_elt(indent)
        for area in self.areas:
            areaelt = etree.Element('area')
            setelt(areaelt, 'x1', str(area['x1']))
            setelt(areaelt, 'y1', str(area['y1']))
            setelt(areaelt, 'x2', str(area['x2']))
            setelt(areaelt, 'y2', str(area['y2']))
            setelt(areaelt, 'src', area['src'])
            setelt(areaelt, 'title', area['title'])
            elt.append(areaelt)
        return elt

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        self.src = apply_media_mappings(self.src, media_root_mappings)


class LocationField(FlatTextField):
    field_type = 'location'
    defname = "Location"
    _attrib_properties = ('latlong',)


class TextField(Field):
    field_type = 'text'
    defname = "Text"

    def __init__(self, name, content, **kwargs):
        super(TextField, self).__init__(name, **kwargs)
        self.content = content

    @classmethod
    def params_from_elt(cls, elt):
        args, kwargs = super(TextField, cls).params_from_elt(elt)
        args = args + (cls.content_from_elt(elt), )
        return args, kwargs

    @staticmethod
    def content_from_elt(elt):
        # The following is a horrible hack to remove the xmlns from the
        # elements when presented in the edit box.
        content = []
        if elt.text:
            tmp = etree.Element('a')
            tmp.text = elt.text
            tmp = etree.tostring(tmp, encoding=unicode)
            tmp = tmp[3:-4]
            content.append(unicode(tmp))
        for e in elt:
            item = etree.tostring(e, encoding=unicode)
            content.append(unicode(item))
        content = u''.join(content)
        return content

    def get_elt(self, indent=0):
        elt = super(TextField, self).get_elt(indent)
        val = u'<root>' + self.content + u'</root>'
        val = etree.fromstring(val)
        if val.text:
            elt.text = val.text
        for e in val:
            elt.append(e)
        return elt

    def apply_mappings(self, record_id_map, coll_id_map, media_root_mappings):
        root = self.get_elt()
        for event, elt in etree.iterwalk(root, events=("start",)):
            attrib = elt.attrib
            data_type = attrib.get('data-type', None)
            if data_type == 'file':
                src = attrib.get('data-src', None)
                if src is not None:
                    src = apply_media_mappings(src, media_root_mappings)
                    attrib['data-src'] = src
            elif data_type == 'link':
                linktype = attrib.get('data-linktype', '')
                target = attrib.get('data-target', '')
                mapped_target = None
                if linktype == 'file':
                    mapped_target = apply_media_mappings(target, media_root_mappings)
                elif linktype == 'record':
                    mapped_target = record_id_map.get(target, target)
                elif linktype == 'collection':
                    mapped_target = coll_id_map.get(target, target)
                if mapped_target is not None:
                    attrib['data-target'] = mapped_target
        self.content = self.content_from_elt(root)

    def to_json(self):
        result = {
            "type": self.field_type,
            "name": self.name,
            "content": self.content,
        }
        return result


    def __str__(self):
        return "%s(type=%s, name=%s, %d bytes)" % \
                (self.__class__.__name__, self.field_type, self.name,
                 len(self.content))


class TitleField(FlatTextField):
    field_type = 'title'
    defname = "Record Title"


class NumberField(FlatTextField):
    field_type = 'number'
    defname = "Number"





class BaseFieldItem(RecordItem):
    tag = 'field'

    def set_properties_from_elt(self, elt, names, level, count, closing):
        RecordItem.set_properties_from_elt(self, elt, names, level, count, closing)
        assert not self.closing
        self.type = elt.get('type') or ''
        self.repeat = elt.get('repeat') or ''

    def set_properties_from_form(self, num, params=None):
        RecordItem.set_properties_from_form(self, num, params=params)
        assert not self.closing
        self.type = param_from_form('ft_%d' % num, params=params)
        self.repeat = param_from_form('fr_%d' % num, required=False,
                                      params=params)

    def get_elt(self):
        elt = RecordItem.get_elt(self)
        setelt(elt, 'type', self.type)
        setelt(elt, 'repeat', self.repeat)
        return elt

    def flatten(self):
        if self.summary is None:
            return
        return [(self.flatname + "_" + self.fieldtype, self.summary)]

    def search_url(self, url_fn):
        """Get the URL for a search for this field value, within the collection
        currently being viewed, if any.

        """
        p = self.search_params()
        if p is None:
            return None
        coll_id = get_lockto_collid()
        if coll_id is not None:
            p['collid'] = coll_id
        p['act'] = 'search'
        return url_fn('search', **p)

    def search_params(self):
        """Generate the filter parameters for a search for this field value,
        or None if no direct search possible.

        """
        return None


class SimpleFieldItem(BaseFieldItem):
    def set_properties_from_elt(self, elt, names, level, count, closing):
        BaseFieldItem.set_properties_from_elt(self, elt, names, level, count, closing)
        assert not self.closing
        self.text = elt.text

    def set_properties_from_form(self, num, params=None):
        BaseFieldItem.set_properties_from_form(self, num, params=params)
        assert not self.closing
        self.text = param_from_form('f_%d' % num, params=params)

    def get_elt(self):
        elt = BaseFieldItem.get_elt(self)
        elt.text = self.text
        return elt

    @property
    def summary(self):
        return self.text


class DateFieldItem(SimpleFieldItem):
    fieldtype = 'date'
    defname = "Date"

    def flatten(self):
        text = self.summary
        if text is None:
            return
        date, err = utils.parsedate.parse_date(text)
        result = []
        if date is not None:
            result.append((self.flatname + '_' + self.fieldtype, str(date)))
        if err is not None:
            result.append((self.flatname + '_' + self.fieldtype + '_error', err))
        return result

    def search_params(self):
        """Generate the filter parameters for a search for this field value,
        or None if no direct search possible.

        """
        text = self.summary
        date, err = utils.parsedate.parse_date(text)
        if date is None:
            return None
        return {'q1f': self.flatname + '_' + self.fieldtype, 'q1m': str(date), 'qs': '1'}

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es

        parsed, err = utils.parsedate.parse_date(value)
        if err:
            raise ValidationError("Can't parse date \"%s\"" % value)
        start, end = map(str, (parsed.start, parsed.end))
        if start == end:
            desc = '%s is %s' % (':'.join(names), start)
        else:
            desc = '%s is between %s and %s' % (':'.join(names), start, end)
        return (client.field(fieldname).range(start, end), desc)

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        return []


class TagFieldItem(SimpleFieldItem):
    fieldtype = 'tag'
    defname = "Tags"

    def search_params(self):
        """Generate the filter parameters for a search for this field value,
        or None if no direct search possible.

        """
        return {'q1f': self.flatname + '_' + self.fieldtype, 'q1m': self.summary, 'qs': '1'}

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es

        return client.field(fieldname).is_in(value), '%s is %s' % (':'.join(names), value)

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_tag'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        # FIXME - do a more efficient case-insensitive match
        info = baseq.calc_occur(group, '').check_at_least(-1).info
        partial_lower = partial.lower()
        items = []
        for item in info[0]['counts']:
            if item[0].lower().startswith(partial_lower):
                items.append(item[0])
                if len(items) >= 10:
                    break
        items.sort()
        return items


class LinkFieldItem(SimpleFieldItem):
    fieldtype = 'link'
    defname = "Link"

    def set_properties_from_elt(self, elt, names, level, count, closing):
        SimpleFieldItem.set_properties_from_elt(self, elt, names, level, count, closing)
        self.linktype = elt.get('linktype') or ''
        self.target = elt.get('target') or ''

    def set_properties_from_form(self, num, params=None):
        SimpleFieldItem.set_properties_from_form(self, num, params=params)
        self.linktype = param_from_form('linktype_%d' % num, required=False,
                                        params=params) or ''
        self.target = param_from_form('target_%d' % num, required=False,
                                      params=params) or ''

    def get_elt(self):
        elt = SimpleFieldItem.get_elt(self)
        setelt(elt, 'linktype', self.linktype)
        setelt(elt, 'target', self.target)
        return elt

    def flatten(self):
        result = []
        if self.summary:
            result.append((self.flatname + '_' + self.fieldtype, self.summary))
        if self.target:
            result.append(('text', self.target))
        return result

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es
        return (
            client.field(fieldname).text(value, op='or'),
            '%s matches %s' % (':'.join(names), value),
        )

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_link'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        # FIXME - do a more efficient case-insensitive match
        info = baseq.calc_occur(group, '').check_at_least(-1).info
        partial_lower = partial.lower()
        items = []
        for item in info[0]['counts']:
            if item[0].lower().startswith(partial_lower):
                items.append(item[0])
                if len(items) >= 10:
                    break
        items.sort()
        return items


def intfromelt(elt, name):
    val = elt.get(name)
    try:
        return int(val)
    except ValueError:
        raise ValidationError("Invalid value for attribute %r: %r" % (name, val))

def flatten_file(mediaitem):
    if mediaitem.mimetype is None:
        return None

    if mediaitem.mimetype.startswith('image/'):
        filetype = 'image'
    elif mediaitem.mimetype.startswith('video/'):
        filetype = 'video'
    elif mediaitem.mimetype.startswith('audio/'):
        filetype = 'audio'
    else:
        filetype = 'media'
    return dict(
        id = mediaitem.src,
        type = filetype,
        fileid = mediaitem.src,
        mimetype = mediaitem.mimetype,
        filealt = [mediaitem.alt],
        filetitle = [mediaitem.title],
        rotate = [mediaitem.rotate]
    )

class FileFieldItem(BaseFieldItem):
    fieldtype = 'file'
    defname = "File"

    def set_properties_from_elt(self, elt, names, level, count, closing):
        BaseFieldItem.set_properties_from_elt(self, elt, names, level, count, closing)
        assert not self.closing
        self.mimetype = elt.get('mimetype') or ''
        self.src = elt.get('src') or ''
        self.display = elt.get('display') or ''
        self.alt = elt.get('alt') or elt.get('title') or ''
        self.title = elt.get('title') or elt.get('alt') or ''
        self.rotate = elt.get('rotate') or ''
        self._summary = None
        areas = elt.findall('area')
        self._areas = [dict(x1=intfromelt(a, 'x1'),
                            y1=intfromelt(a, 'y1'),
                            x2=intfromelt(a, 'x2'),
                            y2=intfromelt(a, 'y2'),
                            src=a.get('src'),
                            title=a.get('title'))
                        for a in areas]

    def set_properties_from_form(self, num, params=None):
        BaseFieldItem.set_properties_from_form(self, num, params=params)
        assert not self.closing
        self.mimetype = param_from_form('mimetype_%d' % num, required=False, params=params) or ''
        self.src = param_from_form('src_%d' % num, required=False, params=params) or ''
        self.display = param_from_form('display_%d' % num, required=False, params=params) or ''
        self.alt = param_from_form('alt_%d' % num, required=False, params=params) or ''
        self.title = param_from_form('title_%d' % num, required=False, params=params) or ''
        self.rotate = param_from_form('rotate_%d' % num, required=False, params=params) or ''
        self._summary = None

    def get_elt(self):
        elt = BaseFieldItem.get_elt(self)
        setelt(elt, 'mimetype', self.mimetype)
        setelt(elt, 'src', self.src)
        setelt(elt, 'display', self.display)
        setelt(elt, 'alt', self.alt)
        setelt(elt, 'title', self.title)
        setelt(elt, 'rotate', self.rotate)
        return elt

    @property
    def areas(self):
        return self._areas

    @property
    def display_textual_summary(self):
        if self.src is not None and self.src.endswith('.txt'):
            return True
        return False

    @property
    def summary(self):
        if self._summary is None:
            self._summary = ' '.join((self.title, self.alt))
            if self.src is not None and self.src.endswith('.txt'):
                try:
                    # FIXME - this pulls in the first 10K of the file to use as
                    # text to search for.  Pretty foul hack - probably should
                    # index the file as a distinct object, with proper document
                    # converters.
                    self._summary += ' ' + open(self.src).read()[:1024 * 10]
                except IOError:
                    pass
            else:
                self._summary += ' ' + self.src.replace('/', ' ') \
                                 .replace(':', ' ')
        return self._summary

    def media(self):
        return [MediaItem(self.src, self.mimetype, self.alt, self.title,
                          self.display, self.rotate)]

    def flatten(self):
        result = [(self.flatname + '_' + self.fieldtype, self.summary),
                  ('text', self.summary),
                  ('fileid', self.src),
                  ('filealt', self.alt),
                  ('filetitle', self.title),
                 ]
        for mediaitem in self.media():
            flat = flatten_file(mediaitem)
            if flat is not None:
                fileid = flat.get('fileid')
                if fileid:
                    result.append(('fileid', fileid))
                result.append(flat)
        return result

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es
        return (
            client.field(fieldname).text(value, op='or'),
            '%s matches %s' % (':'.join(names), value),
        )

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_file'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        # FIXME - do a more efficient case-insensitive match
        info = baseq.calc_occur(group, '').check_at_least(-1).info
        partial_lower = partial.lower()
        items = []
        for item in info[0]['counts']:
            if item[0].lower().startswith(partial_lower):
                items.append(item[0])
                if len(items) >= 10:
                    break
        items.sort()
        return items




class LocationFieldItem(SimpleFieldItem):
    fieldtype = 'location'
    defname = "Location"

    def set_properties_from_elt(self, elt, names, level, count, closing):
        SimpleFieldItem.set_properties_from_elt(self, elt, names, level, count, closing)
        self.latlong = elt.get('latlong') or ''

    def set_properties_from_form(self, num, params=None):
        SimpleFieldItem.set_properties_from_form(self, num, params=params)
        self.latlong = param_from_form('latlong_%d' % num, required=False, params=params) or ''

    def get_elt(self):
        elt = SimpleFieldItem.get_elt(self)
        setelt(elt, 'latlong', self.latlong)
        return elt

    @property
    def summary(self):
        return self.text or self.latlong

    def flatten(self):
        flat = []
        if self.text:
            flat.append((self.flatname + '_' + self.fieldtype, self.text))
#        if self.latlong:
#            flat.append((self.flatname + '_latlong', self.latlong))
        if not flat:
            return
        return flat

    def search_params(self):
        """Generate the filter parameters for a search for this field value,
        or None if no direct search possible.

        """
        # if self.latlong:
        #     return {'q1f': self.flatname + '_latlong', 'q1m': self.latlong, 'qs': '1'}
        return {'q1f': self.flatname + '_' + self.fieldtype, 'q1m': self.text, 'qs': '1'}

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es

        return client.field(fieldname).is_in(value), '%s is %s' % (':'.join(names), value)

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_' + 'location'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        # FIXME - do a more efficient case-insensitive match
        info = baseq.calc_occur(group, '').check_at_least(-1).info
        partial_lower = partial.lower()
        items = []
        for item in info[0]['counts']:
            if item[0].lower().startswith(partial_lower):
                items.append(item[0])
                if len(items) >= 10:
                    break
        items.sort()
        return items


class TextFieldItem(BaseFieldItem):
    fieldtype = 'text'
    defname = "Text"

    def set_properties_from_elt(self, elt, names, level, count, closing):
        BaseFieldItem.set_properties_from_elt(self, elt, names, level, count, closing)
        assert not self.closing
        content = []

        # The following is a horrible hack to remove the xmlns from the
        # elements when presented in the edit box.

        if elt.text:
            tmp = etree.Element('a')
            tmp.text = elt.text
            tmp = etree.tostring(tmp, encoding=unicode)
            tmp = tmp[3:-4]
            content.append(tmp)
        for e in elt:
            item = etree.tostring(e, encoding=unicode)
            content.append(item)
        self._content = u''.join(content)

    def set_properties_from_form(self, num, params=None):
        BaseFieldItem.set_properties_from_form(self, num, params=params)
        assert not self.closing
        content = []
        val = param_from_form('f_%d' % num, params=params)
        if val != '':
            content.extend(clean_html(val))
        self._content = u''.join(content)

    def get_elt(self):
        elt = BaseFieldItem.get_elt(self)
        val = '<root>' + self._content + '</root>'
        val = etree.fromstring(val)
        if val.text:
            elt.text = val.text
        for e in val:
            elt.append(e)
        return elt

    @property
    def summary(self):
        frag = lxml.html.fragment_fromstring(self._content,
                                            create_parent="div")
        text = []
        for el in frag.iter():
            inline = el.tag in inline_tags
            if el.text:
                if not inline:
                    text.append(' ')
                text.append(unicode(el.text))
            if el.tail:
                if not inline:
                    text.append(' ')
                text.append(unicode(el.tail))
        return u''.join(text)

    @property
    def raw_content(self):
        return self._content

    def display_content(self, recordid, url_fn):
        """Get the HTML to use to display the field contents.

        :param recordid: The recorid to display.
        :param url_fn: A function which creates a url for a view.

        """
        doc = self.get_elt()
        for elt in _datatype_pattern(doc):
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

                if src:
                    wrap_elt(elt, 'a', dict(
                        href=url_fn("record-gallery", id=recordid, show=src),
                        target="_blank",
                    ))
                
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
                    if mimetype.startswith('image/'):
                        attrib['href'] = url_fn("record-gallery", id=recordid,
                                                show=target)
                    else:
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

    def media(self):
        result = []
        elt = self.get_elt()
        for item in elt.xpath('//img[@data-type="file"]'):
            mediaitem = MediaItem(item.get('data-src', ''),
                                  item.get('data-mimetype', ''),
                                  item.get('data-alt', ''),
                                  item.get('data-title', ''),
                                  item.get('data-display', ''),
                                  item.get('data-rotate', ''),
                                 )
            result.append(mediaitem)

        for item in elt.xpath('//a[@data-type="link"]'):
            linktype = item.get('data-linktype', '')
            if linktype == 'file':
                mediaitem = MediaItem(item.get('data-target', ''),
                                      item.get('data-mimetype', ''),
                                      '',
                                      item.xpath("string()").strip(),
                                      item.get('data-display', ''),
                                      item.get('data-rotate', ''),
                                     )
                result.append(mediaitem)

        return result

    def flatten(self):
        if self.summary is None:
            return
        result = [(self.flatname + '_' + self.fieldtype, self.summary)]
        for media in self.media():
            flat = flatten_file(media)
            if flat is not None:
                fileid = flat.get('fileid')
                if fileid:
                    result.append(('fileid', fileid))
                result.append(flat)
        return result

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es

        return (
            client.field(fieldname).text(value, op='or'),
            '%s matches %s' % (':'.join(names), value),
        )

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_text'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        info = baseq.calc_occur(group, partial).check_at_least(-1).info
        items = [partial + item[0] for item in info[0]['counts'][:10]]
        items.sort()
        return items


class TitleFieldItem(SimpleFieldItem):
    fieldtype = 'title'
    defname = "Record Title"

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es
        return (
            client.field(fieldname).text(value, op='or'),
            '%s matches %s' % (':'.join(names), value),
        )

    @staticmethod
    def autocomplete(target, fieldconfigs, fieldname, partial):
        fieldname = fieldname + '_' + 'title'
        fieldconfig = fieldconfigs.get(fieldname, None)
        if fieldconfig is None:
            return []
        group = fieldconfig.get('group', None)
        if group is None:
            return []
        baseq = target.filter(Field(fieldname).exists())
        # FIXME - do a more efficient case-insensitive match
        info = baseq.calc_occur(group, '').check_at_least(-1).info
        partial_lower = partial.lower()
        items = []
        for item in info[0]['counts']:
            if item[0].lower().startswith(partial_lower):
                items.append(item[0])
                if len(items) >= 10:
                    break
        items.sort()
        return items


class NumberFieldItem(SimpleFieldItem):
    fieldtype = 'number'
    defname = "Number"

    def flatten(self):
        if self.summary is None:
            return
        val = self.summary
        fullname = self.flatname + '_' + self.fieldtype
        result = []
        try:
            result.append((fullname, float(val)))
        except ValueError, e:
            # Give an invalid value, which will be stored as an error in
            # restpose.
            result.append((fullname, 'error'))

        return result

    @classmethod
    def search_from_params(cls, client, names, value):
        fieldname = flatten_name(names) + '_' + cls.fieldtype
        es = existence_search(client, fieldname, names, value)
        if es is not None:
            return es

        field = client.field(fieldname)
        descnames = ':'.join(names)

        try:
            # Check for a single value
            floatval = float(value)
            return (
                field.range(floatval, floatval),
                '%s equals %s' % (descnames, value),
            )
        except ValueError: pass

        if '-' in value:
            val1, val2 = value.split('-', 1)
            try:
                val1f = float(val1)
                val2f = float(val2)
            except ValueError:
                raise ValidationError("Can't parse number range \"%s\"" % value)

            return (
                field.range(val1f, val2f),
                '%s between %s and %s' % (descnames, val1, val2),
            )

        raise ValidationError("Can't parse numeric search \"%s\" "
                              "(must be of the form NUM or NUM-NUM)" % value)


field_item_types = dict(
    date = DateFieldItem,
    tag = TagFieldItem,
    link = LinkFieldItem,
    file = FileFieldItem,
    location= LocationFieldItem,
    text = TextFieldItem,
    title = TitleFieldItem,
    number = NumberFieldItem,
)

field_types = dict((cls.field_type, cls) for cls in (
    DateField,
    TagField,
    LinkField,
    FileField,
    LocationField,
    TextField,
    TitleField,
    NumberField,
))
