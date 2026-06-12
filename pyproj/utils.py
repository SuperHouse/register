import datetime

from django.utils import timezone


def get_dt_as_string(dt):
    if dt.tzinfo == datetime.timezone.utc:
        timezone.make_aware(dt)
    return dt.strftime('%-d-%b-%Y %H:%M:%S')


def date_from_str(s):
    matchers = (
        '%d-%b-%Y',
        '%Y-%m-%d',
        '%d/%m/%Y',
    )
    for matcher in matchers:
        try:
            return timezone.make_aware(datetime.datetime.strptime(s, matcher), timezone.get_current_timezone())
        except ValueError:
            pass

    raise ValueError(f"oh dear, couldn't parse {s} as a date.")



def int_map(i):
    try:
        return int(i)
    except TypeError:
        return None