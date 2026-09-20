"""
recommendation.py

Contains the application's decision-making logic.

queries.py:
    Retrieves candidate trains from MySQL.

recommendation.py:
    Analyses those candidates and determines the best option.

app.py:
    Displays the result to the user.

Special train rules handled here:
    - "(Not on Sunday ...)" trains are dropped on Sundays and on
      the dates listed in HOLIDAYS.
    - "(Ladies Spl.)" trains are never the main recommendation;
      they are returned in a separate list.
    - AC trains are never the FIRST recommendation. If an AC train
      would be rank 1, it is shown at rank 2 instead.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


# Mumbai locals run on Indian Standard Time regardless of where
# this app happens to be hosted. date.today() / datetime.now()
# without a timezone would use the SERVER's clock instead, which is
# wrong the moment the app is deployed somewhere outside India.
IST = ZoneInfo("Asia/Kolkata")

# A full day in minutes, used to correct for midnight rollover in
# the time arithmetic below (e.g. a train departing 23:50 and
# arriving 00:15 the next day).
MINUTES_PER_DAY = 24 * 60

# Longest Western line journey (Churchgate <-> Dahanu Road) is well
# under 5 hours; anything beyond that in a "journey" is bad
# timetable data, not a real trip.
MAX_REASONABLE_JOURNEY_MINUTES = 300

# Only trains leaving within this many minutes of the FIRST
# available train are ranked against each other.
#
# Why this exists:
#   - "Earliest arrival" needs to look a little beyond the first few
#     departures, because a Fast train leaving 20 minutes later can
#     still reach the destination before a Slow train leaving now.
#   - But without a limit, "Shortest journey" could recommend a Fast
#     train that leaves 3 hours from now just because it is 5
#     minutes quicker.
LOOKAHEAD_WINDOW_MINUTES = 90

# ------------------------------------------------------------
# SPECIAL TRAIN RULES
# ------------------------------------------------------------

# Add dates here when trains marked "(Not on Sunday ...)" should be
# treated as unavailable (Indian Railways runs the Sunday timetable
# on these days).
#
# Add ONE line per holiday, INSIDE the square brackets below:
#
#     date(YEAR, MONTH, DAY),
#
#   - Do NOT put a leading zero on the month or day.
#     date(2026, 10, 02) is a SyntaxError in Python, use date(2026, 10, 2).
#   - Keep the comma at the end of every line.
#   - Sundays are handled automatically and do not need to be listed.
#
# The line below is only an example - remove the # to activate it.
HOLIDAYS = [
    # date(2026, 10, 2),
]


def check_holidays_list(holidays):
    """
    Make sure every entry in HOLIDAYS is a real datetime.date.

    Without this check, a typo like "2026-10-02" (a string) would
    not crash anything - the holiday would just silently never
    match, and the trains would keep showing up on that day.
    """

    for entry in holidays:

        if type(entry) is not date:
            raise ValueError(
                f"HOLIDAYS must contain date(YEAR, MONTH, DAY) "
                f"values, but found: {entry!r}"
            )


check_holidays_list(HOLIDAYS)


def clean_name(train_name):
    """
    Lower-case a train name and collapse repeated spaces so the
    text checks below are not thrown off by capital letters or
    accidental double spaces in the database.
    """

    if train_name is None:
        return ""

    return " ".join(train_name.lower().split())


def is_ladies_special(train_name):
    """
    Identify a Ladies Special train from the train name.

    Recognition rule:
        '(Ladies Spl.)'  or  '(Ladies Special)'
    """

    name = clean_name(train_name)

    return "ladies spl" in name or "ladies special" in name


def is_ac_train(train_name, train_type=None):
    """
    Identify an AC train from its name (or its type).

    Recognition rule - "AC" must appear as a separate word, so
    (AC), - AC -, A/C and "Air Conditioned" are recognised, but a
    station name that merely contains the letters "ac" is not.
    """

    for text in (train_name, train_type):

        words = clean_name(text)

        for symbol in "()[]-,._&":
            words = words.replace(symbol, " ")

        # Single spaces on both sides, so " ac " only matches the
        # whole word.
        words = " " + " ".join(words.split()) + " "

        if " ac " in words or " a/c " in words or " a c " in words:
            return True

        if "air condition" in words:
            return True

    return False


def is_not_on_sunday_or_holiday(train_name):
    """
    Identify trains marked as unavailable on Sundays/holidays.

    Recognition rule - the name contains "not on sun", which covers
    every way this label appears in the timetable:
        '(Not on Sunday)'
        '(Not on Sundays & Holidays)'
        '(Not on Sunday & Holiday)'
        '(Not on Sun.)'
    """

    return "not on sun" in clean_name(train_name)


def as_date(value):
    """
    Return a plain datetime.date, even if a datetime was passed in.
    (A datetime never equals a date, so a datetime would silently
    fail the HOLIDAYS check.)
    """

    if isinstance(value, datetime):
        return value.date()

    return value


def today_ist():
    """
    Today's date in Indian Standard Time.
    """

    return datetime.now(IST).date()


def is_sunday_or_holiday(service_date):
    """
    True if 'Not on Sunday' trains do not run on this date.
    """

    service_date = as_date(service_date)

    return service_date.weekday() == 6 or service_date in HOLIDAYS


def describe_non_operating_day(service_date):
    """
    Short label for the notice shown in the app.

    Returns:
        'a Sunday'
        'a listed holiday'
        None   (ordinary day - nothing to announce)
    """

    service_date = as_date(service_date)

    if service_date.weekday() == 6:
        return "a Sunday"

    if service_date in HOLIDAYS:
        return "a listed holiday"

    return None


def classify_train_restriction(train_name, service_date):
    """
    Determine whether a train has a special recommendation rule
    on the given date.

    service_date is the date the commuter will actually TRAVEL on.
    That is today, or tomorrow when the app is showing tomorrow's
    first trains.

    Returns:
        'not_running_today'
        'ladies_special'
        None

    Order matters: "not running" is checked first. A train that is
    both "Ladies Spl." and "Not on Sunday" must NOT be shown on a
    Sunday just because it is also a Ladies Special.
    """

    if is_not_on_sunday_or_holiday(train_name):
        if is_sunday_or_holiday(service_date):
            return "not_running_today"

    if is_ladies_special(train_name):
        return "ladies_special"

    return None


# ============================================================
# TIME UTILITIES
# ============================================================

def time_to_minutes(value):
    """
    Convert a time value into minutes after midnight.

    Example:
        10:30 -> 630

    Accepts:
        datetime.time
        datetime.timedelta (what mysql-connector-python actually
            returns for SQL TIME columns, instead of datetime.time)
        a string in HH:MM or HH:MM:SS format
    """

    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)

    if isinstance(value, time):
        return value.hour * 60 + value.minute

    if isinstance(value, str):
        try:
            parts = value.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        except (IndexError, ValueError):
            raise ValueError(
                f"Could not parse time string: {value!r}. "
                f"Expected HH:MM or HH:MM:SS."
            )

        return hour * 60 + minute

    raise TypeError(
        "Time value must be datetime.time, datetime.timedelta, "
        "or an HH:MM string."
    )


def calculate_wait_time(current_time, source_time, next_day=False):
    """
    Calculate how long a commuter has to wait for the train.

    next_day:
        True when the train belongs to TOMORROW's timetable (the app
        found nothing left today and is showing tomorrow's first
        trains). A full day is added no matter what the clock times
        look like.

        This cannot be guessed from the clock times alone: tomorrow's
        06:20 train looks "later than" a current time of 06:15, and
        would wrongly come out as a 5 minute wait.

    Safety net:
        For a same-day search a negative wait means the train has
        already left, so it is treated as the next occurrence.
    """

    current = time_to_minutes(current_time)
    source = time_to_minutes(source_time)

    wait = source - current

    if next_day or wait < 0:
        wait += MINUTES_PER_DAY

    return wait


def calculate_journey_duration(source_time, destination_time):
    """
    Calculate journey duration between source and destination.

    Midnight handling:
        A train departing 23:50 and arriving 00:15 crosses
        midnight, which looks like a negative duration in plain
        minutes-since-midnight terms. Add a day back for that case.

    Sanity check:
        If the duration is still negative, or unreasonably long
        even after adjusting for midnight, treat it as bad
        timetable data rather than a real journey.
    """

    source = time_to_minutes(source_time)
    destination = time_to_minutes(destination_time)

    duration = destination - source

    if duration < 0:
        duration += MINUTES_PER_DAY

    # Longest Western line journey (Churchgate <-> Dahanu Road) is
    # well under 5 hours; anything beyond that is bad data, not a
    # real overnight local train.
    if duration < 0 or duration > MAX_REASONABLE_JOURNEY_MINUTES:
        return None

    return duration


# ============================================================
# TRAIN SCORING
# ============================================================

def score_train(train):
    """
    Calculate a score used to rank candidate trains.

    Lower score = better option.

    Primary factor:
        How soon the commuter actually arrives (wait + journey
        time), not the raw destination clock time - a train
        arriving just after midnight should not be ranked as
        "earliest" purely because 00:15 is a small number.

    Secondary factor:
        Shorter journey.

    Tertiary factor:
        Slight preference for Fast trains.

    This is deliberately simple and explainable.

    Note:
        Expects to be called on an option already produced by
        prepare_train_option(), which provides wait_minutes and
        journey_minutes.
    """

    wait_minutes = train.get("wait_minutes")
    journey_minutes = train.get("journey_minutes")

    # Invalid or missing timetable data.
    # (Returns a tuple, like the normal case, so that sorting a mix
    # of good and bad trains can never crash on comparing a tuple
    # with a plain number.)
    if wait_minutes is None or journey_minutes is None:
        return (float("inf"), float("inf"), 0)

    total_minutes_until_arrival = wait_minutes + journey_minutes

    # Fast trains receive a small tie-breaking advantage.
    # (train_type can be empty in the database, so guard against None.)
    train_type = train.get("train_type") or ""
    fast_bonus = 1 if train_type.lower() == "fast" else 0

    return (
        total_minutes_until_arrival,
        journey_minutes,
        -fast_bonus
    )


# ============================================================
# PREPARE RESULT
# ============================================================

def prepare_train_option(train, current_time, next_day=False):
    """
    Add useful calculated information to a raw SQL result.

    If a time is missing or unreadable, wait_minutes and
    journey_minutes are set to None so the train can be skipped
    instead of crashing the whole search.
    """

    result = dict(train)

    try:
        result["wait_minutes"] = calculate_wait_time(
            current_time,
            train["source_time"],
            next_day
        )

        result["journey_minutes"] = calculate_journey_duration(
            train["source_time"],
            train["destination_time"]
        )

    except (TypeError, ValueError):
        result["wait_minutes"] = None
        result["journey_minutes"] = None

    return result


def keep_trains_within_window(trains):
    """
    Keep only the trains leaving within LOOKAHEAD_WINDOW_MINUTES
    of the first train in the list.
    """

    if not trains:
        return []

    first_wait = min(train["wait_minutes"] for train in trains)
    last_allowed_wait = first_wait + LOOKAHEAD_WINDOW_MINUTES

    return [
        train for train in trains
        if train["wait_minutes"] <= last_allowed_wait
    ]


# ============================================================
# RECOMMENDATION
# ============================================================

VALID_PREFERENCES = ("earliest_arrival", "shortest_journey", "least_wait")


def sort_trains(trains, preference):
    """
    Sort a list of prepared trains, best first, for the chosen
    preference.

    Every tie-breaker uses wait + journey (minutes from now)
    instead of the raw destination clock time, so a train that
    arrives just after midnight is not treated as "earliest"
    because 00:15 is a small number.
    """

    if preference == "shortest_journey":

        trains.sort(
            key=lambda train: (
                train["journey_minutes"],
                train["wait_minutes"] + train["journey_minutes"],
                train["wait_minutes"]
            )
        )

    elif preference == "least_wait":

        trains.sort(
            key=lambda train: (
                train["wait_minutes"],
                train["wait_minutes"] + train["journey_minutes"],
                train["journey_minutes"]
            )
        )

    else:
        # Default:
        # Reach the destination as early as possible.
        trains.sort(
            key=score_train
        )


def put_non_ac_train_first(trains):
    """
    Make sure the first train in a ranked list is not an AC train.

    If the best-ranked train is AC, the best NON-AC train is moved
    to the front, which pushes the AC train down to rank 2.
    Every other train keeps its order, so an AC train that was
    already rank 3 or lower stays where it is.

    The train that was moved up is tagged with
    "better_ac_available" so the explanation can be honest that an
    AC train ranks better on the chosen preference.

    If EVERY train is AC there is nothing else to put first, so
    the list is left as it is.
    """

    if not trains:
        return

    first = trains[0]

    if not is_ac_train(first["train_name"], first.get("train_type")):
        return

    for position, train in enumerate(trains):

        if not is_ac_train(train["train_name"], train.get("train_type")):

            best_non_ac = trains.pop(position)
            best_non_ac["better_ac_available"] = True
            trains.insert(0, best_non_ac)
            return


def recommend_trains(
    trains,
    current_time,
    preference="earliest_arrival",
    current_date=None,
    next_day=False
):
    """
    Rank available trains and return a recommendation package.

    Parameters:
        trains:
            List of train dictionaries returned by queries.py.

        current_time:
            Current time of the commuter.

        preference:
            'earliest_arrival'
            'shortest_journey'
            'least_wait'

        current_date:
            The date the commuter will TRAVEL on (used for the
            "Not on Sunday" rule). Defaults to today in IST.
            When next_day is True, pass tomorrow's date here.

        next_day:
            True when the trains belong to tomorrow's timetable.

    Returns:
        {
            "recommended": {...} or None,
            "alternatives": [...],
            "ladies_specials": [...],
            "not_running_today": [...],
            "preference": preference,
            "service_date": date
        }

    "recommended" is None only when every running train is a
    Ladies Special.

    Returns None if there is nothing to show at all.
    """

    if current_date is None:
        current_date = today_ist()

    if preference not in VALID_PREFERENCES:
        raise ValueError(
            f"Unknown preference '{preference}'. "
            f"Expected one of: {', '.join(VALID_PREFERENCES)}."
        )

    if not trains:
        return None

    normal_trains = []
    ladies_specials = []
    not_running_today = []

    for train in trains:

        option = prepare_train_option(
            train,
            current_time,
            next_day
        )

        # Ignore malformed timetable data.
        if option["journey_minutes"] is None:
            continue

        if option["wait_minutes"] is None:
            continue

        # Apply the special train rules.
        restriction = classify_train_restriction(
            option["train_name"],
            current_date
        )

        if restriction == "not_running_today":
            not_running_today.append(option)

        elif restriction == "ladies_special":
            ladies_specials.append(option)

        else:
            normal_trains.append(option)

    if not normal_trains and not ladies_specials:
        return None

    # --------------------------------------------------------
    # DIFFERENT USER PREFERENCES
    # --------------------------------------------------------

    normal_trains = keep_trains_within_window(normal_trains)
    ladies_specials = keep_trains_within_window(ladies_specials)

    sort_trains(normal_trains, preference)
    sort_trains(ladies_specials, preference)

    # AC trains are never the first recommendation.
    put_non_ac_train_first(normal_trains)

    if normal_trains:
        recommended = normal_trains[0]
        alternatives = normal_trains[1:]
    else:
        recommended = None
        alternatives = []

    return {
        "recommended": recommended,
        "alternatives": alternatives,
        "ladies_specials": ladies_specials,
        "not_running_today": not_running_today,
        "preference": preference,
        "service_date": current_date
    }


# ============================================================
# EXPLANATION GENERATOR
# ============================================================

def generate_reason(
    recommended,
    preference="earliest_arrival"
):
    """
    Generate a human-readable explanation for the recommendation.

    This is useful because the application should not merely say
    "Train A recommended"; it should explain why.
    """

    train_name = recommended["train_name"]
    train_type = recommended["train_type"] or "type not listed"

    wait = recommended["wait_minutes"]
    journey = recommended["journey_minutes"]
    total = wait + journey

    # True when an AC train ranks better on this preference but was
    # moved to rank 2 (AC trains are never shown first).
    better_ac_available = recommended.get("better_ac_available", False)

    if better_ac_available:
        pool = "non-AC trains"
        ac_note = (
            " An AC train ranks better on this preference, so it "
            "is listed as option 2."
        )
    else:
        pool = "available scheduled trains"
        ac_note = ""

    if preference == "shortest_journey":

        return (
            f"{train_name} is recommended because it has "
            f"the shortest scheduled journey of approximately "
            f"{journey} minutes among the upcoming {pool} "
            f"(you wait about {wait} minutes for it)."
            f"{ac_note}"
        )

    if preference == "least_wait":

        return (
            f"{train_name} is recommended because it requires "
            f"only about {wait} minutes of waiting among the "
            f"{pool} (journey of about {journey} minutes)."
            f"{ac_note}"
        )

    return (
        f"{train_name} ({train_type}) is recommended because "
        f"it reaches the destination earliest among the "
        f"{pool} - about {total} minutes "
        f"from now ({wait} min wait + {journey} min journey)."
        f"{ac_note}"
    )


# ============================================================
# SIMPLE SUMMARY FOR STREAMLIT
# ============================================================

def create_summary(result):
    """
    Convert recommendation output into a simple dictionary
    that app.py can directly display.
    """

    if result is None:
        return {
            "found": False,
            "message": "No suitable train found."
        }

    recommended = result["recommended"]
    preference = result["preference"]

    # Only Ladies Special trains are running.
    if recommended is None:
        return {
            "found": False,
            "message": "Only Ladies Special trains are available.",
            "ladies_specials": result["ladies_specials"]
        }

    return {
        "found": True,

        "train_name": recommended["train_name"],

        "train_type": recommended["train_type"],

        "direction": recommended["train_direction"],

        "source_time": recommended["source_time"],

        "destination_time": recommended["destination_time"],

        "platform": recommended["source_platform"],

        "wait_minutes": recommended["wait_minutes"],

        "journey_minutes": recommended["journey_minutes"],

        "reason": generate_reason(recommended, preference),

        "alternatives": result["alternatives"]
    }
