
import re

yyyymmdd_re = re.compile(r'(?P<year>[\d][\d][\d][\d])(?P<month>[\d][\d])(?P<day>[\d][\d])')
yyyymmdd_hyphen_re = re.compile(r'(?P<year>[\d][\d][\d][\d])-(?P<month>[\d][\d])-(?P<day>[\d][\d])')
ddmmyyyy_re = re.compile(r'(((?P<day>[\d][\d]?)[\./:])?(?P<month>[\d][\d]?)[\./:])?(?P<year>[\d][\d][\d][\d])')
ddmmyyyy_hyphen_re = re.compile(r'(((?P<day>[\d][\d]?)[\./:])?(?P<month>[\d][\d]?)[\./:])?(?P<year>[\d][\d][\d][\d])')
range_re = re.compile(r'\s*[-:]\s*')

class Date(object):
    def __init__(self, year=None, month=None, day=None):
        assert isinstance(year, int)
        self.year = year
        self.month = month
        self.day = day

    def earliest(self):
        if self.month is None:
            return Date(self.year, 1, 1)
        if self.day is None:
            return Date(self.year, self.month, 1)
        return self

    def latest(self):
        if self.month is None:
            return Date(self.year, 12, 31)
        if self.day is None:
            return Date(self.year, self.month, 31) # FIXME - could return the correct end-day for the month, but not sure we need to.
        return self

    def __str__(self):
        return '%04d-%02d-%02d' % (self.year, self.month, self.day)

class DateRange(object):
    def __init__(self, start, end):
        self.start = start.earliest()
        self.end = end.latest()

    def __str__(self):
        return "%s:%s" % (self.start, self.end)

date_parse_errors = {
    'N': "No valid date found",
    'T': "Unparsed text after date",
}
def parse_date(input):
    """Parse a date.

    Returns (date, error_code), where date is a DateRange object, or None if no
    date could be parsed, and error_code is None if no error, or a character in
    date_parse_errors if an error occurred.

    """
    input = input.strip()
    if input == '':
        return None, None

    # Parse the start
    mo = yyyymmdd_re.match(input)
    if not mo:
        mo = yyyymmdd_hyphen_re.match(input)
    if not mo:
        mo = ddmmyyyy_re.match(input)
    if not mo:
        mo = ddmmyyyy_hyphen_re.match(input)
    if mo:
        start = Date(*map(lambda x: x and int(x), (mo.group('year'), mo.group('month'), mo.group('day'))))
    else:
        return None, 'N'


    # Check if we're at the end of the input
    pos = mo.end()
    if pos == len(input):
        return DateRange(start, start), None

    # Check for a range specifier
    mo = range_re.match(input, pos)
    if mo:
        pos = mo.end()
    else:
        return DateRange(start, start), 'T'

    # Parse the end date
    mo = yyyymmdd_re.match(input, pos)
    if not mo:
        mo = yyyymmdd_hyphen_re.match(input, pos)
    if not mo:
        mo = ddmmyyyy_re.match(input, pos)
    if not mo:
        mo = ddmmyyyy_hyphen_re.match(input, pos)
    if mo:
        end = Date(*map(lambda x: x and int(x), (mo.group('year'), mo.group('month'), mo.group('day'))))
    else:
        return DateRange(start, start), 'T'

    pos = mo.end()
    if pos == len(input):
        return DateRange(start, end), None
    return DateRange(start, end), 'T'

if __name__ == '__main__':
    tests = [
        ('1970', '1970-01-01:1970-12-31', None),
        ('1.1970', '1970-01-01:1970-01-31', None),
        ('11.1.1970', '1970-01-11:1970-01-11', None),
        ('11.1.1970-1972', '1970-01-11:1972-12-31', None),
        ('11.1.1970 - 1972', '1970-01-11:1972-12-31', None),
        ('11.1.1970 - 197', '1970-01-11:1970-01-11', 'T'),
        ('tuesday', None, 'N'),
        ('11.1.1970 12.3.1974', '1970-01-11:1970-01-11', 'T'),
        ('19700111-19721231', '1970-01-11:1972-12-31', None),
        ('19700111:19721231', '1970-01-11:1972-12-31', None),
        ('1970-01-11-1972-12-31', '1970-01-11:1972-12-31', None),
        ('1970-01-11:1972-12-31', '1970-01-11:1972-12-31', None),
        ('1970-1972', '1970-01-01:1972-12-31', None),
    ]

    def test():
        for input, expected, expected_err in tests:
            result, err = parse_date(input)
            if result is not None: result = str(result)
            if expected != result:
                print "Incorrect parse: %s -> %s, expected %s" % (input, result, expected)
            if expected_err != err:
                print "Incorrect error output for %s: got %s, expected %s" % (input, err, expected_err)
    test()
