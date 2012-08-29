import copy
from lxml.html.clean import Cleaner
from lxml.html import fromstring, defs, html_parser
from lxml.etree import XPath, Element, tostring
from StringIO import StringIO
import re

XHTML_NS = "http://www.w3.org/1999/xhtml"
_style_pattern = XPath("descendant-or-self::*[@style]")
_styleclean_re = re.compile(r"^\s*([^\s:]+):\s*(.*)\s*$")
_colorsafe_re = re.compile(r"^#([0-9abcdef]{3}[0-9abcdef]{3}?)$")
_colorsafe_rgb_re = re.compile(r"^\s*rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*$")
cleaner = Cleaner(style=False, safe_attrs_only=False)

def nons(tag):
    """Strip the xhtml namespace off the tag"""
    if tag[0] == '{' and tag[1:len(XHTML_NS)+1] == XHTML_NS:
        return tag.split('}', 1)[-1]
    return tag

def hastexttail(elem):
    return (elem.text is not None and len(elem.text) != 0) or \
           (elem.tail is not None and len(elem.tail) != 0)

def worthless(elem):
    if nons(elem.tag) in ('span', 'body') and len(elem.attrib) == 0:
        return True
    return False

def clean_classes(elem):
    def pick(x):
        if x in ('', 'Apple-style-span'):
            return False
        if x.startswith('exp_'):
            # Classes used by exploratour to make links look right in the
            # editor.
            return False
        return True
    classes = filter(pick, elem.get('class', '').split(' '))
    if len(classes) == 0:
        try:
            del elem.attrib['class']
        except KeyError: pass
    else:
        elem.attrib['class'] = ' '.join(classes)

def clean(html):
    assert isinstance(html, basestring)

    if html.strip() == '':
        return ''
    doc = fromstring(html)

    # Remove all unsafe attrs other than style (which we'll handle later).
    safe_attrs = set(defs.safe_attrs)
    safe_attrs.add('style')
    for elem in doc.iter():
        attrib = elem.attrib
        for aname in attrib.keys():
            if aname not in safe_attrs and not aname.startswith('data-'):
                del attrib[aname]
        if attrib.get('data-type', None) == 'file':
            try:
                del attrib['src']
            except KeyError:
                pass
        clean_classes(elem)

    # Handle all style attrs; filter out non-allowed forms
    for elem in _style_pattern(doc):
        styles = []
        wrap_in = []
        def add_wrap(tag, attrs={}):
            wrap_in.append((tag, attrs))
        for style in elem.get('style').split(';'):
            mo = _styleclean_re.match(style)
            if not mo: continue
            name, value = map(lambda x: x.lower(), mo.groups())
            if name == 'text-decoration':
                if value == 'underline':
                    add_wrap('u')
                    continue
                if value == 'line-through':
                    add_wrap('strike')
                    continue
            if name == 'color' or name == 'background-color':
                mo = _colorsafe_re.match(value)
                if mo:
                    color = mo.groups()[0]
                    styles.append(name + ':#' + color)
                    continue
                mo = _colorsafe_rgb_re.match(value)
                if mo:
                    col_r, col_g, col_b = map(lambda x: int(x), mo.groups()[0:3])
                    styles.append(name + ':rgb(%d,%d,%d)' % (col_r, col_g, col_b))
                    continue
            # Ignore any other styles

        # Set style attribute to new value
        if len(styles) != 0:
            elem.attrib['style'] = ';'.join(styles)
        else:
            del elem.attrib['style']

        # Wrap the element in others, if specified
        if wrap_in:
            for tag, attrs in wrap_in:
                tail = elem.tail
                elem.tail = ''
                elemcopy = copy.deepcopy(elem)
                elem.clear()
                elem.tag = tag
                elem.attrs = attrs
                elem.append(elemcopy)
                elem.tail = tail
                elem = elemcopy

    cleaner(doc)
    for elem in doc.iter():
        if elem.text is not None:
            elem.text = elem.text.replace('\r\n', '\n')
        if elem.tail is not None:
            elem.tail = elem.tail.replace('\r\n', '\n')

    it = doc.iter()
    it.next()
    try:
        while True:
            elem = it.next()
            if worthless(elem) and not hastexttail(elem):
                #print "Dropping %r" % elem
                elem.drop_tag()
                it = doc.iter()
                it.next()
    except StopIteration:
        pass

    if worthless(doc):
        result = []
        if doc.text:
            result.append(unicode(doc.text))
        for elem in doc:
            result.append(tostring(elem, encoding=unicode))
        if doc.tail:
            result.append(unicode(doc.tail))
    else:
        result = [tostring(doc, encoding=unicode)]

    #print "Result: %r" % result
    return result
