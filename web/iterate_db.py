#!/usr/bin/env python

from apps.store.models import Record, Collection, Template
from apps.fields.fields import field_from_data
from lxml import etree
import apps.store.store
import json
from pprint import pprint
import re

def record_to_json(record):
    parsed = record.parse()
    assert record.mtime == parsed.mtime
    # print "JSON:", parsed.coll_ids
    return json.dumps({
        "record": {
            "id": record.id,
            "mtime": record.mtime,
            "title": record.title,
            "collection_ids": parsed.coll_ids,
            "fields": map(lambda field: field.to_json(), parsed.contents),
        },
    }, indent=2)

def record_from_json(raw):
    data = json.loads(raw)
    data = data["record"]
    result = Record()
    result.collections = data["collection_ids"]
    # print "rc", result.collections, data["collection_ids"]

    result.inner_xml = u'\n'.join(
        etree.tostring(
            field_from_data(field).get_elt(indent=2),
            encoding=unicode,
        )
        for field in data["fields"]
    ).strip()
    result.id = data["id"]
    result.mtime = data["mtime"]
    # print "MTIME", result.mtime
    return result

def coll_to_json(coll):
    print coll

    return json.dumps({
        "collection": {
            "id": coll.id,
            "mtime": coll.mtime,
            "title": coll.title,
        },
    }, indent=2)

def coll_from_json(raw):
    data = json.loads(raw)
    data = data["collection"]
    result = Collection(
        id = data["id"],
        mtime = data["mtime"],
        title = data["title"],
    )
    return result

def normxml(raw):
    raw = re.sub('>\s*\\n\s*<', '><', raw)
    raw = re.sub('\s*alt=""', '', raw)
    raw = re.sub('\s*title=""', '', raw)
    # field name="ddgd" type="link" linktype="record" target="dgd"
    raw = re.sub('(<field name="[^"]*") (type="[^"]*") (linktype="[^"]*" target="[^"]*")', r'\1 \3 \2', raw)
    raw = re.sub('</field>&amp;gt;', '</field>', raw)
    return raw

def convert_records():
    count = 0
    outfile = open("records.jsonl", "wb")
    for record in Record.objects:
        record_json = record_to_json(record)

        check_record = record_from_json(record_json)
        cr_xml = check_record.xml.encode('utf8')
        # open("out1", "wb").write(cr_xml)
        cr_xml = normxml(cr_xml)

        # open("out2", "wb").write(record.xml.encode('utf8'))
        record.inner_xml = record.inner_xml
        record.collections = record.collections
        # open("out2a", "wb").write(record.xml.encode('utf8'))
        record_xml = record.xml.encode('utf8')
        record_xml = normxml(record_xml)
        if cr_xml != record_xml:
            open("out1a", "wb").write(cr_xml)
            open("out2b", "wb").write(record_xml)
        assert cr_xml == record_xml

        outfile.write(record_json + "\n")

        count += 1
        print count

        if count <=0: 
            break

    outfile.close()

def convert_collections():
    count = 0
    outfile = open("collections.jsonl", "wb")
    for coll in Collection.objects:
        coll_json = coll_to_json(coll)
        outfile.write(coll_json + "\n")

        coll_xml = etree.tounicode(coll.root).encode('utf8')
        print coll_xml

        check_coll = coll_from_json(coll_json)
        check_coll_xml = etree.tounicode(check_coll.root).encode('utf8')
        print check_coll_xml

        if check_coll_xml != coll_xml:
            open("coll_xml", "wb").write(coll_xml)
            open("check_coll_xml", "wb").write(check_coll_xml)
        assert check_coll_xml == coll_xml

        count += 1
        print count

        if count <= 0:
            break
    outfile.close()


# convert_records()
convert_collections()
