from .base import (
    Base,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    relationship,
)


collection_parents_table = Table(
    "collection_parents",
    Base.metadata,
    Column("parent_id", Integer, ForeignKey("collections.id"), primary_key=True),
    Column("child_id", Integer, ForeignKey("collections.id"), primary_key=True),
)


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
        backref="children",
        lazy="joined",
        join_depth=10,
    )

    def __repr__(self):
        return "<Collection(id={}, title={}, mtime={}, parents={})".format(
            repr(self.id), repr(self.title), repr(self.mtime), repr(self.parents)
        )
