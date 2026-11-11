"""Prayer times calculated locally (no network), standard astronomical method.

Same approach as the widely used PrayTimes.org algorithm: sun position per day,
twilight angles per method, a high-latitude rule for northern summers, and
optional per-prayer minute adjustments.
"""
import datetime as dt
import math

# key: (label, fajr angle, isha angle or None, isha minutes after maghrib or None)
METHODS = {
    "mwl": ("Muslim World League (common in Europe)", 18.0, 17.0, None),
    "diyanet": ("Diyanet / DITIB (Turkey, Turkish mosques in Germany)", 18.0, 17.0, None),
    "umm_al_qura": ("Umm al-Qura (Saudi Arabia)", 18.5, None, 90),
    "egypt": ("Egyptian General Authority", 19.5, 17.5, None),
    "isna": ("ISNA (North America)", 15.0, 15.0, None),
    "uoif": ("UOIF (France, 12°)", 12.0, 12.0, None),
    "karachi": ("Karachi (Pakistan, India)", 18.0, 18.0, None),
    "gulf": ("Gulf region (UAE, Qatar)", 19.5, None, 90),
    "kuwait": ("Kuwait", 18.0, 17.5, None),
    "jakim": ("JAKIM (Malaysia)", 20.0, 18.0, None),
    "kemenag": ("Kemenag (Indonesia)", 20.0, 18.0, None),
}

# What to do when the sun never gets low enough for Fajr/Isha (northern summers)
HIGH_LAT_RULES = {
    "angle": "Angle-based (recommended for Europe)",
    "seventh": "One-seventh of the night",
    "middle": "Middle of the night",
    "none": "None (pure astronomy)",
}

PRAYERS = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

# Presets grouped by country; any town can be found with the search box or typed as coordinates
COUNTRIES = {
    "Germany": {
        "Berlin": (52.5200, 13.4050), "Hamburg": (53.5511, 9.9937), "München (Munich)": (48.1351, 11.5820),
        "Köln (Cologne)": (50.9375, 6.9603), "Frankfurt am Main": (50.1109, 8.6821), "Stuttgart": (48.7758, 9.1829),
        "Düsseldorf": (51.2277, 6.7735), "Dortmund": (51.5136, 7.4653), "Essen": (51.4556, 7.0116),
        "Leipzig": (51.3397, 12.3731), "Bremen": (53.0793, 8.8017), "Dresden": (51.0504, 13.7373),
        "Hannover": (52.3759, 9.7320), "Nürnberg (Nuremberg)": (49.4521, 11.0767), "Duisburg": (51.4344, 6.7623),
        "Bochum": (51.4818, 7.2162), "Wuppertal": (51.2562, 7.1508), "Bielefeld": (52.0302, 8.5325),
        "Bonn": (50.7374, 7.0982), "Münster": (51.9607, 7.6261), "Mannheim": (49.4875, 8.4660),
        "Karlsruhe": (49.0069, 8.4037), "Augsburg": (48.3705, 10.8978), "Wiesbaden": (50.0782, 8.2398),
        "Gelsenkirchen": (51.5177, 7.0857), "Mönchengladbach": (51.1805, 6.4428), "Braunschweig": (52.2689, 10.5268),
        "Aachen": (50.7753, 6.0839), "Kiel": (54.3233, 10.1228), "Chemnitz": (50.8278, 12.9214),
        "Halle (Saale)": (51.4969, 11.9688), "Magdeburg": (52.1205, 11.6276), "Freiburg im Breisgau": (47.9990, 7.8421),
        "Krefeld": (51.3388, 6.5853), "Mainz": (49.9929, 8.2473), "Lübeck": (53.8655, 10.6866),
        "Erfurt": (50.9848, 11.0299), "Oberhausen": (51.4963, 6.8638), "Rostock": (54.0924, 12.0991),
        "Kassel": (51.3127, 9.4797), "Hagen": (51.3671, 7.4633), "Saarbrücken": (49.2402, 6.9969),
        "Hamm": (51.6739, 7.8150), "Potsdam": (52.3906, 13.0645), "Ludwigshafen": (49.4774, 8.4452),
        "Oldenburg": (53.1435, 8.2146), "Osnabrück": (52.2799, 8.0472), "Heidelberg": (49.3988, 8.6724),
        "Darmstadt": (49.8728, 8.6512), "Regensburg": (49.0134, 12.1016), "Würzburg": (49.7913, 9.9534),
        "Ulm": (48.4011, 9.9876), "Göttingen": (51.5413, 9.9158), "Offenbach am Main": (50.0956, 8.7761),
    },
    "Austria": {"Wien (Vienna)": (48.2082, 16.3738), "Graz": (47.0707, 15.4395), "Linz": (48.3069, 14.2858),
                "Salzburg": (47.8095, 13.0550), "Innsbruck": (47.2692, 11.4041)},
    "Switzerland": {"Zürich": (47.3769, 8.5417), "Genève (Geneva)": (46.2044, 6.1432), "Basel": (47.5596, 7.5886),
                    "Bern": (46.9480, 7.4474), "Lausanne": (46.5197, 6.6323)},
    "Netherlands": {"Amsterdam": (52.3676, 4.9041), "Rotterdam": (51.9244, 4.4777), "Den Haag": (52.0705, 4.3007),
                    "Utrecht": (52.0907, 5.1214), "Eindhoven": (51.4416, 5.4697)},
    "Belgium": {"Brussel / Bruxelles": (50.8503, 4.3517), "Antwerpen": (51.2194, 4.4025), "Liège": (50.6326, 5.5797)},
    "France": {"Paris": (48.8566, 2.3522), "Marseille": (43.2965, 5.3698), "Lyon": (45.7640, 4.8357),
               "Strasbourg": (48.5734, 7.7521), "Toulouse": (43.6047, 1.4442), "Lille": (50.6292, 3.0573)},
    "United Kingdom": {"London": (51.5074, -0.1278), "Birmingham": (52.4862, -1.8904), "Manchester": (53.4808, -2.2426),
                       "Bradford": (53.7960, -1.7594), "Leicester": (52.6369, -1.1398), "Glasgow": (55.8642, -4.2518)},
    "Scandinavia": {"Stockholm": (59.3293, 18.0686), "Oslo": (59.9139, 10.7522), "Copenhagen": (55.6761, 12.5683),
                    "Malmö": (55.6050, 13.0038), "Helsinki": (60.1699, 24.9384)},
    "Saudi Arabia": {"Riyadh": (24.7136, 46.6753), "Makkah": (21.4225, 39.8262), "Madinah": (24.4672, 39.6112),
                     "Jeddah": (21.4858, 39.1925), "Dammam": (26.4207, 50.0888)},
    "Jordan": {"Amman": (31.9539, 35.9106), "Irbid": (32.5556, 35.8500), "Zarqa": (32.0728, 36.0880)},
    "Gulf": {"Dubai": (25.2048, 55.2708), "Abu Dhabi": (24.4539, 54.3773), "Doha": (25.2854, 51.5310),
             "Kuwait City": (29.3759, 47.9774), "Manama": (26.2285, 50.5860), "Muscat": (23.5880, 58.3829)},
    "Middle East & Africa": {"Cairo": (30.0444, 31.2357), "Baghdad": (33.3152, 44.3661), "Beirut": (33.8938, 35.5018),
                             "Damascus": (33.5138, 36.2765), "Jerusalem": (31.7683, 35.2137),
                             "Istanbul": (41.0082, 28.9784), "Ankara": (39.9334, 32.8597),
                             "Casablanca": (33.5731, -7.5898), "Tunis": (36.8065, 10.1815),
                             "Algiers": (36.7538, 3.0588)},
    "Asia": {"Karachi": (24.8607, 67.0011), "Lahore": (31.5204, 74.3587), "Jakarta": (-6.2088, 106.8456),
             "Kuala Lumpur": (3.1390, 101.6869), "Dhaka": (23.8103, 90.4125)},
    "Americas & Oceania": {"New York": (40.7128, -74.0060), "Toronto": (43.6532, -79.3832),
                           "Los Angeles": (34.0522, -118.2437), "Chicago": (41.8781, -87.6298),
                           "Sydney": (-33.8688, 151.2093)},
}
# Flat lookup (also keeps older saved settings working)
CITIES = {city: ll for cities in COUNTRIES.values() for city, ll in cities.items()}
CITIES.setdefault("Berlin", COUNTRIES["Germany"]["Berlin"])
CITIES.setdefault("Wien", COUNTRIES["Austria"]["Wien (Vienna)"])


