#!/usr/bin/env python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
import render
import unittest

class RenderTest(unittest.TestCase):
    def test_basic(self):
        """Test a basic render operation.

        """
        html = render.render('home.html')
        self.assertTrue('<title>Home - Exploratour</title>' in html)

if __name__ == '__main__':
    unittest.main()
