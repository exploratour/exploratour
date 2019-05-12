from .base import (
    Base,
    Column,
    Integer,
    String,
    DateTime,
    Table,
    ForeignKey,
    relationship,
)


record_collections_table = Table(
    "record_collections",
    Base.metadata,
    Column("record_id", Integer, ForeignKey("records.id")),
    Column("collection_id", Integer, ForeignKey("collections.id")),
)


class Record(Base):
    __tablename__ = "records"

    id = Column(String, primary_key=True)
    title = Column(String)
    mtime = Column(DateTime)
    fields = Column(String)
    collections = relationship(
        "Collection", secondary=record_collections_table, backref="records"
    )

    def __repr__(self):
        return "<Record(id={}, title={}, mtime={})".format(
            repr(self.id), repr(self.title), repr(self.mtime)
        )
