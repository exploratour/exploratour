#!/usr/bin/env python

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
sys.path.insert(0, config.topdir)
sys.path.insert(0, config.configdir)
import ext

import shutil
import tempfile
import unittest

class TestRecordStore(unittest.TestCase):
    def test_record_store(self):
        """Test the Record store.

        """
        config.datadir = os.path.join(self.tempdir, 'data')
        config.logdir = os.path.join(config.datadir, 'logs')
        config.storedir = os.path.join(config.datadir, 'store')

        from apps.store.models import Record, Collection
        import apps.store.store

        self.assertEqual(list(Record.objects), [])
        Record.objects.set(Record())
        self.assertEqual(list(r.xml for r in Record.objects),
            [u'<record xmlns="http://exploratour.org/schema/1" id="1"/>'])

        apps.store.store.flush()

    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="exploratourtest")

    def tearDown(self):
        shutil.rmtree(self.tempdir)

if __name__ == '__main__':
    unittest.main()
