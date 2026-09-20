"""
queries.py

Handles all communication between the Python application
and the MySQL database.

Database:
    mumbai_local

Current MVP scope:
    - Stations
    - Railway lines
    - Trains
    - Train routes / stops
    - Scheduled arrival times
    - Platforms

Not included in the current MVP:
    - Live train location
    - Real-time delays
    - Cancellations
    - Dynamic platform changes
    - Full day-specific timetables (the one exception: trains marked
      "Not on Sunday" in their name can be excluded, see
      find_train_options)

Design:
    SQL -> retrieve and filter data
    recommendation.py -> analyse and rank trains
    app.py -> user interface
"""


# ============================================================
# STATIONS
# ============================================================

def get_all_stations(connection):
    """
    Return all stations available in the database.
    Used for source/destination selection.
    """

    query = """
        SELECT
            station_name,
            station_code
        FROM stations
        ORDER BY station_name;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()


def get_station_by_code(connection, station_code):
    """
    Return details of one station using its station code.
    """

    query = """
        SELECT
            station_name,
            station_code
        FROM stations
        WHERE station_code = %s;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (station_code,))
        return cursor.fetchone()
    finally:
        cursor.close()


def search_stations(connection, search_text):
    """
    Search stations using partial station names.

    Example:
        'dad' -> Dadar
        'and' -> Andheri
    """

    query = """
        SELECT
            station_name,
            station_code
        FROM stations
        WHERE station_name LIKE %s
        ORDER BY station_name;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (f"%{search_text}%",))
        return cursor.fetchall()
    finally:
        cursor.close()


# ============================================================
# LINES
# ============================================================

def get_all_lines(connection):
    """
    Return all railway lines stored in the database.
    """

    query = """
        SELECT
            line_name
        FROM line
        ORDER BY line_name;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()


def get_lines_for_station(connection, station_code):
    """
    Return all railway lines serving a particular station.

    Example:
        DDR -> Western, Central
    """

    query = """
        SELECT
            l.line_name
        FROM station_lines sl
        JOIN line l
            ON sl.line_name = l.line_name
        WHERE sl.station_code = %s
        ORDER BY l.line_name;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (station_code,))
        return cursor.fetchall()
    finally:
        cursor.close()


def get_stations_on_line(connection, line_name):
    """
    Return all stations associated with a particular line.

    Note:
        This returns stations alphabetically because the current
        station_lines table does not store route sequence for a line.
    """

    query = """
        SELECT
            s.station_name,
            s.station_code
        FROM station_lines sl
        JOIN stations s
            ON sl.station_code = s.station_code
        WHERE sl.line_name = %s
        ORDER BY s.station_name;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (line_name,))
        return cursor.fetchall()
    finally:
        cursor.close()


# ============================================================
# TRAINS
# ============================================================

def get_all_trains(connection):
    """
    Return all trains stored in the database.
    """

    query = """
        SELECT
            train_id,
            train_name,
            train_type,
            train_direction
        FROM trains
        ORDER BY train_id;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()


def get_train_by_id(connection, train_id):
    """
    Return details of one train.
    """

    query = """
        SELECT
            train_id,
            train_name,
            train_type,
            train_direction
        FROM trains
        WHERE train_id = %s;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (train_id,))
        return cursor.fetchone()
    finally:
        cursor.close()


def get_trains_by_type(connection, train_type):
    """
    Return trains of a specific type.

    Example:
        Fast
        Slow
    """

    query = """
        SELECT
            train_id,
            train_name,
            train_type,
            train_direction
        FROM trains
        WHERE train_type = %s
        ORDER BY train_id;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (train_type,))
        return cursor.fetchall()
    finally:
        cursor.close()


def get_trains_by_direction(connection, direction):
    """
    Return trains travelling towards a particular destination.

    Example:
        Borivali
        Virar
        Churchgate
    """

    query = """
        SELECT
            train_id,
            train_name,
            train_type,
            train_direction
        FROM trains
        WHERE train_direction = %s
        ORDER BY train_type, train_id;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (direction,))
        return cursor.fetchall()
    finally:
        cursor.close()


