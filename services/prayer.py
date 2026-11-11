"""Prayer times calculated locally (no network), standard astronomical method."""
import datetime as dt
import math

# name: (fajr angle, isha angle or None, isha minutes after maghrib or None)
METHODS = {
    "umm_al_qura": ("Umm al-Qura (Makkah)", 18.5, None, 90),
    "mwl": ("Muslim World League", 18.0, 17.0, None),
    "isna": ("ISNA (North America)", 15.0, 15.0, None),
    "egypt": ("Egyptian General Authority", 19.5, 17.5, None),
    "karachi": ("Karachi", 18.0, 18.0, None),
}
PRAYERS = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

# A few presets; any latitude/longitude can be typed in
CITIES = {
    "Riyadh": (24.7136, 46.6753), "Makkah": (21.4225, 39.8262), "Madinah": (24.4672, 39.6112),
    "Jeddah": (21.4858, 39.1925), "Dammam": (26.4207, 50.0888), "Amman": (31.9539, 35.9106),
    "Dubai": (25.2048, 55.2708), "Abu Dhabi": (24.4539, 54.3773), "Doha": (25.2854, 51.5310),
    "Kuwait City": (29.3759, 47.9774), "Manama": (26.2285, 50.5860), "Muscat": (23.5880, 58.3829),
    "Cairo": (30.0444, 31.2357), "Baghdad": (33.3152, 44.3661), "Beirut": (33.8938, 35.5018),
    "Damascus": (33.5138, 36.2765), "Jerusalem": (31.7683, 35.2137), "Istanbul": (41.0082, 28.9784),
    "Casablanca": (33.5731, -7.5898), "Tunis": (36.8065, 10.1815), "Karachi": (24.8607, 67.0011),
    "Jakarta": (-6.2088, 106.8456), "Kuala Lumpur": (3.1390, 101.6869), "London": (51.5074, -0.1278),
    "Paris": (48.8566, 2.3522), "Berlin": (52.5200, 13.4050), "New York": (40.7128, -74.0060),
    "Toronto": (43.6532, -79.3832), "Los Angeles": (34.0522, -118.2437), "Sydney": (-33.8688, 151.2093),
}

_r, _d = math.radians, math.degrees


def _fix(a, mod):
    a = a - mod * math.floor(a / mod)
    return a + mod if a < 0 else a


def _julian(year, month, day):
    if month <= 2:
        year -= 1
        month += 12
    a = math.floor(year / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def _sun(jd):
    d = jd - 2451545.0
    g = _fix(357.529 + 0.98560028 * d, 360)
    q = _fix(280.459 + 0.98564736 * d, 360)
    lon = _fix(q + 1.915 * math.sin(_r(g)) + 0.020 * math.sin(_r(2 * g)), 360)
    e = 23.439 - 0.00000036 * d
    ra = _d(math.atan2(math.cos(_r(e)) * math.sin(_r(lon)), math.cos(_r(lon)))) / 15
    decl = _d(math.asin(math.sin(_r(e)) * math.sin(_r(lon))))
    eqt = q / 15 - _fix(ra, 24)
    return decl, eqt


def _hour_angle(angle, lat, decl):
    """Hours between solar noon and the sun reaching `angle` degrees below the horizon."""
    x = (-math.sin(_r(angle)) - math.sin(_r(lat)) * math.sin(_r(decl))) / (math.cos(_r(lat)) * math.cos(_r(decl)))
    if abs(x) > 1:
        return None  # the sun never gets there today (far north/south in summer)
    return _d(math.acos(x)) / 15


def prayer_times(date, lat, lng, utc_offset_hours, method="umm_al_qura", asr_hanafi=False):
    """Returns {name: datetime} for the six daily times on `date` (a datetime.date)."""
    _, fajr_angle, isha_angle, isha_minutes = METHODS.get(method, METHODS["umm_al_qura"])
    jd = _julian(date.year, date.month, date.day) - lng / (15 * 24)

    def noon(t):
        return _fix(12 - _sun(jd + t)[1], 24)

    def at(angle, t, before):
        decl = _sun(jd + t)[0]
        h = _hour_angle(angle, lat, decl)
        if h is None:
            return None
        return noon(t) + (-h if before else h)

    def asr(t):
        decl = _sun(jd + t)[0]
        factor = 2 if asr_hanafi else 1
        alt = _d(math.atan(1 / (factor + math.tan(_r(abs(lat - decl))))))
        h = _hour_angle(-alt, lat, decl)
        return noon(t) + (h if h is not None else 3)

    hours = {
        "Fajr": at(fajr_angle, 5 / 24, True),
        "Sunrise": at(0.833, 6 / 24, True),
        "Dhuhr": noon(12 / 24) + 1 / 60,     # one minute after zenith
        "Asr": asr(13 / 24),
        "Maghrib": at(0.833, 18 / 24, False),
    }
    hours["Isha"] = (hours["Maghrib"] + isha_minutes / 60) if isha_minutes else at(isha_angle, 18 / 24, False)
    # Twilight never fully ends at high latitudes in summer: use the common
    # "one seventh of the night" approximation for the missing times.
    if hours["Sunrise"] is None or hours["Maghrib"] is None:   # polar day / night
        hours["Sunrise"] = hours["Sunrise"] or hours["Dhuhr"] - 6
        hours["Maghrib"] = hours["Maghrib"] or hours["Dhuhr"] + 6
        if isha_minutes:
            hours["Isha"] = hours["Maghrib"] + isha_minutes / 60
    night = 24 - (hours["Maghrib"] - hours["Sunrise"])
    if hours["Fajr"] is None:
        hours["Fajr"] = hours["Sunrise"] - night / 7
    if hours["Isha"] is None:
        hours["Isha"] = hours["Maghrib"] + night / 7

    base = dt.datetime(date.year, date.month, date.day)
    out = {}
    for name in PRAYERS:
        local = hours[name] + utc_offset_hours - lng / 15
        out[name] = base + dt.timedelta(minutes=round(local * 60))
    return out


def local_utc_offset_hours(now=None):
    now = now or dt.datetime.now().astimezone()
    return now.utcoffset().total_seconds() / 3600


def next_prayer(times, now):
    """(name, datetime) of the next prayer today (Sunrise excluded), or None after Isha."""
    for name in PRAYERS:
        if name != "Sunrise" and times[name] > now:
            return name, times[name]
    return None
