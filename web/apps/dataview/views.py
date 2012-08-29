# -*- coding: UTF8 -*-

from apps.search.views import build_search
from apps.store.models import Record
from apps.shortcuts import getparam
from apps.templates.render import render
import lxml.etree as etree

import re
import datetime

single_full_bamboostyle_date_re = re.compile('([\d]{1,2})[\./]([\d]{1,2})[\./]([\d]{4})')

loc_dms_re = re.compile(r'(?P<deg>[\d]{1,2})[o°]((?P<min>[\d]{1,2})[^\d]((?P<sec>[\d]{1,2}(\.\d*)?)[^\d])?)?(?P<dir>[NSEW])')

class LatLong(object):
    def __init__(self, lat, long):
        self.lat = lat
        self.long = long

def locparse(loc, dir):
    try:
        return float(loc), dir
    except ValueError: pass
    mo = loc_dms_re.match(loc)
    if not mo:
        return None
    groups = mo.groupdict()
    deg = groups.get('deg', None)
    min = groups.get('min', None)
    sec = groups.get('sec', None)
    deg, min, sec = map(lambda x: x or 0, [deg, min, sec])
    deg, min, sec = map(lambda x: float(x) or 0, [deg, min, sec])
    return deg + min / 60.0 + sec / 3600.0, groups.get('dir', None)

def latlongparse(latlong):
    if latlong is None:
        return None

    ll = map(lambda x: x.strip(), latlong.split(','))
    if len(ll) == 1:
        ll = map(lambda x: x.strip(), latlong.split(' '))
    if len(ll) != 2:
        return None

    lat, long = None, None
    a = locparse(ll[0], 'N')
    if a is None: return None
    b = locparse(ll[1], 'E')
    if b is None: return None
    for pos, dir in (a, b):
        if dir == 'N': lat = pos
        elif dir == 'S': lat = -pos
        elif dir == 'E': long = pos
        elif dir == 'W': long = -pos
    
    if lat is None or long is None:
        return None

    return LatLong(lat, long)

class DataViewController(object):
    def view(self, id, **params):
        context = {}

        stash = {}
        showfull = int(getparam('showfull', '0', stash))
        search = build_search(stash)

        # FIXME - hack
        q = search['q']
        q.startrank = 0
        q.endrank = 20000
        items = q.results

        ids = set()
        for item in items:
            if item.data['type'][0] != 'r': continue
            ids.add(item.data['id'][0])
        points = []
        for id in sorted(ids):
            rec = Record.objects.get(unicode(id))
            date = rec.root.find("field[@type='date']")
            if date is None:
                continue
            date = date.text
            if date is None:
                continue
            mo = single_full_bamboostyle_date_re.match(date) 
            if not mo:
                continue
            day, month, year = map(lambda x: int(x), (mo.group(1), mo.group(2), mo.group(3)))
            date = datetime.date(year, month, day)

            locs = rec.root.findall(".//field[@type='location']")
            for loc in locs:
                ll = latlongparse(loc.get('latlong'))
                if ll is None:
                    continue
                points.append([ll.lat, ll.long, rec.id, date])

        points.sort(key=lambda x: x[3])
        startdate = points[0][3]
        for i in xrange(len(points)):
            days = (points[i][3] - startdate).days
            points[i][3] = points[i][3].isoformat()
            points[i].append(days)

        context['points'] = points
        context['center_point'] = [points[0][0], points[0][1], 7]

        return render("dataview.html", context)
