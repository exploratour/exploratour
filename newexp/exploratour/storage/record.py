from .base import Base, Column, String, Integer, Enum, DateTime, relationship, ForeignKey
from .record_collections import record_collections_table
import enum


class Field(Base):
    __tablename__ = "fields"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    type = Column(String)
    list_id = Column(Integer, ForeignKey('list_of_fields.id'))
    position = Column(Integer)

    __mapper_args__ = {
        "polymorphic_identity": "field",
        "polymorphic_on": type
    }

class TitleField(Field):
    __tablename__ = "title_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    title = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "title",
    }

class TextField(Field):
    __tablename__ = "text_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    text = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "text",
    }

class DateField(Field):
    __tablename__ = "date_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    date_string = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "date",
    }

class LocationField(Field):
    __tablename__ = "location_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    latlong = Column(String)
    text = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "location",
    }

class FileField(Field):
    __tablename__ = "file_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    class DisplayTypes(enum.Enum):
        full = 1
        inline = 2
        thumb = 3
        icon = 4
        text = 6
        icontext = 5

    display = Column(Enum(DisplayTypes))
    mimetype = Column(String)
    src = Column(String)

    alt = Column(String)
    text = Column(String)
    title = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "file",
    }

class LinkField(Field):
    __tablename__ = "link_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    class LinkTypes(enum.Enum):
        record = 1
        collection = 2
        search = 3
        url = 4

    linktype = Column(Enum(LinkTypes))
    target = Column(String)
    text = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "link",
    }

class ListOfFields(Base):
    __tablename__ = "list_of_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)

class GroupField(Field):
    __tablename__ = "group_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    list_of_fields_id = Column(Integer, ForeignKey("list_of_fields.id"))
    relationship(ListOfFields, cascade="all, delete-orphan")

    __mapper_args__ = {
        "polymorphic_identity": "group",
    }

class TagField(Field):
    __tablename__ = "tag_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    text = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "tag",
    }

class NumberField(Field):
    __tablename__ = "numberfields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    text = Column(String)

    __mapper_args__ = {
        "polymorphic_identity": "number",
    }

class Record(Base):
    __tablename__ = "records"

    id = Column(String, primary_key=True)
    title = Column(String)
    mtime = Column(DateTime)
    list_field_id = Column(Integer, ForeignKey("list_of_fields.id"))
    fields = relationship(ListOfFields, cascade="all, delete-orphan", foreign_keys=[list_field_id], single_parent=True)
    raw_fields = Column(String)
    collections = relationship(
        "Collection", secondary=record_collections_table, lazy="joined"
    )

    def __repr__(self):
        return "<Record(id={}, title={}, mtime={} fields={})>".format(
            repr(self.id), repr(self.title), repr(self.mtime),
            repr(self.fields),
        )
