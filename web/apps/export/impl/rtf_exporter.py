from apps.export.impl.base import FieldSpecificExporter
from apps.mediainfo.views import mapper
import config
import os

from rtfng.Elements import Document, LINE
from rtfng.PropertySets import TextPropertySet
from rtfng.document.character import B, TEXT, Text
from rtfng.document.section import Section
from rtfng.document.paragraph import Paragraph
from rtfng.object.picture import Image as rtfng_Image
from lxml import etree

try:
    from PIL import Image as pil_Image
except ImportError:
    import Image as pil_Image

import StringIO

class RtfExporter(FieldSpecificExporter):
    fmt = 'rtf'
    description = "Rich Text Format (RTF) for loading into word processors"
    priority = 100

    @property
    def headers(self):
        return {
            'Content-Type': 'application/rtf',
            'Content-Disposition': 'attachment; filename=export.rtf',
        }

    @property
    def resultpath(self):
        return self.outpath

    def encode_unicode(self, text):
        return ''.join(['\u%s?' % str(ord(ch)) for ch in text])


    def get_image(self, src, width=600, height=450):
        localpath = mapper._map_path(src)
        if localpath is None:
            return None

        img = pil_Image.open(localpath)
        img.thumbnail((width, height), pil_Image.ANTIALIAS)

        out = StringIO.StringIO()
        ext = src.split('.')[-1].lower()
        if ext in ('jpg', 'jpeg'):
            img.save(out, "JPEG")
            fakename = 'img.jpg'
        else:
            img.save(out, "PNG")
            fakename = 'img.png'

        out = StringIO.StringIO(out.getvalue())

        return rtfng_Image(fakename, fin=out, scale_x=50, scale_y=50)


    def append_file(self, para, mimetype, src, summary):
        """Append a file.
        
        Embeds an image if possible, otherwise, embeds the summary, otherwise
        embeds the filename.

        """
        img = None
        if mimetype in (u'image/jpeg', u'image/png'):
            img = self.get_image(src)
            para.append(img)
            return
        summary = (summary or u'').strip()
        if summary:
            para.append(TEXT(summary, font="Courier"))
        else:
            para.append(src)


    def append_text_field(self, field):
        block_elts = set('h1,h2,h3,h4,h5,h6,div,p,br'.split(','))
        para = None
        formatting_stack = [TextPropertySet()]
        for action, elt in etree.iterwalk(field.get_elt(),
                                          events=("start", "end")):
            closing = (action == 'end')
            is_block = (elt.tag in block_elts)

            if closing:
                if elt.tag in ('b', 'i', 'u'):
                    formatting_stack.pop()
            else:
                if elt.tag in ('b', 'i', 'u'):
                    new_format = formatting_stack[-1].Copy()
                    if elt.tag == 'b':
                        new_format.bold = True
                    elif elt.tag == 'i':
                        new_format.italic = True
                    elif elt.tag == 'u':
                        new_format.underline = True
                    formatting_stack.append(new_format)

            if para is not None and is_block:
                # If starting or ending a block tag, and have some text
                # buffered, emit it.
                yield para
                para = None
            textprops = formatting_stack[-1]

            # Add any trailing text for closing tags.
            if closing:
                if elt.tail:
                    if para is None:
                        para = Paragraph(self.ss.ParagraphStyles.Normal)
                    para.append(Text(self.encode_unicode(elt.tail), textprops))
                continue

            # Handle special element types.

            if elt.tag == 'br':
                assert para is None
                para = Paragraph(self.ss.ParagraphStyles.Normal)
                #para.append(LINE)
                continue

            data_type = elt.attrib.get('data-type', None)
            display = elt.attrib.get('data-display', None)

            if data_type == 'file':
                src = elt.attrib.get('data-src', None)
                mimetype = elt.attrib.get('data-mimetype', None)
                alt = elt.attrib.get('data-alt', None)
                title = elt.attrib.get('data-title', None)

                if para is None:
                    para = Paragraph(self.ss.ParagraphStyles.Normal)
                self.append_file(para, mimetype, src, title or alt)
                continue

            elif data_type == 'link':
                linktype = elt.attrib.get('data-linktype', '')
                if linktype == 'file':
                    src = elt.attrib.get('data-target', None)
                    mimetype = elt.attrib.get('data-mimetype', None)
                    if mimetype.startswith('image/'):
                        alt = elt.attrib.get('data-alt', None)
                        title = elt.attrib.get('data-title', None)
                        if para is None:
                            para = Paragraph(self.ss.ParagraphStyles.Normal)
                        self.append_file(para, mimetype, src, title or alt)
                        continue

            if elt.text:
                if para is None:
                    para = Paragraph(self.ss.ParagraphStyles.Normal)
                para.append(Text(self.encode_unicode(elt.text), textprops))

        if para is not None:
            yield para


    def emit_paragraphs(self, r, fielditer):
        p = None
        last_fname = None
        last_type = None

        for full_name, field in fielditer:

            # Text fields are handled specially
            if field.type == u'text':
                if p is not None:
                    yield p
                    p = None
                for p in self.append_text_field(field):
                    yield p
                p = None
                continue

            # Finish the current paragraph if we have a new field.
            if p is not None and (full_name != last_fname or
                                  field.type != last_type):
                last_fname = full_name
                last_type = field.type
                if p is not None:
                    yield p
                    p = None

            # If it's a title, with the same title as the document, skip it.
            if field.type == u'title':
                if field.summary == r.title:
                    continue

            # Start a paragraph if needed
            if p is None:
                p = Paragraph(self.ss.ParagraphStyles.Normal)
                p.append(B(full_name.title()))
                p.append(u': ')
                new_para = True
            else:
                new_para = False

            # If it's a file, append it to the paragraph.
            if field.type == u'file':
                self.append_file(p, field.mimetype, field.src,
                                  field.summary)
                continue

            # If it's a title, append to the paragraph, and finish the
            # paragraph.
            if field.type == u'title':
                summary = (field.summary or u'').strip()
                if summary:
                    p.append(summary)
                    yield p
                    p = None
                continue

            # Simple field types: just add the text, don't finish the paragraph
            if field.type in (u'date', u'location', u'number',
                              u'tag', u'link'):
                summary = (field.summary or u'').strip()
                if summary:
                    if not new_para:
                        summary = u', ' + summary
                    p.append(summary)
                continue

            p.append('Unknown field type: %s' % field.type)

        if p is not None:
            yield p

    def custom_emit_fields(self, r):
        fields = {}
        for field_key, full_name, field in self.emit_fields(r):
            if field_key not in self.fields:
                continue
            fields.setdefault(field_key, []).append((full_name, field))
        for field in self.fields:
            for full_name, field in fields.get(field, []):
                yield full_name, field

    def record_emit_fields(self, r):
        for field_key, full_name, field in self.emit_fields(r):
            if field_key not in self.fields:
                continue
            yield full_name, field

    def emit_fields(self, r):
        group = []
        for field in r.walkfields():
            if field.tag == u'group':
                if field.closing:
                    group.pop()
                else:
                    group.append(field.name)
                continue
            if field.closing:
                continue
            full_name = ':'.join(group + [field.name])
            field_key = full_name + '_' + field.type
            yield field_key, full_name, field

    def export(self, tempdir):
        self.outpath = os.path.join(tempdir, 'export.rtf')
        self.imgnum = 1

        doc = Document()
        self.ss = doc.StyleSheet

        export_title = u'Export (%d records)' % len(self.objs)

        on_empty_page = True

        if self.custom_order:
            emitter = self.custom_emit_fields
        else:
            emitter = self.record_emit_fields

        count = 0
        size = len(self.objs)
        while len(self.objs) > 0:
            count += 1
            yield "Formatting record %d of %d" % (count, size)
            r = self.objs.pop(0)

            if on_empty_page:
                section = Section()
            else:
                section = Section(break_type=Section.PAGE)
            on_empty_page = False

            p = Paragraph(self.ss.ParagraphStyles.Heading1)
            p.append(r.title)
            section.append(p)

            for p in self.emit_paragraphs(r, emitter(r)):
                section.append(p)

            if len(section) > 0:
                doc.Sections.append(section)

        fd = open(self.outpath, "wb")
        doc.write(fd)
        fd.close()
