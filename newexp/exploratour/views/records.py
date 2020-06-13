from ..storage.record import FileField


FIELD_VIEWS = {}

def FieldView(field, prevfield):
    return FIELD_VIEWS[field.type](field, prevfield)


def register_field_view(*field_names):
    def wrap(cls):
        def wrapped(field, prevfield):
            view = cls(field, prevfield)
            for field_name in field_names:
                setattr(view, field_name, getattr(field, field_name))
            return view

        FIELD_VIEWS[cls.type] = wrapped
        return wrapped
    return wrap

class BaseFieldView:
    @property
    def template(self):
        return "records/fields/" + self.type + "/field_view.html"

    def __init__(self, field, prevfield):
        self.field = field
        self.prevfield = prevfield


@register_field_view("title")
class TitleFieldView(BaseFieldView):
    type = 'title'

@register_field_view("name", "date_string")
class DateFieldView(BaseFieldView):
    type = 'date'

@register_field_view("name", "display", "src", "title", "alt")
class FileFieldView(BaseFieldView):
    type = 'file'
    DisplayTypes = FileField.DisplayTypes

@register_field_view("name", "text")
class TextFieldView(BaseFieldView):
    type = 'text'

@register_field_view("name", "text")
class TagFieldView(BaseFieldView):
    type = 'tag'

@register_field_view("name", "text", "latlong")
class LocationFieldView(BaseFieldView):
    type = 'location'

@register_field_view("name", "text")
class TextFieldView(BaseFieldView):
    type = 'text'

@register_field_view("name", "text", "linktype", "target")
class LinkFieldView(BaseFieldView):
    type = 'link'
    @property
    def template(self):
        assert self.linktype.name in ('url', 'record', 'collection', 'search')
        return "records/fields/link/linktype_" + self.linktype.name + "_view.html"

@register_field_view("name")
class GroupFieldView(BaseFieldView):
    type = 'group'

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
            prevfield = None
            for field in fields:
                yield FieldView(field, prevfield)
                prevfield = field
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
