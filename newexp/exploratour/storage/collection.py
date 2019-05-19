from .base import (
    Base,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    relationship,
    column_property,
    select,
    func,
)

from .record_collections import record_collections_table, collection_parents_table
from .record import Record


class Collection(Base):
    __tablename__ = "collections"

    id = Column(String, primary_key=True)
    title = Column(String)
    mtime = Column(DateTime)
    autoorder = Column(
        String
    )  # Just model as a string until we have modelled the field names
    parents = relationship(
        "Collection",
        secondary=collection_parents_table,
        primaryjoin=id == collection_parents_table.c.parent_id,
        secondaryjoin=id == collection_parents_table.c.child_id,
        lazy="select",
        join_depth=10,
    )
    children = relationship(
        "Collection",
        secondary=collection_parents_table,
        primaryjoin=id == collection_parents_table.c.child_id,
        secondaryjoin=id == collection_parents_table.c.parent_id,
        order_by=("Collection.title, Collection.id"),
        lazy="joined",
        join_depth=10,
    )
    from sqlalchemy import text

    record_count = column_property(
        select(
            [func.count(record_collections_table.c.record_id)],
            record_collections_table.c.collection_id == id,
        ),
        deferred=True,
    )
    records = relationship("Record", secondary=record_collections_table, lazy="dynamic")

    def _collection_order_query(self):
        row_query = self.records.with_entities(
            Record.id, func.row_number().over(order_by="id").label("row")
        )
        # print(row_query)
        # print(list(row_query))
        return row_query.subquery()

    def record_position(self, record):
        row_query = self._collection_order_query()
        r = Record.query.with_entities(row_query).filter(row_query.c.id == record.id).one()
        return r.row

    def next_record(self, row):
        row_query = self._collection_order_query()
        r = Record.query.with_entities(row_query).filter(row_query.c.row == row + 1).one()
        return r

    def __repr__(self):
        return "<Collection(id={}, title={}, mtime={}, parents={})>".format(
            repr(self.id), repr(self.title), repr(self.mtime), repr(self.parents)
        )
