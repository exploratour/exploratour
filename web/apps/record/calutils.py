from apps.store.models import Record
from apps.store.search import Collection as SearchCollection
import calendar
import datetime
from restpose import Field

def mkgrpname((start, end),):
    if start + 1 == end:
        return "%d records" % (start + 1)
    else:
        return "%d-%d records" % (start + 1, end)

def mkgroups(dates):
    """Make the groups that the dates will be highlighted with.

    """
    if dates:
        max_per_day = max(map(lambda x: len(x), dates.values()))
    else:
        max_per_day = 1
    if max_per_day <= 4:
        groups = [1, 2, 3, 4]
    else:
        groups = [1, int(max_per_day * .5), int(max_per_day * .75), max_per_day]
    groupnames = ["1 record",
                  mkgrpname(groups[0:2]),
                  mkgrpname(groups[1:3]),
                  mkgrpname(groups[2:4])]
    if max_per_day < 4:
        groupnames = groupnames[:max_per_day]
    return groupnames, groups


def date_range(calstyle, date):
    """Get the date range that the calendar would have when showing a
    given date.

    """
    if calstyle == 'year':
        return date[:4] + '-01-01', date[:4] + '-12-31'
    elif calstyle == 'month':
        return date[:7] + '-01', date[:7] + '-31'
    elif calstyle == 'day':
        return date, date

def mkmonth(year, month, dates, groups):
    """Make an array of data for the year and month given.

    """
    cal = calendar.monthcalendar(int(year), month)
    for row in cal:
        for index in range(len(row)):
            day = row[index]
            if day == 0:
                row[index] = None
            else:
                date = '%04.d-%02.d-%02.d' % (year, month, day)
                items = dates.get(date, ())
                grp = 0
                len_items = len(items)
                if len_items > 0:
                    while grp < len(groups):
                        grp += 1
                        if len_items <= groups[grp - 1]:
                            break

                row[index] = [day, grp, items, date]
    while len(cal) < 6:
        cal.append([None] * 7)
    return dict(name=calendar.month_name[month], weeks=cal,
                startdate='%04.d-%02.d' % (year, month))

def get_firstdate(q, datefield):
    """Get the first date in the results of a query.

    """
    sq = q.filter(Field(datefield).exists()).order_by(datefield)[:1]
    try:
        sq0 = sq[0]
    except IndexError:
        return None
    return min((date for date in sq0.data.get(datefield, [])))


def calendar_items(id, incsubs, calstyle, startdate,
                   year, month, day, datefield):
    # If date was supplied as year,month,day, convert it.
    if year is not None:
        startdate = '%04.d' % int(year)
        if month is not None:
            startdate += '-%02.d' % int(month)
            if day is not None:
                startdate += '-%02.d' % int(day)

    record_docs = SearchCollection.doc_type('record')
    if incsubs:
        q = record_docs.field.coll.is_or_is_descendant(id)
    else:
        q = record_docs.field.coll.is_in(id)

    info = q.calc_facet_count(datefield).check_at_least(-1).info
    counts = info[0]['counts']
    counts.sort()

    prevdate = None
    nextdate = None
    firstdate = None
    years = set()
    dates = {}

    if not startdate:
        # No start date supplied.
        if len(counts) > 0:
            startdate = '%04.d-%02.d-%02.d' % tuple(counts[0][0])
        else:
            startdate = None

    # Adjust the accuracy of startdate according to the calendar style, and set
    # enddate accordingly.
    if startdate is not None:
        startdate, enddate = date_range(calstyle, startdate)
        q = q.filter(Field(datefield).range(startdate, enddate))

        # Set prevdate, nextdate, firstdate, years
        startdate_tuple = (int(startdate[:4]),
                           int(startdate[5:7]),
                           int(startdate[8:10]))
        enddate_tuple = (int(enddate[:4]),
                         int(enddate[5:7]),
                         int(enddate[8:10]))
        for (date_tuple, count) in counts:
            date_tuple = tuple(date_tuple)
            years.add(date_tuple[0])
            if date_tuple < startdate_tuple:
                if prevdate is None or prevdate < date_tuple:
                    prevdate = date_tuple
            elif date_tuple > enddate_tuple:
                if nextdate is None or nextdate > date_tuple:
                    nextdate = date_tuple
        years = tuple(sorted(years))
        if prevdate is not None:
            prevdate = '%04.d-%02.d-%02.d' % tuple(prevdate)
        if nextdate is not None:
            nextdate = '%04.d-%02.d-%02.d' % tuple(nextdate)

        # Set dates
        for r in q:
            for date in r.data.get(datefield, []):
                dates.setdefault(date, []).append(r.object)
                if firstdate is None:
                    firstdate = date
                elif firstdate > date:
                    firstdate = date

    # Set year, month, day
    year = 1
    month = 1
    day = 1
    if startdate is not None:
        if len(startdate) > 0:
            year = int(startdate[:4])
        if len(startdate) > 4:
            month = max(1, int(startdate[5:7]))
        if len(startdate) > 7:
            day = max(1, int(startdate[8:10]))

    # Months is always the list of all months.
    months = [(i, calendar.month_name[i]) for i in xrange(1, 13)]

    # Count the number of entries on each day, and set the groupings
    # accordingly.
    groupnames, groups = mkgroups(dates)

    result = dict(calstyle=calstyle, dates=dates,
                  years=years, months=months,
                  startdate=startdate,
                  year=year, month=month, day=day,
                  groupnames=groupnames,
                  nextdate=nextdate, prevdate=prevdate)

    if int(year) <= 0:
        # FIXME - hack to handle missing data, and out of range dates.
	year = datetime.datetime.now().year
	month = datetime.datetime.now().month
	day = datetime.datetime.now().day

    if calstyle == 'year':
        months = []
        for month in range(1, 13):
            months.append(mkmonth(year, month, dates, groups))
        result['months'] = months

    if calstyle == 'month':
        result['month_grid'] = mkmonth(year, month, dates, groups)

    elif calstyle == 'day':
        records = dates.get(startdate, ())
        result['records'] = records

    return result