# ============================================================
# TRAIN ROUTES
# ============================================================

def get_train_route(connection, train_id):
    """
    Return the complete route of a train in stop order.

    stop_sequence is what tells us the order of stations.
    """

    query = """
        SELECT
            ts.stop_sequence,
            s.station_name,
            s.station_code,
            ts.arrival_time,
            ts.platform
        FROM train_stops ts
        JOIN stations s
            ON ts.station_code = s.station_code
        WHERE ts.train_id = %s
        ORDER BY ts.stop_sequence;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (train_id,))
        return cursor.fetchall()
    finally:
        cursor.close()


def get_train_stop_at_station(connection, train_id, station_code):
    """
    Return the timetable information of one train at one station.
    """

    query = """
        SELECT
            t.train_name,
            t.train_type,
            t.train_direction,
            s.station_name,
            s.station_code,
            ts.stop_sequence,
            ts.arrival_time,
            ts.platform
        FROM train_stops ts

        JOIN trains t
            ON ts.train_id = t.train_id

        JOIN stations s
            ON ts.station_code = s.station_code

        WHERE ts.train_id = %s
          AND ts.station_code = %s;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (train_id, station_code))
        return cursor.fetchone()
    finally:
        cursor.close()


# ============================================================
# STATION BOARD
# ============================================================

def get_trains_at_station(connection, station_code):
    """
    Return all trains scheduled to stop at a particular station.
    """

    query = """
        SELECT
            t.train_id,
            t.train_name,
            t.train_type,
            t.train_direction,
            ts.arrival_time,
            ts.platform,
            ts.stop_sequence
        FROM train_stops ts

        JOIN trains t
            ON ts.train_id = t.train_id

        WHERE ts.station_code = %s

        ORDER BY ts.arrival_time, t.train_id;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (station_code,))
        return cursor.fetchall()
    finally:
        cursor.close()


def get_upcoming_trains(connection, station_code, current_time, limit=5):
    """
    Return the next scheduled trains at a station.

    Current MVP assumption:
        arrival_time is treated as the effective boarding time.

    Midnight handling:
        arrival_time is a plain TIME value with no date attached.
        Late at night, after the last train of the day, nothing is
        left that is ">= current_time" even though service starts
        again a few hours later. In that case we fall back to the
        earliest trains of the day instead of returning nothing.

    Warning:
        This station board does NOT apply the "Not on Sunday" rule.
        The app does not use it - journey searches must go through
        find_train_options().
    """

    query = """
        SELECT
            t.train_id,
            t.train_name,
            t.train_type,
            t.train_direction,
            ts.arrival_time,
            ts.platform
        FROM train_stops ts

        JOIN trains t
            ON ts.train_id = t.train_id

        WHERE ts.station_code = %s
          AND ts.arrival_time >= %s

        ORDER BY ts.arrival_time, t.train_id

        LIMIT %s;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            query,
            (station_code, current_time, limit)
        )

        results = cursor.fetchall()

        # Nothing left today -> show the first trains of the day
        # instead of an empty result.
        if not results:
            fallback_query = """
                SELECT
                    t.train_id,
                    t.train_name,
                    t.train_type,
                    t.train_direction,
                    ts.arrival_time,
                    ts.platform
                FROM train_stops ts

                JOIN trains t
                    ON ts.train_id = t.train_id

                WHERE ts.station_code = %s

                ORDER BY ts.arrival_time, t.train_id

                LIMIT %s;
            """

            cursor.execute(fallback_query, (station_code, limit))
            results = cursor.fetchall()

        return results

    finally:
        cursor.close()


# ============================================================
# MAIN JOURNEY SEARCH
# ============================================================

# SQL pattern for trains marked "Not on Sunday ...".
# Matches: (Not on Sunday), (Not on Sundays & Holidays), (Not on Sun.)
#
# Keep this in step with is_not_on_sunday_or_holiday() in
# recommendation.py, which is the final check on every train.
NOT_ON_SUNDAY_PATTERN = "%not on sun%"


