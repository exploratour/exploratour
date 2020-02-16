from .base import Base, Column, String, Integer, Enum, DateTime, relationship, ForeignKey
from .record_collections import record_collections_table
import enum


class Field(Base):
    __tablename__ = "fields"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    type = Column(String)
    list_id = Column(Integer, ForeignKey('list_fields.id'))
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

class ListField(Base):
    __tablename__ = "list_fields"
    id = Column(Integer, ForeignKey("fields.id"), primary_key=True, autoincrement=True)
    fields = relationship(Field, cascade="all, delete-orphan", order_by="Field.position", foreign_keys=[Field.list_id])

    __mapper_args__ = {
        "polymorphic_identity": "list",
    }

class Record(Base):
    __tablename__ = "records"

    id = Column(String, primary_key=True)
    title = Column(String)
    mtime = Column(DateTime)
    fields = Column(Integer, ForeignKey("list_fields.id"))
    raw_fields = Column(String)
    collections = relationship(
        "Collection", secondary=record_collections_table, lazy="joined"
    )

    def __repr__(self):
        return "<Record(id={}, title={}, mtime={} fields={})>".format(
            repr(self.id), repr(self.title), repr(self.mtime),
            repr(self.fields),
        )
