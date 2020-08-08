from ..storage.record import FileField


FIELD_VIEWS = {}


def FieldView(field, closing):
    return FIELD_VIEWS[field.type](field, closing)


def register_field_view(*field_names):
    def wrap(cls):
        def wrapped(field, closing):
            value = {}
            for field_name in field_names:
                value[field_name] = getattr(field, field_name)
            return cls(field.name, value, closing)

        FIELD_VIEWS[cls.type] = wrapped
        return wrapped

    return wrap


class BaseFieldView:
    @property
    def template(self):
        return "records/fields/" + self.type + "/field_view.html"

    def __init__(self, name, value, closing):
        self.closing = closing
        self.name = name
        self.values = [value]

    def merges_with(self, prev):
        raise NotImplementedError


class BaseSingularFieldView(BaseFieldView):
    def __init__(self, name, value, closing):
        super().__init__(name, value, closing)

    @property
    def value(self):
        return self.values[0]

    def merges_with(self, prev):
        return False


class BaseRepeatableFieldView(BaseFieldView):
    def __init__(self, name, value, closing):
        super().__init__(name, value, closing)

    def merges_with(self, prev):
        return (
            not self.closing
            and not prev.closing
            and self.type == prev.type
            and self.name == prev.name
        )


@register_field_view("title")
class TitleFieldView(BaseSingularFieldView):
    type = "title"


@register_field_view("name", "date_string")
class DateFieldView(BaseRepeatableFieldView):
    type = "date"


@register_field_view("name", "display", "src", "title", "alt")
class FileFieldView(BaseRepeatableFieldView):
    type = "file"
    DisplayTypes = FileField.DisplayTypes


@register_field_view("name", "text")
class TextFieldView(BaseSingularFieldView):
    type = "text"


@register_field_view("name", "text")
class TagFieldView(BaseRepeatableFieldView):
    type = "tag"


@register_field_view("name", "text", "latlong")
class LocationFieldView(BaseRepeatableFieldView):
    type = "location"


@register_field_view("name", "text")
class TextFieldView(BaseSingularFieldView):
    type = "text"


@register_field_view("name", "text", "linktype", "target")
class LinkFieldView(BaseSingularFieldView):
    type = "link"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values[0]["linktype"] = self.values[0]["linktype"].name


@register_field_view("name")
class GroupFieldView(BaseSingularFieldView):
    type = "group"


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
                yield FieldView(field, closing=False)
                if hasattr(field, "fields"):
                    for fv in flatten(field.fields.fields):
                        yield fv
                    yield FieldView(field, closing=True)

        for fv in flatten(self._record.fields.fields):
            yield fv

    @property
    def field_runs(self):
        accumulator = None
        for fv in self.flat_fields:
            if accumulator is None:
                accumulator = fv
                continue

            if fv.merges_with(accumulator):
                accumulator.values.extend(fv.values)
                continue

            yield accumulator
            accumulator = fv

        if accumulator is not None:
            yield accumulator

    @property
    def collection_nav(self):
        colls = []
        for coll in self._record.collections:
            pos = coll.record_position(self._record)
            prev_record = coll.record_at_position(pos - 1)
            if prev_record:
                prev = dict(title=prev_record.title, id=prev_record.id,)
            else:
                prev = None
            next_record = coll.record_at_position(pos + 1)
            if next_record:
                next = dict(title=next_record.title, id=next_record.id,)
            else:
                next = None

            colls.append(
                dict(
                    id=coll.id,
                    title=coll.title,
                    pos=pos,
                    record_count=coll.record_count,
                    prev=prev,
                    next=next,
                )
            )
        return colls
