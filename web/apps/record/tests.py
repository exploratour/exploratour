#!/usr/bin/env python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
import unittest

import sanitize_html
import lxml.etree

class SanitizeTest(unittest.TestCase):
    def test_clean(self):
        """Test cleaning some HTML.

        """
        inputs = [
            ("", ""),
            ("a", "<p>a</p>"),
            ("<p>a</p>", "<p>a</p>"),
            ("""<<script>script>Broken and dubious html</script</script>>""",
             """<p>script&gt;Broken and dubious html&gt;</p>"""),
            ("""<<script></script>script> alert("Haha, I hacked your page.");<<script></script>script>""",
             """<p>script&gt; alert("Haha, I hacked your page.");script&gt;</p>"""),
            ("""<strike>Struck</strike>""",
             """<strike>Struck</strike>"""),
            ("""<span><span style="text-decoration: underline;">Underlined</span>_</span>""",
             """<span><u>Underlined</u>_</span>"""),
            ("""<span style="text-decoration: underline;">Underlined</span>""",
             """<u>Underlined</u>"""),
            ("""<span style="text-decoration: underline;">Underlined</span>_""",
             """<span><u>Underlined</u>_</span>"""),
            ("""<span style="text-decoration: line-through;text-decoration: underline;">Underlined</span>_""",
             """<span><strike><u>Underlined</u></strike>_</span>"""),
            ("""<span style="border: 1px solid black;">Bordered</span>""",
             """<span>Bordered</span>"""),
            ("""<p><span style="border: 1px solid black;">Bordered</span> Not</p>""",
             """<p>Bordered Not</p>"""),
            ("""<p>A<b>B</b><i>C</i><u>d</u>_<span style="text-decoration: underline;">D</span>_<span style="text-decoration: line-through;">E</span>_<span style="color: #993300;">F<span style="background-color: #333300;">G<span style="background-color: #ffffff; color: #000000;">H</span></span></span></p>""",
             """<p>A<b>B</b><i>C</i><u>d</u>_<u>D</u>_<strike>E</strike>_<span style="color:#993300">F<span style="background-color:#333300">G<span style="background-color:#ffffff;color:#000000">H</span></span></span></p>"""),
        ]

        for input, output in inputs:
            doc = sanitize_html.clean(input)
            self.assertEqual(doc, output)

if __name__ == '__main__':
    unittest.main()
