"""
app.py

Mumbai Local Assistant
----------------------

User-facing Streamlit application.

Application flow:

    User Input
        ↓
    MySQL Queries
        ↓
    Candidate Trains
        ↓
    Recommendation Engine
        ↓
    Result + Explanation

Current project scope:
    - Scheduled timetable data
    - Direct source → destination journeys
    - Train type filtering
    - Platform information
    - Arrival time at source
    - Scheduled arrival at destination
    - "Not on Sunday" trains hidden on Sundays and listed holidays
    - Ladies Special trains shown separately

Not included:
    - Live train location
    - Real-time delay updates
    - Cancellation detection
    - Dynamic platform changes
"""

import streamlit as st
from datetime import datetime, timedelta

from database import get_connection
from queries import (
    get_all_stations,
    get_lines_for_station,
    find_train_options,
    get_stops_between,
)

from recommendation import (
    IST,
    recommend_trains,
    create_summary,
    time_to_minutes,
    is_sunday_or_holiday,
    describe_non_operating_day,
)


# How many trains to fetch from MySQL for ranking.
#
# This must be much bigger than the number of rows shown on screen.
# "Earliest arrival" can only be worked out correctly if the list
# includes the Fast trains leaving a little later than the first few
# Slow trains. (recommendation.py then trims the list to a sensible
# lookahead window.)
CANDIDATE_LIMIT = 150

# How many rows to show in the "Other suitable options" table.
MAX_ALTERNATIVES_SHOWN = 10

