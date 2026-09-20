# Mumbai Local Assistant

A Streamlit-based Mumbai suburban railway assistant that uses a MySQL timetable database to find and rank suitable local trains for a selected journey.

The project is currently an **MVP focused on the Western Railway (WR) line**. It is designed as a small but properly structured software project: MySQL stores the railway data, Python handles database access and recommendation logic, and Streamlit provides the user interface.

---

## 1. Problem Statement

For a passenger who is unfamiliar with the Mumbai suburban railway system, simply knowing the timetable is not always enough. The useful question is often:

> **Which scheduled train should I take from my station to my destination, given my current time and preference?**

Mumbai Local Assistant answers that question using structured timetable data instead of requiring the user to manually compare multiple trains.

---

## 2. What the MVP Does

The current MVP allows a user to:

- Select a source station.
- Select a destination station.
- Use the current time in Indian Standard Time (IST), with manual adjustment available.
- Choose what matters most:
  - Earliest arrival
  - Shortest journey
  - Least waiting time
- Filter between:
  - Any
  - Fast
  - Slow
- See a primary train recommendation.
- See other suitable scheduled trains.
- View:
  - Train name
  - Train type
  - Source arrival time
  - Source platform, where available
  - Destination arrival time
  - Waiting time
  - Scheduled journey duration
- Expand route details to see intermediate stops.

The application is intended to be useful even when the commuter does not already know which train service to select.

---

## 3. Current MVP Data Scope

The present database is deliberately limited so that the project can remain manageable and verifiable as a first implementation.

### Railway coverage

- **Western Railway (WR) line only**
- The station data currently covers the Western line subset used by the present timetable data.

### Timetable coverage

- Only trains **starting their journey before 6:00 AM** have currently been entered.
- The currently entered trains complete their journeys by approximately **8:30 AM at the latest**.
- The database therefore does **not** represent the complete all-day Western Railway timetable yet.

### Current data model

The MVP stores:

- Stations
- Railway lines
- Station-to-line relationships
- Trains
- Ordered train stops
- Scheduled arrival times
- Platform information where available

The timetable is treated as scheduled data rather than live operational data.

---

## 4. What the MVP Does Not Provide

The current version does **not** provide:

- Live train location
- Real-time delays
- Cancellation detection
- Dynamic platform changes
- Real-time operational status
- A complete full-day Western Railway timetable
- Central Railway / Harbour Railway / other suburban line coverage

These are outside the current MVP boundary and are planned as future extensions.

---

## 5. Application Architecture

The project follows a simple layered structure:

```text
User
  ↓
app.py
  ↓
queries.py
  ↓
MySQL database
  ↓
recommendation.py
  ↓
app.py
  ↓
Recommendation shown to user
```

More specifically:

```text
                 ┌─────────────────┐
                 │   Streamlit UI  │
                 │     app.py      │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   queries.py    │
                 │  SQL / DB reads │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │      MySQL      │
                 │  mumbai_local   │
                 └─────────────────┘
                          ▲
                          │
                 ┌────────┴────────┐
                 │recommendation.py│
                 │ ranking/logic   │
                 └─────────────────┘
```

### Separation of responsibilities

**`app.py`**

Handles the user interface and application flow.

**`database.py`**

Handles MySQL connection setup and database health checks.

**`queries.py`**

Contains SQL queries and database access functions. It is responsible for retrieving structured data from MySQL.

**`recommendation.py`**

Contains the application's decision-making logic, including waiting-time calculation, journey-duration calculation, ranking, and recommendation explanations.

This separation keeps SQL, business logic, and UI concerns from being mixed together.

---

## 6. Database Structure

The database is named:

```text
mumbai_local
```

### Main tables

```text
stations
-----------
station_code  (PK)
station_name


line
-----------
line_name     (PK)


station_lines
-----------
station_code  (PK/FK)
line_name     (PK/FK)


trains
-----------
train_id          (PK)
train_name
train_type
train_direction


train_stops
-----------
train_id          (PK/FK)
stop_sequence     (PK)
station_code      (FK)
arrival_time
platform
```

### Why `train_stops` is important

A train cannot be represented only as:

```text
Churchgate → Borivali
```

The application needs the ordered station-level timetable:

```text
Churchgate
↓
Marine Lines
↓
Charni Road
↓
...
↓
Borivali
```

The `stop_sequence` column provides the order of stations for each train and allows the application to verify that a destination occurs after the selected source station.

---

## 7. Recommendation Logic

The application first retrieves candidate trains that:

1. Stop at the selected source station.
2. Stop at the selected destination station.
3. Reach the destination after the source in the train's route.
4. Match the selected train-type filter, if one is specified.
5. Are scheduled according to the current timetable data.

The recommendation layer then calculates:

### Waiting time

```text
train arrival at source - current time
```

### Journey duration

```text
destination arrival - source arrival
```

The logic also accounts for midnight rollover so that times crossing midnight are not incorrectly treated as negative durations.

### Ranking preferences

**Earliest arrival**

Ranks trains based on the total time until reaching the destination, while using journey duration and train type as tie-breakers.

