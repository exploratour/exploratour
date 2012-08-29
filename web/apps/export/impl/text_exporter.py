from apps.export.impl.base import FieldSpecificExporter
import os

class TextExporter(FieldSpecificExporter):
    fmt = 'txt'
    description = "Plain unformatted text format"
    priority = 20

    @property
    def headers(self):
        return {
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Disposition': 'attachment; filename=export.txt',
        }

    @property
    def resultpath(self):
        return self.outpath

    def walk_fields(self, record):
        """Walk the selected fields of a record.
        
        Yields (full_name, summary).
        
        """
        group = []
        for field in record.walkfields():
            if field.tag == u'group':
                if field.closing:
                    group.pop()
                else:
                    group.append(field.name)
                continue
            full_name = ':'.join(group + [field.name])
            if full_name + '_' + field.type not in self.fields:
                continue
            summary = None
            if hasattr(field, 'summary'):
                summary = field.summary
            if summary is not None:
                summary = summary.strip()

            if summary:
                yield full_name, field.type, summary

    def fmt_record_order(self, fd, record):
        """Format a record in record order, and write to fd."""
        subresult = []
        for full_name, field_type, summary in self.walk_fields(record):
            row = full_name.title() + u': ' + summary
            if '\n' in summary:
                row = row + "\n"
            subresult.append(row)
        if len(subresult) > 0:
            fd.write(u'\n'.join(subresult).encode('utf8'))

    def fmt_custom_order(self, fd, record):
        """Format a record in custom order, and write to fd."""
        subresult = {}
        for full_name, field_type, summary in self.walk_fields(record):
            row = full_name.title() + u': ' + summary
            if '\n' in summary:
                row = row + "\n"
            subresult.setdefault(full_name + '_' + field_type, []).append(row)
        if len(subresult) > 0:
            output = []
            for field in self.fields:
                output.extend(subresult.get(field, []))
            fd.write(u'\n'.join(output).encode('utf8'))

    def export(self, tempdir):
        self.outpath = os.path.join(tempdir, 'export.txt')
        fd = open(self.outpath, "wb")
        if self.custom_order:
            formatter = self.fmt_custom_order
        else:
            formatter = self.fmt_record_order
        try:
            count = 0
            size = len(self.objs)
            while len(self.objs) > 0:
                count += 1
                yield "Formatting record %d of %d" % (count, size)
                if count != 1:
                    fd.write(u'\n\n' + u'=' * 70 + '\n\n')
                r = self.objs.pop(0)
                formatter(fd, r)
        finally:
            fd.close()
