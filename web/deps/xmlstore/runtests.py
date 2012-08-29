#!/usr/bin/env python

from lxml import etree
import os
import random
import shutil
import tempfile
import time
import unittest
import xmlstore

class TestXmlStore(unittest.TestCase):
    def test_num_to_path(self):
        topdir = os.path.join('invalid', 'path')
        store = xmlstore.XmlStore(topdir)
        self.assertEqual(store._num_to_path(0),
                         os.path.join(topdir, "F0"))
        self.assertEqual(store._num_to_path(1),
                         os.path.join(topdir, "F1"))
        self.assertEqual(store._num_to_path(9),
                         os.path.join(topdir, "F9"))
        self.assertEqual(store._num_to_path(10),
                         os.path.join(topdir, "D1", "F0"))
        self.assertEqual(store._num_to_path(11),
                         os.path.join(topdir, "D1", "F1"))
        self.assertEqual(store._num_to_path(19),
                         os.path.join(topdir, "D1", "F9"))
        self.assertEqual(store._num_to_path(20),
                         os.path.join(topdir, "D2", "F0"))
        self.assertEqual(store._num_to_path(99),
                         os.path.join(topdir, "D9", "F9"))
        self.assertEqual(store._num_to_path(100),
                         os.path.join(topdir, "D1", "D0", "F0"))
        self.assertEqual(store._num_to_path(101),
                         os.path.join(topdir, "D1", "D0", "F1"))
        self.assertEqual(store._num_to_path(999),
                         os.path.join(topdir, "D9", "D9", "F9"))
        self.assertEqual(store._num_to_path(1000),
                         os.path.join(topdir, "D1", "D0", "D0", "F0"))

    def test_cachedtree(self):
        """Test the XmlStore.CachedTree class.

        """
        elt_tree = etree.ElementTree(etree.Element("container"))
        tree = xmlstore.XmlStore.CachedTree(elt_tree)
        self.assertEqual(len(tree), 0)
        outname = os.path.join(self.tempdir, "tmp1")
        self.assertFalse(os.path.exists(outname + ".xml"))
        tree.write(outname)
        self.assertTrue(os.path.exists(outname + ".xml"))
        contents = open(outname + ".xml").read().decode('utf-8')
        self.assertEqual(contents, u"<?xml version='1.0' encoding='UTF-8'?>\n"
                         u"<container/>")

        # Add a record.  Check that adding it multiple times has no further
        # effect.
        record = etree.XML(u"<record id=\"id\xa31\"/>")
        self.assertRaises(KeyError, tree.get, u"id\xa31")
        tree.set(record)
        self.assertEqual(etree.tounicode(tree.get(u"id\xa31")),
                         u"<record id=\"id&#xA3;1\"/>")
        tree.set(record)
        self.assertEqual(etree.tounicode(tree.get(u"id\xa31")),
                         u"<record id=\"id&#xA3;1\"/>")
        self.assertEqual(len(tree), 1)
        tree.write(outname)
        self.assertEqual(len(tree), 1)
        contents = open(outname + ".xml").read().decode('utf-8')
        self.assertEqual(contents, u"<?xml version='1.0' encoding='UTF-8'?>\n"
                         u"<container><record id=\"id\xa31\"/></container>")

        # Check that adding a record with no id fails correctly.
        record2 = etree.XML(u"<record/>")
        self.assertRaises(AssertionError, tree.set, record2)
        self.assertEqual(len(tree), 1)

        # Add a second record.
        record2.set(u'id', u'2')
        elt = etree.SubElement(record2, u"field")
        elt.set(u'name', u'title')
        elt.text = u"An interesting element"
        tree.set(record2)
        self.assertEqual(len(tree), 2)
        tree.write(outname)
        self.assertEqual(len(tree), 2)
        contents = open(outname + ".xml").read().decode('utf-8')
        self.assertEqual(contents, u"<?xml version='1.0' encoding='UTF-8'?>\n"
                         u"<container><record id=\"id\xa31\"/>"
                         u"<record id=\"2\"><field name=\"title\">"
                         u"An interesting element</field></record>"
                         u"</container>")

        # Check record contents.
        self.assertEqual(etree.tounicode(tree.get(u"id\xa31")),
                         u"<record id=\"id&#xA3;1\"/>")
        self.assertEqual(etree.tounicode(tree.get(u"2")),
                         u"<record id=\"2\"><field name=\"title\">"
                         u"An interesting element</field></record>")

        # Remove a record.
        self.assertRaises(KeyError, tree.remove, u"3")
        self.assertEqual(len(tree), 2)
        tree.remove(u"2")
        self.assertEqual(len(tree), 1)
        self.assertEqual(etree.tounicode(tree.get(u"id\xa31")),
                         u"<record id=\"id&#xA3;1\"/>")
        self.assertRaises(KeyError, tree.remove, u"2")
        tree.write(outname)
        contents = open(outname + ".xml").read().decode('utf-8')
        self.assertEqual(contents, u"<?xml version='1.0' encoding='UTF-8'?>\n"
                         u"<container><record id=\"id\xa31\"/>"
                         u"</container>")

    def test_basic_operations(self):
        """Test very basic operations of the XML store.

        """
        store = xmlstore.XmlStore(self.tempdir)
        self.assertRaises(KeyError, store.get, u"0")
        store.set(u'<record id="0"/>')
        self.assertEqual(etree.tounicode(store.get(u"0")),
                         u'<record id="0"/>')
        self.assertRaises(KeyError, store.remove, u"1")
        store.remove(u'0')
        self.assertRaises(KeyError, store.get, u"0")
        store.flush()

        self.assertRaises(KeyError, store.get_meta, u'foo')
        store.set_meta(u'foo', u'bar')
        self.assertEqual(store.get_meta(u'foo'), u'bar')
        store.del_meta(u'foo')
        self.assertRaises(KeyError, store.get_meta, u'foo')

    def test_add_speed(self):
        store = xmlstore.XmlStore(self.tempdir)
        count = 10000
        starttime = time.time()
        for num in xrange(count):
            id = unicode(num)
            record = (u'<record id="%s"><field name="title">'
                      u'Title %d</field></record>' % (id, num))
            store.set(record)
        store.flush()
        endtime = time.time()
        print "%f adds per second" % (float(count) / (endtime - starttime))

        starttime = time.time()
        for num in xrange(count):
            id = unicode(num)
            record = (u'<record id="%s"><field name="title">'
                      u'New Title %d</field></record>' % (id, num))
            store.set(record)
        store.flush()
        endtime = time.time()
        print "%f replaces per second" % (float(count) / (endtime - starttime))

        starttime = time.time()
        c = 0
        for record in store:
            store.get(record)
            c += 1
        endtime = time.time()
        print "%f iterations per second" % (float(c) / (endtime - starttime))

    def test_multiple_op(self):
        """Test multiple operations.

        """
        store_kwargs = { "items_per_file": 10 }
        store = xmlstore.XmlStore(self.tempdir, **store_kwargs)
        items = {}
        meta = {}
        removed = []
        meta_removed = []
        count = 10000
        ops = ('add', 'add', 'add', 'readd', 'remove', 'replace',
               'get', 'get', 'get',
               'badremove1', 'badremove2',
               'badget1', 'badget2',
               'flush', 'reopen', 'checklen', 'checkall',
               'addmeta', 'getmeta', 'delmeta', 'replacemeta',
               'readdmeta', 'badgetmeta1', 'badgetmeta2',
               'baddelmeta1', 'baddelmeta2',
              )
        def mkrec(id):
            # We should really escape id and count, but we know they're safe in
            # this test.
            return (u'<record id="%s"><field name="title">'
                    u'Title %d</field></record>' % (id, count))
        def log(msg):
            pass # print msg
        while count > 0:
            count -= 1
            op = random.choice(ops)
            if op == 'add':
                # Add a random record
                id = unicode(random.randint(0, 10000000))
                record = mkrec(id)
                items[id] = record
                log("add(%r)" % id)
                store.set(record)
            elif op == 'remove':
                # Remove a random record
                if len(items) == 0:
                    continue
                id = random.choice(items.keys())
                log("remove(%r)" % id)
                store.remove(id)
                del items[id]
                removed.append(id)
            elif op == 'readd':
                # Replace a record which had been removed
                if len(removed) == 0:
                    continue
                index = random.randint(0, len(removed) - 1)
                id = removed[index]
                del removed[index]
                if id in items:
                    # It's been added again
                    continue
                log("readd(%r)" % id)
                record = mkrec(id)
                items[id] = record
                store.set(record)
            elif op == 'badremove1':
                # Remove an id which has already been removed
                if len(removed) == 0:
                    continue
                id = random.choice(removed)
                if id in items:
                    # It's been added again
                    continue
                log("badremove1(%r)" % id)
                self.assertRaises(KeyError, store.remove, id)
            elif op == 'badremove2':
                # Remove an id which has never been used
                id = unicode(random.randint(0, 10000000)) + 'X'
                log("badremove2(%r)" % id)
                self.assertRaises(KeyError, store.remove, id)
            elif op == 'replace':
                # Replace a random record
                if len(items) == 0:
                    continue
                id = random.choice(items.keys())
                log("replace(%r)" % id)
                record = mkrec(id)
                items[id] = record
                store.set(record)
            elif op == 'get':
                # Get a record which exists
                if len(items) == 0:
                    continue
                id = random.choice(items.keys())
                log("get(%r)" % id)
                record = store.get(id)
                self.assertEqual(items[id], etree.tounicode(record))
            elif op == 'badget1':
                # Get a record which has already been removed
                if len(removed) == 0:
                    continue
                id = random.choice(removed)
                if id in items:
                    # It's been added again
                    continue
                log("badget1(%r)" % id)
                self.assertRaises(KeyError, store.get, id)
            elif op == 'badget2':
                # Get a record which has never existed
                # Remove an id which has never been used
                id = unicode(random.randint(0, 10000000)) + 'X'
                log("badget2(%r)" % id)
                self.assertRaises(KeyError, store.get, id)
            elif op == 'flush':
                # Flush changes
                log("flush()")
                store.flush()
            elif op == 'reopen':
                # Reopen the store, checking that changes persisted.
                log("reopen()")
                store.close()
                store = xmlstore.XmlStore(self.tempdir, **store_kwargs)
            elif op == 'checklen':
                # Check the length of the store
                log("checklen()")
                self.assertEqual(len(store), len(items))
            elif op == 'checkall':
                # Check the contents of the store
                log("checkall()")
                newitems = dict((id, etree.tounicode(store.get(id))) for id in store)
                self.assertEqual(newitems, items)
                self.assertEqual(len(newitems), len(store))
            elif op == 'addmeta':
                # Add a metadata value.
                log("addmeta")
                store.set_meta(u'%d' % count, u'v%d' % count)
                meta[u'%d' % count] = u'v%d' % count
            elif op == 'getmeta':
                # Get a metadata value
                log("getmeta")
                if len(meta) == 0:
                    continue
                name = random.choice(meta.keys())
                self.assertEqual(store.get_meta(name), meta[name])
            elif op == 'delmeta':
                # Delete a metadata value
                log("delmeta")
                if len(meta) == 0:
                    continue
                name = random.choice(meta.keys())
                store.del_meta(name)
                del meta[name]
                meta_removed.append(name)
            elif op == 'replacemeta':
                # Replace an existing metadata value
                log("replacemeta")
                if len(meta) == 0:
                    continue
                name = random.choice(meta.keys())
                store.set_meta(name, u'v%d' % count)
                meta[name] = u'v%d' % count
            elif op == 'readdmeta':
                # Re-add a metadata value which was removed
                if len(meta_removed) == 0:
                    continue
                index = random.randint(0, len(meta_removed) - 1)
                name = meta_removed[index]
                log("readdmeta(%r)" % name)
                del meta_removed[index]
                if name in meta:
                    # It's been added again
                    continue
                meta[name] = u'v%d' % count
                store.set_meta(name, u'v%d' % count)
            elif op == 'badgetmeta1':
                # Get a metadata value which has already been removed
                if len(meta_removed) == 0:
                    continue
                name = random.choice(meta_removed)
                if name in meta:
                    # It's been added again
                    continue
                log("badgetmeta1(%r)" % name)
                self.assertRaises(KeyError, store.get_meta, name)
            elif op == 'badgetmeta2':
                # Get a metadata value which has never been used
                name = unicode(random.randint(0, 10000000)) + 'X'
                log("badgetmeta2(%r)" % name)
                self.assertRaises(KeyError, store.get_meta, name)
            elif op == 'baddelmeta1':
                # Remove a metadata value which has already been removed
                # Get a metadata value which has already been removed
                if len(meta_removed) == 0:
                    continue
                name = random.choice(meta_removed)
                if name in meta:
                    # It's been added again
                    continue
                log("baddelmeta1(%r)" % name)
                self.assertRaises(KeyError, store.del_meta, name)
            elif op == 'baddelmeta2':
                name = unicode(random.randint(0, 10000000)) + 'X'
                log("baddelmeta2(%r)" % name)
                self.assertRaises(KeyError, store.del_meta, name)
            else:
                # Should never happen.
                self.assertNotEqual(op, op)

        # Check the length of the store
        log("final check")
        newitems = dict((id, etree.tounicode(store.get(id))) for id in store)
        self.assertEqual(newitems, items)
        self.assertEqual(len(newitems), len(store))

    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="xmlstoretest")

    def tearDown(self):
        shutil.rmtree(self.tempdir)

if __name__ == '__main__':
    unittest.main()