# One clock reading per script run, in Indian Standard Time.
# The date and the time below both come from this single reading, so
# a search made a moment before midnight can never mix "23:59" with
# tomorrow's date.
now_ist = datetime.now(IST)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Mumbai Local Assistant",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.6rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        font-size: 1.05rem;
        color: #666666;
        margin-bottom: 1.5rem;
    }

    .small-label {
        font-size: 0.85rem;
        color: #666666;
        margin-bottom: 0.15rem;
    }

    .big-value {
        font-size: 1.2rem;
        font-weight: 600;
    }

    /* Keep Streamlit's top controls, but remove the colored decoration bar. */
    div[data-testid="stDecoration"] {
        display: none;
    }

    header[data-testid="stHeader"] {
        background: transparent;
        box-shadow: none;
    }

    .disclaimer {
        font-size: 0.80rem;
        color: #777777;
        padding: 0.75rem;
        border-top: 1px solid #dddddd;
        margin-top: 2rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🚆 Mumbai Local Assistant</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="subtitle">
        From timetable data to a practical train recommendation.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE HELPER
# ============================================================

def fetch_stations():
    """
    Fetch station data from MySQL.

    Returns:
        List of station dictionaries.

    Raises:
        RuntimeError if database access fails.
    """

    connection = None

    try:
        connection = get_connection()
        return get_all_stations(connection)

    except Exception as error:
        raise RuntimeError(
            f"Unable to load stations from database: {error}"
        ) from error

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def format_time(value):
    """
    Format a time value as a clean, zero-padded HH:MM string.

    Accepts either a timedelta (what queries.py's results come
    back as, since mysql-connector-python returns SQL TIME columns
    that way) or a datetime.time (what Streamlit's time widget
    returns). Without this, the two types print inconsistently -
    a timedelta shows "4:15:00" while a datetime.time shows
    "04:15:00" for the exact same clock time.
    """

    total_minutes = time_to_minutes(value)
    hours, minutes = divmod(total_minutes, 60)
    hours = hours % 24

    return f"{hours:02d}:{minutes:02d}"


# ============================================================
# LOAD STATIONS
# ============================================================

try:
    stations = fetch_stations()

except RuntimeError as error:
    st.error(str(error))
    st.stop()


# Stop the application if there are no stations.
if not stations:
    st.error(
        "No stations were found in the database. "
        "Please check your MySQL data."
    )
    st.stop()


# Create:
# station label ("Name (CODE)") -> station code
#
# The code is folded into the label because station_name alone is
# not guaranteed unique - two rows that happen to share a display
# name would silently collide in a plain name -> code dictionary,
# and one of them would quietly become unselectable in the dropdown
# with no error shown anywhere.
station_map = {
    f"{station['station_name']} ({station['station_code']})":
        station["station_code"]
    for station in stations
}

station_names = list(station_map.keys())


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Journey Settings")

    st.caption(
        "Choose your journey and let the application "
        "find suitable scheduled trains."
    )

    source_name = st.selectbox(
        "From",
        station_names,
        index=None,
        placeholder="Select source station",
    )

    destination_name = st.selectbox(
        "To",
        station_names,
        index=None,
        placeholder="Select destination station",
    )

    use_live_time = st.checkbox(
        "Use live time (IST)",
        value=True,
    )

    if use_live_time:

        travel_date = now_ist.date()

        current_time = now_ist.time().replace(
            second=0,
            microsecond=0
        )

        st.caption(
            f"Now: {travel_date.strftime('%a, %d %b %Y')}, "
            f"{current_time.strftime('%H:%M')} IST"
        )

    else:

        # Give the two widgets their starting values ONCE, through
        # session_state. If the starting value were passed as
        # value=<the clock right now>, it would change every minute,
        # Streamlit would treat that as a brand new widget, and the
        # time the user picked would silently reset to "now".
        if "custom_date" not in st.session_state:
            st.session_state["custom_date"] = now_ist.date()

        if "custom_time" not in st.session_state:
            st.session_state["custom_time"] = now_ist.time().replace(
                second=0,
                microsecond=0
            )

        travel_date = st.date_input(
            "Travel date",
            key="custom_date",
        )

        current_time = st.time_input(
            "Time at source station",
            key="custom_time",
        )

    preference_label = st.selectbox(
        "What matters most?",
        [
            "Earliest arrival",
            "Shortest journey",
            "Least waiting time",
        ],
    )

    train_type_label = st.selectbox(
        "Train type",
        [
            "Any",
            "Fast",
            "Slow",
        ],
    )

    search_button = st.button(
        "🔎 Find best train",
        use_container_width=True,
        type="primary",
    )

    st.divider()

    st.subheader("Project Scope")

    st.caption(
        """
        This MVP uses scheduled railway data.

        It does not provide live train tracking,
        real-time delays, cancellations, or dynamic
        platform changes.
        """
    )


# ============================================================
# SEARCH HELPERS
# ============================================================

def search_trains(
    connection,
    source_code,
    destination_code,
    current_time,
    travel_date,
    train_type
):
    """
    Find the candidate trains for a journey.

    Step 1:
        Trains still to come on the travel date.

    Step 2:
        If nothing is left (e.g. searching late at night, after the
        last local has gone), search again for the first trains of
        the NEXT day.

    Each step checks its OWN date. Whether "Not on Sunday" trains
    are hidden depends on the date the train actually runs on:
    a Saturday night search must hide them (tomorrow is Sunday), a
    Sunday night search must show them again (tomorrow is Monday).

    Returns:
        (train_options, service_date, showing_next_day)
    """

    service_date = travel_date
    showing_next_day = False

    train_options = find_train_options(
        connection=connection,
        source_code=source_code,
        destination_code=destination_code,
        current_time=current_time,
        train_type=train_type,
        direction=None,
        limit=CANDIDATE_LIMIT,
        exclude_not_on_sunday=is_sunday_or_holiday(service_date),
    )

    if not train_options:

        service_date = travel_date + timedelta(days=1)
        showing_next_day = True

        train_options = find_train_options(
            connection=connection,
            source_code=source_code,
            destination_code=destination_code,
            current_time=None,
            train_type=train_type,
            direction=None,
            limit=CANDIDATE_LIMIT,
            exclude_not_on_sunday=is_sunday_or_holiday(service_date),
        )

    return train_options, service_date, showing_next_day


def format_minutes(minutes):
    """
    Show minutes in a readable way.

    Example:
        5   -> "5 min"
        280 -> "4 h 40 min"

    (Tomorrow's first train can be several hours away, and
    "280 min" is hard to read.)
    """

    if minutes < 60:
        return f"{minutes} min"

    hours, remaining = divmod(minutes, 60)

    if remaining == 0:
        return f"{hours} h"

    return f"{hours} h {remaining:02d} min"


def build_train_rows(trains, first_rank=None):
    """
    Turn a list of trains into rows for st.dataframe().

    If first_rank is given, a Rank column is added, counting up
    from that number.
    """

    rows = []

    for position, train in enumerate(trains):

        row = {}

        if first_rank is not None:
            row["Rank"] = first_rank + position

        row["Train"] = train["train_name"]
        row["Type"] = train["train_type"]
        row["At Source"] = format_time(train["source_time"])
        row["Destination"] = format_time(train["destination_time"])
        row["Platform"] = (
            str(train["source_platform"])
            if train["source_platform"] is not None
            else "—"
        )
        row["Wait"] = format_minutes(train["wait_minutes"])
        row["Journey"] = format_minutes(train["journey_minutes"])

        rows.append(row)

    return rows


def show_ladies_specials(ladies_specials):
    """
    Show Ladies Special trains in their own table.

    They are kept out of the ranking above because they can only be
    used by women commuters - and they are not mixed into the
    "Other suitable options" ranks, which would make a Ladies
    Special look like the 5th-best option for everyone.
    """

    if not ladies_specials:
        return

    st.markdown("## 🚺 Ladies Special trains")

    st.caption(
        "Reserved for women commuters, so these are not part of "
        "the ranking above."
    )

    st.dataframe(
        build_train_rows(ladies_specials[:MAX_ALTERNATIVES_SHOWN]),
        use_container_width=True,
        hide_index=True,
    )


def show_footer():
    """
    Project scope note shown at the bottom of every result page.
    """

    st.markdown(
        """
        <div class="disclaimer">
            <strong>Project scope:</strong>
            This application uses scheduled Mumbai suburban railway
            data stored in MySQL. It is an academic MVP and does not
            provide live train tracking, real-time delays,
            cancellations, or dynamic platform changes.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SEARCH STATE
# ============================================================
#
# Streamlit reruns this entire script top to bottom on every
# widget interaction, and st.button() only reports True on the one
# rerun where it was just clicked - it reports False on every other
# rerun, including one triggered by an unrelated widget like the
# "Show route" checkbox further down this page. Without saving a
# completed search in st.session_state, touching that checkbox (or
# any other widget) after a search would silently throw the user
# back to the landing screen and discard the results on screen.
#
# For the same reason, everything the results page needs (including
# the notices about Sundays/holidays and Ladies Specials) is saved
# and shown from the results section below - not from inside the
# "if search_button:" block, where it would vanish on the next rerun.

# A search saved by an older version of this file is missing some of
# the keys used below. Drop it instead of crashing on it.
if "search_result" in st.session_state:

    if "service_date" not in st.session_state["search_result"]:
        st.session_state.pop("search_result")


if search_button:

    if source_name is None or destination_name is None:

        st.warning(
            "Please select both a source and destination station."
        )
        st.session_state.pop("search_result", None)
        st.stop()

    if source_name == destination_name:

        st.warning(
            "Source and destination cannot be the same station."
        )
        st.session_state.pop("search_result", None)
        st.stop()

    source_code = station_map[source_name]
    destination_code = station_map[destination_name]

    # Convert UI preference to recommendation.py format.
    preference_map = {
        "Earliest arrival": "earliest_arrival",
        "Shortest journey": "shortest_journey",
        "Least waiting time": "least_wait",
    }

    preference = preference_map[preference_label]

    # Convert "Any" into None because that means
    # no train type restriction in the SQL query.
    if train_type_label == "Any":
        train_type = None
    else:
        train_type = train_type_label

    # --------------------------------------------------------
    # QUERY DATABASE
    # --------------------------------------------------------

    connection = None

    try:

        connection = get_connection()

        train_options, service_date, showing_next_day = search_trains(
            connection=connection,
            source_code=source_code,
            destination_code=destination_code,
            current_time=current_time,
            travel_date=travel_date,
            train_type=train_type,
        )

        # Station line information (Western / Central).
        source_lines = get_lines_for_station(
            connection,
            source_code,
        )

        destination_lines = get_lines_for_station(
            connection,
            destination_code,
        )

    except Exception as error:

        st.error(
            f"Something went wrong while searching the database: "
            f"{error}"
        )
        st.session_state.pop("search_result", None)
        st.stop()

    finally:

        if connection is not None and connection.is_connected():
            connection.close()

    if not train_options:

        st.warning(
            f"No suitable scheduled train was found from "
            f"{source_name} to {destination_name}."
        )

        st.info(
            "Try a different station pair, or allow both "
            "Fast and Slow trains."
        )

        st.session_state.pop("search_result", None)
        st.stop()

    # --------------------------------------------------------
    # RECOMMENDATION ENGINE
    # --------------------------------------------------------
    #
    # service_date is the date the trains will actually run on:
    # the travel date, or the day after it when the search moved on
    # to tomorrow's first trains. The "Not on Sunday" rule is
    # checked against that date.

    result = recommend_trains(
        trains=train_options,
        current_time=current_time,
        preference=preference,
        current_date=service_date,
        next_day=showing_next_day
    )

    if result is None:

        st.warning(
            "The database returned train records, but none of "
            "them could be used (invalid timetable data, or they "
            "do not run on the selected date)."
        )
        st.session_state.pop("search_result", None)
        st.stop()

    summary = create_summary(result)

    source_line_names = [
        item["line_name"]
        for item in source_lines
    ]

    destination_line_names = [
        item["line_name"]
        for item in destination_lines
    ]

    # Save everything this page needs to render, so any later
    # rerun that isn't the search button itself (the route
    # checkbox below, for instance) can redraw this same result
    # instead of losing it.
    st.session_state["search_result"] = {
        "source_name": source_name,
        "destination_name": destination_name,
        "source_code": source_code,
        "destination_code": destination_code,
        "search_time": current_time,
        "service_date": service_date,
        "showing_next_day": showing_next_day,
        "result": result,
        "summary": summary,
        "source_line_names": source_line_names,
        "destination_line_names": destination_line_names,
    }


# ============================================================
# DEFAULT LANDING SCREEN
# ============================================================

if "search_result" not in st.session_state:

    st.info(
        "Select your source station, destination, current time "
        "and preference from the sidebar."
    )

    st.markdown("### How it works")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 1. Choose journey")
        st.write(
            "Select where you are and where you want to go."
        )

    with col2:
        st.markdown("#### 2. Query the database")
        st.write(
            "The application finds scheduled trains serving "
            "both stations in the correct route order."
        )

    with col3:
        st.markdown("#### 3. Get a recommendation")
        st.write(
            "Python ranks the available options according "
            "to your selected preference."
        )

    st.stop()


# ============================================================
# READ SAVED SEARCH RESULT
# ============================================================

search_data = st.session_state["search_result"]

source_name = search_data["source_name"]
destination_name = search_data["destination_name"]
source_code = search_data["source_code"]
destination_code = search_data["destination_code"]
service_date = search_data["service_date"]
result = search_data["result"]
summary = search_data["summary"]
source_line_names = search_data["source_line_names"]
destination_line_names = search_data["destination_line_names"]


# ============================================================
# JOURNEY HEADER
# ============================================================

st.markdown("## Journey")

journey_col1, journey_col2, journey_col3 = st.columns(
    [2, 1, 2]
)

with journey_col1:
    st.metric(
        "From",
        source_name,
    )

with journey_col2:
    st.markdown(
        "<div style='text-align:center; font-size:1.8rem;'>→</div>",
        unsafe_allow_html=True,
    )

with journey_col3:
    st.metric(
        "To",
        destination_name,
    )

# Showing the timetable date makes it obvious which day the
# Sunday/holiday rule was applied for.
st.caption(
    f"Timetable date: {service_date.strftime('%A, %d %b %Y')}"
)

if search_data["showing_next_day"]:
    st.info(
        f"No more trains are left on this route after "
        f"{format_time(search_data['search_time'])} - showing "
        f"the first scheduled trains for "
        f"{service_date.strftime('%A, %d %b %Y')} instead."
    )


# ============================================================
# STATION LINE INFORMATION
# ============================================================

line_col1,_, line_col2 = st.columns([2, 1, 2])

with line_col1:

    if source_line_names:
        st.caption(
            f"Source line(s): {', '.join(source_line_names)}"
        )

with line_col2:

    if destination_line_names:
        st.caption(
            f"Destination line(s): "
            f"{', '.join(destination_line_names)}"
        )


# ============================================================
# SPECIAL TRAIN NOTICES
# ============================================================

recommended = result["recommended"]
ladies_specials = result["ladies_specials"]

day_description = describe_non_operating_day(service_date)

if day_description:
    st.warning(
        f"ℹ️ {service_date.strftime('%A, %d %b %Y')} is "
        f"{day_description}, so trains marked \"Not on Sunday\" "
        f"are excluded from these results."
    )

if ladies_specials and recommended is not None:
    st.info(
        "ℹ️ Ladies Special trains are also available on this "
        "route. They are listed separately below and are not "
        "selected as the main recommendation."
    )


# ============================================================
# ONLY LADIES SPECIAL TRAINS RUNNING
# ============================================================

if recommended is None:

    st.warning(
        "Only Ladies Special trains are available for this "
        "search. They can only be used by women commuters."
    )

    show_ladies_specials(ladies_specials)
    show_footer()
    st.stop()


# ============================================================
# RECOMMENDED TRAIN
# ============================================================

st.markdown("## ⭐ Recommended train")


st.markdown(
    f"### 🚆 {recommended['train_name']}"
)

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

with info_col1:
    st.markdown(
        '<div class="small-label">Train type</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="big-value">{recommended["train_type"] or "—"}</div>',
        unsafe_allow_html=True,
    )

with info_col2:
    st.markdown(
        '<div class="small-label">At source</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="big-value">'
        f'{format_time(recommended["source_time"])}'
        f'</div>',
        unsafe_allow_html=True,
    )

with info_col3:
    st.markdown(
        '<div class="small-label">Platform</div>',
        unsafe_allow_html=True,
    )

    platform = recommended["source_platform"]

    if platform is None:
        platform_text = "Not specified"
    else:
        platform_text = str(platform)

    st.markdown(
        f'<div class="big-value">{platform_text}</div>',
        unsafe_allow_html=True,
    )

with info_col4:
    st.markdown(
        '<div class="small-label">Destination</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="big-value">'
        f'{format_time(recommended["destination_time"])}'
        f'</div>',
        unsafe_allow_html=True,
    )


st.markdown("---")

metric_col1, metric_col2 = st.columns(2)

with metric_col1:
    st.metric(
        "Waiting time",
        format_minutes(recommended["wait_minutes"]),
    )

with metric_col2:
    st.metric(
        "Scheduled journey",
        format_minutes(recommended["journey_minutes"]),
    )

st.markdown(
    f"**Why this train?** {summary['reason']}"
)



# ============================================================
# ALTERNATIVE TRAINS
# ============================================================

alternatives = result["alternatives"][:MAX_ALTERNATIVES_SHOWN]

if alternatives:

    st.markdown("## Other suitable options")

    st.dataframe(
        build_train_rows(alternatives, first_rank=2),
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No other suitable trains were found in the current "
        "search result."
    )


# ============================================================
# LADIES SPECIAL TRAINS
# ============================================================

show_ladies_specials(ladies_specials)


# ============================================================
# ROUTE DETAILS
# ============================================================

st.markdown("## Route details")

show_route = st.checkbox(
    "Show stops between source and destination"
)

if show_route:

    connection = None

    try:

        connection = get_connection()

        route_stops = get_stops_between(
            connection=connection,
            train_id=recommended["train_id"],
            source_code=source_code,
            destination_code=destination_code,
        )

    except Exception as error:

        st.error(
            f"Could not load route details: {error}"
        )

        route_stops = []

    finally:

        if connection is not None and connection.is_connected():
            connection.close()

    if route_stops:

        route_rows = []

        for stop in route_stops:

            route_rows.append(
                {
                    "Stop": stop["stop_sequence"],
                    "Station": stop["station_name"],
                    "Code": stop["station_code"],
                    "Arrival": format_time(stop["arrival_time"]),
                    "Platform": (
                        str(stop["platform"])
                        if stop["platform"] is not None
                        else "—"
                    ),
                }
            )

        st.dataframe(
            route_rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Route information is not available for this journey."
        )


# ============================================================
# FOOTER / SCOPE
# ============================================================

show_footer()
