from apps.fields.fields import RecordItem_from_form
from apps.record.errors import ValidationError
from apps.shortcuts import getparam, listify_values
from apps.store.models import Record, Collection, Template
from lxml import etree
import lxml.html
try:
    from simplejson import json
except ImportError:
    import json

def copy_elt_without_values(root, keep=None):
    """Copy an XML element tree for part of a record without the values.

    Used when editing to make a new empty instance of part of a record.

    """
    if keep is None:
        keep = ()
    else:
        keep = tuple(keep)
    keep = (u'name', u'type') + keep
    stack = [etree.Element('root')]
    for event, elt in etree.iterwalk(root, events=("start", "end")):
        if event == 'start':
            newelt = etree.SubElement(stack[-1], elt.tag)
            for k, v in elt.attrib.iteritems():
                if k in keep:
                    newelt.set(k, v)
            stack.append(newelt)
        elif event == 'end':
            del stack[-1]
    assert len(stack) == 1
    return stack[0][0]

def indent_previous(stack, offset=0):
    parent = stack[-1]['item']
    depth = (len(stack) - 1 + offset) * 2
    if parent.tag == u'group':
        if len(parent) != 0:
            prev = parent[-1]
            prev.tail = '\n' + " " * depth
        else:
            parent.text = '\n' + " " * depth

def record_from_simple_request(params):
    # Iterate through the parameters in order, getting the values and adding
    # them to the record.  The stack is used for groups.
    result = Record()
    ordering = map(int, filter(lambda x: x != '', getparam('ordering', '', params=params).split(',')))
    stack = [dict(item=result.root, repeat=False, remove=False, num=None)]
    for num in ordering:
        item = RecordItem_from_form(num, params=params)

        repeat = (getparam('repeat_%d' % num, '', params=params) != '')
        remove = (getparam('remove_%d' % num, '', params=params) != '')

        if item.tag == u'field':
            if remove:
                continue
            indent_previous(stack)
            elt = item.get_elt()
            stack[-1]['item'].append(elt)
            if repeat:
                # Special case for the "display" attribute - preserve it, for
                # file fields.
                newelt = copy_elt_without_values(elt, keep=('display',))
                indent_previous(stack)
                stack[-1]['item'].append(newelt)

        elif item.tag == u'group':
            if num == stack[-1]['num']:
                if len(stack) <= 1:
                    raise ValidationError("More groups closed than opened")
                indent_previous(stack, -1)
                if stack[-1]['remove']:
                    del stack[-2]['item'][-1]
                elif stack[-1]['repeat']:
                    # Repeat this element.
                    newgroup = copy_elt_without_values(stack[-1]['item'])
                    indent_previous(stack[:-1])
                    stack[-2]['item'].append(newgroup)
                del stack[-1]
            else:
                indent_previous(stack)
                elt = item.get_elt()
                stack[-1]['item'].append(elt)
                stack.append(dict(item=elt, repeat=repeat, remove=remove,
                                  num=num))

    return result

class FormValidator(object):
    def __init__(self, params):
        self.params = listify_values(params)

    def require_param(self, param):
        vals = self.params.get(param, None)
        if vals is None or len(vals) == 0:
            raise ValidationError("Parameter \"%s\" missing from request" % param)
        return vals

    def require_unique_param(self, param):
        vals = self.params.get(param, None)
        if vals is None or len(vals) == 0:
            raise ValidationError("Parameter \"%s\" missing from request" % param)
        if len(vals) != 1:
            raise ValidationError("Duplicate values for parameter \"%s\" in request" % param)
        return vals[0]

class RecordValidator(FormValidator):
    """Get a record from a set of parameters.

    Used to return a partially edited record back to the browser.

    """
    def __init__(self, params, remcoll):
        super(RecordValidator, self).__init__(params)
        self._get_collections()
        if remcoll is not None:
            self.invalid_collections.remove(remcoll)
            self.collections = tuple(sorted(filter(lambda x: x != remcoll,
                                            self.collections)))

    def _validate_xml(self):
        inner_xml = self.require_unique_param('inner_xml')

        result = Record()
        etree.clear_error_log()
        try:
            result.inner_xml = inner_xml.strip()
        except etree.XMLSyntaxError, e:
            entry = e.error_log.last_error
            raise ValidationError("Invalid XML supplied: %s, "
                                  "at line %d, character %d" %
                                  (entry.message, entry.line - 1, entry.column))
        return result

    def _validate_simple(self):
        result = record_from_simple_request(self.params)
        return result

    def validate(self):
        # FIXME - check csrf token
        fmt = self.require_unique_param('fmt')

        if fmt == 'xml':
            result = self._validate_xml()
        elif fmt == 'simple':
            result = self._validate_simple()
        else:
            raise ValidationError("Invalid value for 'fmt' parameter")

        if self.invalid_collections:
            raise ValidationError("Collection id '%s' not found" %
                                  (self.invalid_collections[0],))

        result.id = self.id
        result.collections = self.collections
        return result

    @property
    def id(self):
        id = self.params.get('id', None)
        if id is None or len(id) == 0 or len(id[0]) == 0:
            return None
        return id[0]

    @property
    def title(self):
        return "Record %s" % self.id

    def _get_collections(self):
        self.invalid_collections = []

        remcolls = set(self.params.get('remcoll', ()))
        collids = set(filter(lambda x: x != u'' and x not in remcolls,
                             self.params.get('collid', ())))
        colltitle = set(filter(lambda x: x != u'',
                               self.params.get('colltitle', ())))

        for title in colltitle:
            colls = Collection.find_by_title(title)
            if len(colls) == 0:
                self.invalid_collections.append(title)
            for coll in colls:
                if coll.id not in remcolls:
                    collids.add(coll.id)

        self.collections = collids