def find_train_options(
    connection,
    source_code,
    destination_code,
    current_time=None,
    train_type=None,
    direction=None,
    limit=5,
    exclude_not_on_sunday=False
):
    """
    Canonical journey-search query - the single source of truth
    for source -> destination train searches in this application.
    Nothing else in this file should be used for that purpose.

    Finds direct trains satisfying:

        - Source station
        - Destination station
        - Correct route direction
        - Current-time cutoff
        - Optional train type
        - Optional direction
        - Optional "Not on Sunday" exclusion
        - Result limit

    current_time:
        Only trains leaving the source at or after this time are
        returned. Pass None to get the whole day's trains, earliest
        first (used for tomorrow's first trains).

    exclude_not_on_sunday:
        True on Sundays and holidays. Trains whose name contains
        "Not on Sunday" are removed here, INSIDE the SQL, so the
        LIMIT is applied to trains that actually run. If they were
        removed later in Python, a crowded stretch of "Not on Sunday"
        trains could use up the whole LIMIT and leave nothing behind.

    limit:
        Maximum number of trains. Pass None for no limit.

    Midnight handling:
        arrival_time is a plain TIME value with no date attached.
        Late at night, after the last train on this route has
        already left, nothing is left that is ">= current_time".
        This function does NOT guess what happens next - the caller
        (app.py) decides to search again with current_time=None for
        TOMORROW, because only the caller knows tomorrow's date
        (and therefore whether tomorrow is a Sunday or holiday).

    Returns:
        train details
        source arrival time
        source platform
        destination arrival time
        stop sequences
    """

    query = """
        SELECT
            t.train_id,
            t.train_name,
            t.train_type,
            t.train_direction,

            source_stop.arrival_time AS source_time,
            source_stop.platform AS source_platform,

            destination_stop.arrival_time AS destination_time,

            source_stop.stop_sequence AS source_sequence,
            destination_stop.stop_sequence AS destination_sequence

        FROM trains t

        JOIN train_stops source_stop
            ON t.train_id = source_stop.train_id

        JOIN train_stops destination_stop
            ON t.train_id = destination_stop.train_id

        WHERE source_stop.station_code = %s
          AND destination_stop.station_code = %s

          AND source_stop.stop_sequence
              < destination_stop.stop_sequence
    """

    # The parameters must be added in the SAME order as the %s
    # placeholders appear in the query text.
    parameters = [source_code, destination_code]

    if current_time is not None:
        query += """
          AND source_stop.arrival_time >= %s
        """
        parameters.append(current_time)

    if train_type is not None:
        query += """
          AND t.train_type = %s
        """
        parameters.append(train_type)

    if direction is not None:
        query += """
          AND t.train_direction = %s
        """
        parameters.append(direction)

    if exclude_not_on_sunday:
        query += """
          AND LOWER(COALESCE(t.train_name, '')) NOT LIKE %s
        """
        parameters.append(NOT_ON_SUNDAY_PATTERN)

    query += """
        ORDER BY source_stop.arrival_time, t.train_id
    """

    if limit is not None:
        query += """
        LIMIT %s
        """
        parameters.append(limit)

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, tuple(parameters))
        return cursor.fetchall()

    finally:
        cursor.close()


# ============================================================
# PLATFORM
# ============================================================

def get_trains_on_platform(connection, station_code, platform):
    """
    Return trains scheduled on a particular platform.
    """

    query = """
        SELECT
            t.train_id,
            t.train_name,
            t.train_type,
            t.train_direction,
            ts.arrival_time,
            ts.platform
        FROM train_stops ts

        JOIN trains t
            ON ts.train_id = t.train_id

        WHERE ts.station_code = %s
          AND ts.platform = %s

        ORDER BY ts.arrival_time;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            query,
            (station_code, platform)
        )

        return cursor.fetchall()

    finally:
        cursor.close()


def get_platforms_at_station(connection, station_code):
    """
    Return the distinct platforms present in the timetable
    for a station.
    """

    query = """
        SELECT DISTINCT
            platform
        FROM train_stops
        WHERE station_code = %s
          AND platform IS NOT NULL
        ORDER BY platform;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, (station_code,))
        return cursor.fetchall()

    finally:
        cursor.close()