**Shortest journey**

Prioritizes the smallest scheduled journey duration.

**Least waiting time**

Prioritizes the train requiring the least waiting from the current time.

The calculations are intentionally kept simple and explainable so the behaviour can be understood and verified without a complex machine-learning model.

---

## 8. Special Train Services

Train names can contain service-specific information such as:

```text
(15CAR)
(AC)
(Ladies Spl.)
(Not on Sunday & Holiday)
```

These labels are stored as part of the train information so the timetable can distinguish different services.

Holiday/day-specific operating rules and more comprehensive special-service handling can be expanded as the timetable coverage grows.

---

## 9. Time and Time Zone

Mumbai railway timings are handled using **Indian Standard Time (Asia/Kolkata)**.

The application uses Python's `zoneinfo` module so that the default current time is not dependent on the machine's local time zone.

This matters when the application is later hosted on a server whose system time zone is different from India.

---

## 10. Project Structure

The core MVP currently follows:

```text
mumbai_local/
│
├── app.py
├── database.py
├── queries.py
├── recommendation.py
├── requirements.txt
├── README.md
│

---

## 11. Requirements

Recommended environment:

- Python 3.10 or newer
- MySQL Server
- A MySQL database named `mumbai_local`
- Internet access only when installing Python packages

Python dependencies are listed in `requirements.txt`.

Install them with:

```bash
pip install -r requirements.txt
```

---

## 12. MySQL Setup

Create the database in MySQL:

```sql
CREATE DATABASE mumbai_local;
```

Then create/populate the project's tables according to the schema used by the application.

The application expects the following database name:

```text
mumbai_local
```

---

## 13. Database Configuration

`database.py` contains the MySQL connection configuration.

Example:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YOUR_MYSQL_PASSWORD",
    "database": "mumbai_local"
}
```

Replace the password with your local MySQL password.

For a larger or publicly deployed application, credentials should be moved to environment variables or Streamlit secrets rather than committed directly to source control.

---

## 14. Running the Application

From the project directory:

```bash
streamlit run app.py
```

Streamlit will start the application locally and provide a browser URL.

---

## 15. Typical User Flow

```text
1. Select source station
           ↓
2. Select destination station
           ↓
3. Confirm / adjust current time
           ↓
4. Select journey preference
           ↓
5. Select train type
           ↓
6. Find best train
           ↓
7. View recommendation
           ↓
8. Compare alternatives
           ↓
9. Optionally inspect intermediate stops
```

---

## 16. Data Quality and Validation

Because timetable data directly affects the recommendation engine, incorrect database rows can produce incorrect recommendations.

Important integrity checks include:

- Every `train_stops.train_id` should refer to an existing train.
- Every `train_stops.station_code` should refer to an existing station.
- `stop_sequence` should increase along a train's route.
- Arrival times should normally progress with the stop sequence.
- A selected destination must occur after the selected source.
- Train IDs should be unique.
- Timetable times should use a consistent `TIME` representation.
- Platform values should not be invented when the source timetable does not provide reliable information.

The project therefore treats database correctness as a core part of the application rather than merely a data-entry task.

---

## 17. Current Limitations

The biggest limitation of the MVP is **timetable coverage**, not the recommendation logic.

At present, the database is intentionally an early-morning Western Railway subset. This keeps the project small enough to validate end-to-end before expanding the dataset.

The current version also relies on scheduled timetable information. It cannot know whether a train is actually running late, cancelled, short-terminated, or using a temporarily changed platform.

---

## 18. Future Scope

### Phase 1 — Complete Western Railway timetable

Expand the current early-morning dataset to the **full-day Western Railway timetable**, including later services and the remaining scheduled trains.

### Phase 2 — Operational information

Add:

- Delay information
- Cancellations
- Better day-specific timetable handling
- Holiday-aware service availability
- More robust special-train rules

### Phase 3 — Other Mumbai suburban lines

Expand coverage to:

- Central Railway
- Harbour Line
- Other relevant suburban services

This will require additional line/station relationships and careful handling of interchange stations.

### Phase 4 — More intelligent journey assistance

Potential extensions include:

- Better route comparison
- Interchange journeys
- More detailed platform guidance
- Historical delay analysis
- User-specific preferences
- Live operational data

---

## 19. Design Philosophy

The project intentionally follows a simple principle:

> **Reliable data + clear database design + explainable logic before advanced features.**

The goal of the MVP is not to imitate the full functionality of a production railway application. It is to demonstrate a complete software pipeline:

```text
Real-world problem
        ↓
Database design
        ↓
Data collection
        ↓
SQL queries
        ↓
Python logic
        ↓
User interface
        ↓
Useful recommendation
```

AI tools were used selectively during development for debugging, code review, and documentation support.

---

## 20. Project Status

**Current status:** MVP / active development

**Current coverage:** Western Railway — early-morning timetable subset

**Primary technologies:**

- Python
- Streamlit
- MySQL
- SQL
- `mysql-connector-python`
- Python `zoneinfo`

The project is intentionally being built incrementally: first a small, testable timetable dataset; then broader coverage and operational features.
