from .base import Base, Column, Integer, Table, ForeignKey


record_collections_table = Table(
    "record_collections",
    Base.metadata,
    Column(
        "record_id", Integer, ForeignKey("records.id"), primary_key=True, index=True
    ),
    Column(
        "collection_id",
        Integer,
        ForeignKey("collections.id"),
        primary_key=True,
        index=True,
    ),
)

collection_parents_table = Table(
    "collection_parents",
    Base.metadata,
    Column("parent_id", Integer, ForeignKey("collections.id"), primary_key=True),
    Column("child_id", Integer, ForeignKey("collections.id"), primary_key=True),
)
