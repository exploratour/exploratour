from exploratour.storage import Storage, Collection, Record, Field, TitleField, TextField, DateField, LocationField, FileField, LinkField, ListField
import config

from datetime import datetime
import os
import json
import shutil
import sys


def run():
    collection_file = sys.argv[1]
    record_file = sys.argv[2]
    try:
        clear_db_first = bool(int(sys.argv[3]))
    except IndexError:
        clear_db_first = False

    if clear_db_first:
        print("Clearing DB")
        os.unlink(config.DB_PATH)

    storage = Storage()
    storage.create_tables()
    session = storage.session()

    if clear_db_first:
        print("Writing collections")
        with open(collection_file, "rb") as fd:
           for line in fd:
               line = line.strip()
               if not line:
                   continue
               add_collection_from_data(json.loads(line), session)

        print("Writing collection hierarchy")
        with open(collection_file, "rb") as fd:
           for line in fd:
               line = line.strip()
               if not line:
                   continue
               add_collection_parents_from_data(json.loads(line), session)

        session.flush()

        print("Checking collection hierarchy for consistency")
        with open(collection_file, "rb") as fd:
           for line in fd:
               line = line.strip()
               if not line:
                   continue
               check_collection_parents(json.loads(line), session)

        session.commit()
        shutil.copy2(config.DB_PATH, config.DB_PATH + "_collections")


    print("Writing records")
    with open(record_file, "rb") as fd:
        for line in fd:
            line = line.strip()
            if not line:
                continue
            add_record_from_data(json.loads(line), session)

    session.commit()


def make_field_list(fields, session):
    """Creates a ListField given a list of dicts representing fields"""
    lf = ListField()
    session.add(lf)
    session.commit()
    assert lf.id is not None
    for pos, field in enumerate(fields):
        field_type = field.pop("type")
        if field_type == "title":
            f = TitleField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                title=field.pop("text"),
            )
            session.add(f)
        elif field_type == "text":
            f = TextField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                text=field.pop("content"),
            )
            session.add(f)
        elif field_type == "date":
            f = DateField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                date_string=field.pop("text"),
            )
            session.add(f)
        elif field_type == "location":
            f = LocationField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                latlong=field.pop("latlong"),
                text=field.pop("text"),
            )
            session.add(f)
        elif field_type == "file":
            areas = field.pop("areas")
            assert len(areas) == 0, repr((areas, field))
            f = FileField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                display=field.pop("display"),
                mimetype=field.pop("mimetype"),
                src=field.pop("src"),
                alt=field.pop("alt"),
                text=field.get("text", None) or "",
                title=field.pop("title"),
            )
            field.pop("text")
            session.add(f)
        elif field_type == "link":
            f = LinkField(
                name=field.pop("name"),
                list_id=lf.id,
                position=pos,
                linktype=field.pop("linktype"),
                target=field.pop("target"),
                text=field.pop("text"),
            )
            session.add(f)

        else:
            print("Stopping", field)
            raise Exception("Unknown field type")
        assert len(field) == 0, field
    return lf


def add_record_from_data(data, session):
    """Add a record from the JSON.

    Needs to be called after all the collections exist

    Checks that all the data is used.
    """
    assert len(data.keys()) == 1
    data = data["record"]
    record_id = data.pop("id")
    title = data.pop("title")
    mtime = datetime.fromtimestamp(data.pop("mtime"))
    collection_ids = data.pop("collection_ids")
    fields = data.pop("fields")
    raw_fields = json.dumps(fields, allow_nan=False, sort_keys=True, separators=(',', ':'))

    assert len(data) == 0, (record_id, data)
    collections = [
        session.query(Collection).filter_by(id=coll_id).one()
        for coll_id in collection_ids
    ]

    lf = make_field_list(fields, session)
    print("Record ID:", record_id, " ListField.id:", lf.id)

    r = Record(
        id=record_id,
        title=title,
        mtime=mtime,
        fields=lf.id,
        raw_fields=raw_fields,
        collections=collections,
    )
    session.add(r)


def add_collection_from_data(data, session):
    """Add all the collection data, apart from parent relationships.

    Ensures all the fields in the data are used.

    """
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
    """Add the collection parent relationships to the database.

    Needs to be called after all the collections exist.

    """
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
    """Check the collection parent data in the DB matches that in JSON.

    """
    data = data["collection"]
    coll_id = data.pop("id")
    parents = data.pop("parents")
    children = data.pop("children")
    coll = session.query(Collection).filter_by(id=coll_id).one()
    assert sorted(parents) == sorted([parent.id for parent in coll.parents])
    assert sorted(children) == sorted([parent.id for parent in coll.children])


if __name__ == "__main__":
    run()