# ============================================================
# INTERMEDIATE STOPS
# ============================================================

def get_stops_between(
    connection,
    train_id,
    source_code,
    destination_code
):
    """
    Return all stations between source and destination
    for a selected train.

    This can later be used to display:
        Dadar → Bandra → Khar → Santacruz → ... → Borivali
    """

    query = """
        SELECT
            s.station_name,
            s.station_code,
            ts.stop_sequence,
            ts.arrival_time,
            ts.platform

        FROM train_stops ts

        JOIN stations s
            ON ts.station_code = s.station_code

        JOIN train_stops source_stop
            ON source_stop.train_id = ts.train_id
           AND source_stop.station_code = %s

        JOIN train_stops destination_stop
            ON destination_stop.train_id = ts.train_id
           AND destination_stop.station_code = %s

        WHERE ts.train_id = %s

          AND ts.stop_sequence
              BETWEEN source_stop.stop_sequence
              AND destination_stop.stop_sequence

        ORDER BY ts.stop_sequence;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            query,
            (
                source_code,
                destination_code,
                train_id
            )
        )

        return cursor.fetchall()

    finally:
        cursor.close()


# ============================================================
# DATABASE VALIDATION
# ============================================================

def database_health_check(connection):
    """
    Return basic counts from all important MVP tables.

    Useful for checking whether the Python application
    is connected to the expected database.
    """

    query = """
        SELECT

            (SELECT COUNT(*)
             FROM stations) AS station_count,

            (SELECT COUNT(*)
             FROM line) AS line_count,

            (SELECT COUNT(*)
             FROM trains) AS train_count,

            (SELECT COUNT(*)
             FROM train_stops) AS train_stop_count;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchone()

    finally:
        cursor.close()


def find_invalid_train_stops(connection):
    """
    Find train_stop records whose train_id does not
    correspond to a train.

    With proper foreign keys this should normally return
    zero rows.
    """

    query = """
        SELECT
            ts.*
        FROM train_stops ts

        LEFT JOIN trains t
            ON ts.train_id = t.train_id

        WHERE t.train_id IS NULL;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()

    finally:
        cursor.close()


def find_invalid_station_stops(connection):
    """
    Find train_stop records whose station_code does not
    correspond to a station.
    """

    query = """
        SELECT
            ts.*
        FROM train_stops ts

        LEFT JOIN stations s
            ON ts.station_code = s.station_code

        WHERE s.station_code IS NULL;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()

    finally:
        cursor.close()


def find_time_sequence_violations(connection):
    """
    Find train_stop records where arrival_time does not increase
    as stop_sequence increases, for the same train.

    find_train_options() relies on the assumption that a later
    stop_sequence always means a later arrival_time. This check
    catches a data-entry mistake that breaks that assumption.

    Assumes stop_sequence values are consecutive integers
    (1, 2, 3, ...) per train, with no gaps.
    """

    query = """
        SELECT
            ts1.train_id,
            ts1.stop_sequence AS first_sequence,
            ts1.arrival_time AS first_time,
            ts2.stop_sequence AS second_sequence,
            ts2.arrival_time AS second_time

        FROM train_stops ts1

        JOIN train_stops ts2
            ON ts1.train_id = ts2.train_id
           AND ts2.stop_sequence = ts1.stop_sequence + 1

        WHERE ts2.arrival_time <= ts1.arrival_time;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()

    finally:
        cursor.close()


def find_duplicate_stop_sequences(connection):
    """
    Check whether the same train has duplicate stop_sequence values.

    Normally this should return zero rows because your
    composite primary key prevents such duplicates.
    """

    query = """
        SELECT
            train_id,
            stop_sequence,
            COUNT(*) AS occurrences

        FROM train_stops

        GROUP BY
            train_id,
            stop_sequence

        HAVING COUNT(*) > 1;
    """

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query)
        return cursor.fetchall()

    finally:
        cursor.close()