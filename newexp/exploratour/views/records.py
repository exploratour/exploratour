from ..storage.record import FileField


FIELD_VIEWS = {}

def FieldView(field):
    return FIELD_VIEWS[field.type](field)


def register_field_view(cls):
    FIELD_VIEWS[cls.type] = cls
    return cls


@register_field_view
class TitleFieldView:
    type = 'title'
    def __init__(self, field):
        self.title = field.title

@register_field_view
class DateFieldView:
    type = 'date'
    def __init__(self, field):
        self.name = field.name
        self.date_string = field.date_string

@register_field_view
class FileFieldView:
    type = 'file'
    DisplayTypes = FileField.DisplayTypes
    def __init__(self, field):
        self.name = field.name
        self.display = field.display
        self.src = field.src
        self.title = field.title
        self.alt = field.alt


class ClosingFieldView:
    def __init__(self, field):
        self.field = field
        self.closing = True
        self.id = field.id
        self.name = field.name
        self.type = field.type
        self.position = field.position


class RecordView:
    def __init__(self, record):
        self._record = record

    @property
    def title(self):
        return self._record.title

    @property
    def flat_fields(self):
        def flatten(fields):
            for field in fields:
                yield FieldView(field)
                if hasattr(field, 'fields'):
                    for f in flatten(field.fields.fields):
                        yield f
                    yield ClosingFieldView(field)
        for f in flatten(self._record.fields.fields):
            yield f

    @property
    def collection_nav(self):
        colls = []
        for coll in self._record.collections:
            pos = coll.record_position(self._record)
            prev_record = coll.record_at_position(pos - 1)
            if prev_record:
                prev = dict(
                    title=prev_record.title,
                    id=prev_record.id,
                )
            else:
                prev = None
            next_record = coll.record_at_position(pos + 1)
            if next_record:
                next = dict(
                    title=next_record.title,
                    id=next_record.id,
                )
            else:
                next = None

            colls.append(dict(
                id= coll.id,
                title= coll.title,
                pos= pos,
                record_count= coll.record_count,
                prev= prev,
                next= next,
            ))
        return colls
