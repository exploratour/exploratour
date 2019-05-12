from storage import storage, Collection, Record
from datetime import datetime
import sys
import json


def run():
    storage.create_tables()
    collection_file = sys.argv[1]
    record_file = sys.argv[2]

    session = storage.start_session()

    with open(collection_file, "rb") as fd:
        for line in fd:
            line = line.strip()
            if not line:
                continue
            add_collection_from_data(json.loads(line), session)

    with open(collection_file, "rb") as fd:
        for line in fd:
            line = line.strip()
            if not line:
                continue
            add_collection_parents_from_data(json.loads(line), session)

    session.flush()
    session.commit()

    with open(collection_file, "rb") as fd:
        for line in fd:
            line = line.strip()
            if not line:
                continue
            check_collection_parents(json.loads(line), session)

    with open(record_file, "rb") as fd:
        for line in fd:
            line = line.strip()
            if not line:
                continue
            add_record_from_data(json.loads(line), session)

    session.flush()


def add_record_from_data(data, session):
    assert len(data.keys()) == 1
    data = data["record"]
    record_id = data.pop("id")
    title = data.pop("title")
    mtime = datetime.fromtimestamp(data.pop("mtime"))
    collection_ids = data.pop("collection_ids")
    fields = data.pop("fields")

    assert len(data) == 0, (record_id, data)
    collections = [
        session.query(Collection).filter_by(id=coll_id).one()
        for coll_id in collection_ids
    ]

    r = Record(
        id=record_id,
        title=title,
        mtime=mtime,
        fields=str(fields),
        collections=collections,
    )
    session.add(r)


def add_collection_from_data(data, session):
    assert len(data.keys()) == 1
    data = data["collection"]
    coll_id = data.pop("id")
    title = data.pop("title")
    mtime = datetime.fromtimestamp(data.pop("mtime"))
    parents = data.pop("parents")
    children = data.pop("children")
    autoorder = data.pop("autoorder", None)
    assert len(data) == 0, data
    c = Collection(
        id=coll_id, title=title, mtime=mtime, autoorder=autoorder and str(autoorder)
    )
    session.add(c)


def add_collection_parents_from_data(data, session):
    data = data["collection"]
    coll_id = data.pop("id")
    parents = data.pop("parents")
    children = data.pop("children")
    coll = session.query(Collection).filter_by(id=coll_id).one()
    parents = [
        session.query(Collection).filter_by(id=parent_id).one() for parent_id in parents
    ]
    coll.parents = parents


def check_collection_parents(data, session):
    data = data["collection"]
    coll_id = data.pop("id")
    parents = data.pop("parents")
    children = data.pop("children")
    coll = session.query(Collection).filter_by(id=coll_id).one()
    assert sorted(parents) == sorted([parent.id for parent in coll.parents])
    assert sorted(children) == sorted([parent.id for parent in coll.children])


if __name__ == "__main__":
    run()
