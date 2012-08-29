#!/usr/bin/env python

"""Script to strip xml namespaces from all xml files in a tree."""

from lxml import etree
import os
import StringIO

EXPL_NS = u"http://exploratour.org/schema/1"
EXPL_NS_B = u"{%s}" % EXPL_NS

def strip_ns(path):
    print "Stripping namespace from " + path
    tree = etree.parse(open(path))
    root = tree.getroot()

    if not root.tag.startswith(EXPL_NS_B):
        root.tag = EXPL_NS_B + root.tag

    for elt in root.iter():
        if elt.tag.startswith(EXPL_NS_B):
            elt.tag = elt.tag[len(EXPL_NS_B):]
        elt.tag = EXPL_NS_B + elt.tag

    new_root = etree.Element(root.tag, root.attrib)
    new_root[:] = root[:]
    root = new_root

    doc = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    tree = etree.parse(StringIO.StringIO(doc))
    root = tree.getroot()

    for elt in root.iter():
        if elt.tag.startswith(EXPL_NS_B):
            elt.tag = elt.tag[len(EXPL_NS_B):]

    new_root = etree.Element(root.tag, root.attrib)
    new_root[:] = root[:]
    root = new_root

    fd = open(path + ".tmp", "wb")
    try:
        fd.write(etree.tostring(root, encoding="UTF-8", xml_declaration=True))
    finally:
        fd.close()
    os.rename(path + '.tmp', path)

def strip_dir(dir):
    for dirpath, dirnames, filenames in os.walk(dir):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if path.endswith('.xml'):
                strip_ns(path)
            else:
                print "Ignoring " + path

if __name__ == '__main__':
    import sys
    strip_dir(sys.argv[1])
