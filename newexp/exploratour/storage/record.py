from .base import Base, Column, String, DateTime, relationship

from .record_collections import record_collections_table


class Record(Base):
    __tablename__ = "records"

    id = Column(String, primary_key=True)
    title = Column(String)
    mtime = Column(DateTime)
    fields = Column(String)
    collections = relationship(
        "Collection",
        secondary=record_collections_table,
        lazy="joined",
    )

    def __repr__(self):
        return "<Record(id={}, title={}, mtime={})>".format(
            repr(self.id), repr(self.title), repr(self.mtime)
        )
