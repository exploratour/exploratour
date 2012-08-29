from lxml import etree
import os.path
import os

def rename(filepath, srcext, destext):
    if os.name == 'nt':
        # Can't rename to existing files, so we have to move the old one, then
        # rename, then delete the old one.
        if os.path.exists(filepath + destext):
            if os.path.exists(filepath + '.bak'):
                os.unlink(filepath + '.bak')
            os.rename(filepath + destext, filepath + ".bak")
            os.rename(filepath + srcext, filepath + destext)
            os.unlink(filepath + ".bak")
        else:
            os.rename(filepath + srcext, filepath + destext)
    else:
        os.rename(filepath + srcext, filepath + destext)

class XmlStore(object):
    class CachedTree(object):
        """A cached XML tree, with some properties.

        """
        __slots__ = ("tree", "modified")
        def __init__(self, tree, modified=False):
            self.tree = tree
            self.modified = modified

        def __len__(self):
            return len(self.tree.getroot())

        def write(self, filepath):
            """Write the cached tree to a given filepath.

            The ".xml" extension is added to the end of the filepath.

            """
            if not os.path.exists(os.path.dirname(filepath)):
                os.makedirs(os.path.dirname(filepath))
            fd = open(filepath + ".tmp", "wb")
            try:
                self.tree.write(fd, encoding="UTF-8", xml_declaration=True)
            finally:
                fd.close()

            # Atomic replace of the old file with the new one.
            rename(filepath, ".tmp", ".xml")
            self.modified = False

        def set(self, record):
            """Set a record.

            The record must be an Element, with the "id" property set to the id
            for the record.

            """
            self.modified = True
            record_id = record.get(u'id')
            assert record_id is not None
            old = self.tree.xpath('/*/*[@id=$id]', id=record_id)
            if len(old) != 0:
                old[0].getparent().remove(old[0])
            self.tree.getroot().append(record)

        def remove(self, id):
            """Remove the record with the given id.

            Raises KeyError if the record isn't found.

            """
            self.modified = True
            old = self.tree.xpath('/*/*[@id=$id]', id=id)
            if len(old) == 0:
                raise KeyError("Key with id %r not found" % id)
            assert len(old) == 1
            old[0].getparent().remove(old[0])

        def get(self, id):
            """Get the record with the given id.

            Raises KeyError if the record isn't found.

            """
            old = self.tree.xpath('/*/*[@id=$id]', id=id)
            if len(old) == 0:
                raise KeyError("Key with id %r not found" % id)
            assert len(old) == 1
            return old[0]

    class Cache(object):
        """A cache of parsed XML files.

        """
        def __init__(self):
            self.cache = {}

        def __del__(self):
            """Flush any modified trees on delete.

            Don't write code relying on this method; it's here to try and
            prevent dataloss, but you should always call flush() (or clear())
            explicitly before exiting.

            """
            self.flush()

        def flush(self):
            """Write any modified trees in the cache to disk.

            """
            for filepath, tree in self.cache.iteritems():
                if tree.modified:
                    tree.write(filepath)

        def clear(self):
            """Clear the cache, flushing any modified trees.

            """
            self.flush()
            self.cache = {}

        def get(self, filepath):
            """Get a tree from the cache.

            Returns a CachedTree, creating an empty one if the file didn't
            exist.

            """
            tree = self.cache.get(filepath, None)
            if tree is not None:
                return tree

            # Clear the cache - for now, we only keep one parsed file in it,
            # but this could easily be modified in future.
            self.clear()

            if os.path.exists(filepath + '.xml'):
                fd = open(filepath + '.xml', "rb")
                try:
                    tree = XmlStore.CachedTree(etree.parse(fd))
                finally:
                    fd.close()
            elif os.path.exists(filepath + '.bak'):
                # This can happen on windows if we crashed after renaming the
                # old file away, but before writing the new one.
                fd = open(filepath + '.bak', "rb")
                try:
                    tree = XmlStore.CachedTree(etree.parse(fd))
                finally:
                    fd.close()
            else:
                # Make an empty container tree.
                # Don't mark it as modified, because if no entries get put into
                # it, we don't want to write it back.
                xmltree = etree.ElementTree(etree.Element("container"))
                tree = XmlStore.CachedTree(xmltree)
            self.cache[filepath] = tree
            return tree

    def __init__(self, topdir, items_per_file=100):
        """Make a new XML store, in the directory given by topdir.

        The XML store stores the records it is given in a set of XML files.  It
        puts at most `items_per_file` items in each file.

        """
        self.topdir = topdir

        # Dictionary mapping from id to file number.
        self.idmap = {}
        self.idmap_modified = False

        # Meta info dictionary.
        self.meta = {}

        # Next file number to allocate.
        self.next_num = 0

        # Number of files to put in each directory.
        self.files_per_dir = 10

        # Number of items to put in each file.
        self.items_per_file = items_per_file

        # Cache of parsed files.
        self.tree_cache = XmlStore.Cache()

        # Read the idmap from idmap.xml
        self.idmap_path = os.path.join(self.topdir, 'idmap')

        fd = None
        if os.path.exists(self.idmap_path + ".xml"):
            fd = open(self.idmap_path + ".xml", "rb")
        elif os.path.exists(self.idmap_path + ".bak"):
            fd = open(self.idmap_path + ".bak", "rb")
        if fd is not None:
            try:
                idmap_xml = etree.parse(fd)
            finally:
                fd.close()
            for elt in idmap_xml.xpath(u'/*/id'):
                num = int(elt.text)
                self.idmap[elt.get(u'id')] = num
                if num > self.next_num:
                    self.next_num = num
            for elt in idmap_xml.xpath(u'/*/meta'):
                self.meta[elt.get(u'name')] = elt.text

    def __del__(self):
        """Flush any modified trees on delete.

        Don't write code relying on this method; it's here to try and
        prevent dataloss, but you should always call flush() or close()
        explicitly before exiting.

        """
        self.flush()
 
    def __len__(self):
        return len(self.idmap)

    def __iter__(self):
        keys = self.idmap.keys()
        keys.sort()
        for key in keys:
            yield key

    def close(self):
        """Cleanup, flushing all changes to disk, and dropping any cache items.

        """
        self.flush()
        self.tree_cache.clear()
        self.idmap = None

    def flush(self):
        """Flush all changes to disk.

        """
        if self.idmap_modified:
            map = etree.Element("idmap")
            for id in sorted(self.idmap.keys()):
                elt = etree.SubElement(map, "id")
                elt.set('id', id)
                elt.text = unicode(self.idmap[id])
            for name in sorted(self.meta.keys()):
                elt = etree.SubElement(map, "meta")
                elt.set('name', name)
                elt.text = unicode(self.meta[name])
            map = etree.ElementTree(map)

            if not os.path.exists(os.path.dirname(self.idmap_path)):
                os.makedirs(os.path.dirname(self.idmap_path))
            fd = open(self.idmap_path + ".tmp", "wb")
            try:
                map.write(fd, encoding="UTF-8", xml_declaration=True)
            finally:
                fd.close()

            # Atomic replace of the old file with the new one.
            rename(self.idmap_path, ".tmp", ".xml")
            self.idmap_modified = False

        self.tree_cache.flush()

    def _num_to_path(self, filenum):
        """Convert a file number to the path for that file.

        Returns the path without the extension.

        """
        components = []
        while filenum >= self.files_per_dir:
            components.append(filenum % self.files_per_dir)
            filenum = filenum // self.files_per_dir
        components.append(filenum)
        components.reverse()
        result = []
        for c in components[:-1]:
            result.append("D%d" % c)
        result.append("F%d" % components[-1])
        return os.path.join(self.topdir, *result)

    def _get_tree(self, filenum):
        """Get the tree for a given filenum.

        """
        return self.tree_cache.get(self._num_to_path(filenum))

    def set(self, record):
        """Set a record.

        `record` should be an lxml Element object, or a unicode string
        containing raw XML.  The record must have an "id" attribute containing
        the ID to use.

        If a record with the same id already exists, it is replaced.

        """
        assert not isinstance(record, str)
        if isinstance(record, unicode):
            record = etree.fromstring(record)

        id = record.get(u'id')
        assert id is not None

        filenum = self.idmap.get(id, None)
        if filenum is None:
            filenum = self.next_num
            tree = self._get_tree(filenum)
            if len(tree) >= self.items_per_file:
                self.next_num += 1
                filenum = self.next_num
                tree = self._get_tree(filenum)

            self.idmap[id] = filenum
            self.idmap_modified = True
        else:
            tree = self._get_tree(filenum)

        tree.set(record)

    def remove(self, id):
        """Remove the record with a given id.

        Raises KeyError if the record isn't found.

        """
        filenum = self.idmap[id]
        tree = self._get_tree(filenum)
        tree.remove(id)
        del self.idmap[id]
        self.idmap_modified = True

    def get(self, id):
        """Get the record with a given id.

        Raises KeyError if the record isn't found.

        """
        filenum = self.idmap[id]
        tree = self._get_tree(filenum)
        return tree.get(id)

    def get_meta(self, name):
        """Get a metadata value.

        Raises KeyError if the value isn't found.

        """
        assert isinstance(name, unicode)
        return self.meta[name]

    def set_meta(self, name, value):
        """Set a metadata value.

        """
        assert isinstance(name, unicode)
        assert isinstance(value, unicode)
        self.meta[name] = value
        self.idmap_modified = True

    def del_meta(self, name):
        """Delete a metadata value.

        """
        assert isinstance(name, unicode)
        del self.meta[name]
        self.idmap_modified = True