def country_of(city):
    return next((c for c, cities in COUNTRIES.items() if city in cities), None)


def suggested_method(country):
    """A sensible default calculation method for a country (the user can change it)."""
    return {"Germany": "mwl", "Austria": "mwl", "Switzerland": "mwl", "Netherlands": "mwl",
            "Belgium": "mwl", "France": "uoif", "United Kingdom": "mwl", "Scandinavia": "mwl",
            "Saudi Arabia": "umm_al_qura", "Jordan": "mwl", "Gulf": "gulf",
            "Middle East & Africa": "egypt", "Asia": "karachi",
            "Americas & Oceania": "isna"}.get(country, "mwl")


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


def prayer_times(date, lat, lng, utc_offset_hours, method="umm_al_qura", asr_hanafi=False,
                 high_lat="angle", offsets=None):
    """Returns {name: datetime} for the six daily times on `date` (a datetime.date).

    high_lat: rule for Fajr/Isha when twilight lasts all night (see HIGH_LAT_RULES).
    offsets: {prayer: minutes} added at the end, to match a local mosque timetable.
    """
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

    def portion(angle):
        if high_lat == "middle":
            return night / 2
        if high_lat == "seventh":
            return night / 7
        return night * angle / 60          # angle-based (also the fallback for "none")

    # Fajr: never earlier than the rule allows; also used when the angle is never reached
    fajr_limit = portion(fajr_angle)
    if hours["Fajr"] is None or (high_lat != "none" and hours["Sunrise"] - hours["Fajr"] > fajr_limit):
        hours["Fajr"] = hours["Sunrise"] - fajr_limit
    if not isha_minutes:
        isha_limit = portion(isha_angle)
        if hours["Isha"] is None or (high_lat != "none" and hours["Isha"] - hours["Maghrib"] > isha_limit):
            hours["Isha"] = hours["Maghrib"] + isha_limit

    base = dt.datetime(date.year, date.month, date.day)
    out = {}
    for name in PRAYERS:
        local = hours[name] + utc_offset_hours - lng / 15
        out[name] = base + dt.timedelta(minutes=round(local * 60) + int((offsets or {}).get(name, 0) or 0))
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
