"""
database.py

Handles the connection between the Python application
and the MySQL database.

Database used:
    mumbai_local
"""

import streamlit as st
import mysql.connector
from mysql.connector import Error


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_CONFIG = {
    "host": st.secrets["mysql"]["host"],
    "port": st.secrets["mysql"]["port"],
    "database": st.secrets["mysql"]["database"],
    "user": st.secrets["mysql"]["username"],
    "password": st.secrets["mysql"]["password"],
}


# ============================================================
# CREATE DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create and return a connection to the MySQL database.

    Returns:
        MySQL connection object

    Raises:
        RuntimeError if the connection cannot be established.
    """

    try:
        connection = mysql.connector.connect(**DB_CONFIG)

        if connection.is_connected():
            return connection

        raise RuntimeError("Could not establish MySQL connection.")

    except Error as error:
        raise RuntimeError(
            f"Failed to connect to MySQL: {error}"
        ) from error


# ============================================================
# TEST DATABASE CONNECTION
# ============================================================

def test_connection():
    """
    Test whether the application can successfully connect
    to the Mumbai Local database.

    Returns:
        True if successful
        False otherwise
    """

    connection = None

    try:
        connection = get_connection()

        print("Successfully connected to MySQL.")
        print("Database: mumbai_local")

        return True

    except RuntimeError as error:
        print(error)
        return False

    finally:
        if connection is not None and connection.is_connected():
            connection.close()
            print("MySQL connection closed.")


# ============================================================
# SIMPLE DATABASE INFORMATION
# ============================================================

def get_database_info():
    """
    Return basic information about the current database.

    This is useful for checking that Python is connected
    to the database we actually intend to use.
    """

    connection = None
    cursor = None

    try:
        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT DATABASE() AS database_name;")

        result = cursor.fetchone()

        return result

    except Error as error:
        raise RuntimeError(
            f"Could not retrieve database information: {error}"
        ) from error

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

def get_table_counts():
    """
    Return the number of records in the main MVP tables.

    Useful for checking whether Python is connected to the
    expected database and whether the database contains data.
    """

    connection = None
    cursor = None

    try:
        connection = get_connection()

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                (SELECT COUNT(*) FROM stations) AS station_count,
                (SELECT COUNT(*) FROM line) AS line_count,
                (SELECT COUNT(*) FROM station_lines) AS station_line_count,
                (SELECT COUNT(*) FROM trains) AS train_count,
                (SELECT COUNT(*) FROM train_stops) AS train_stop_count;
        """

        cursor.execute(query)

        return cursor.fetchone()

    except Error as error:
        raise RuntimeError(
            f"Could not perform database health check: {error}"
        ) from error

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ============================================================
# RUN DIRECTLY FOR TESTING
# ============================================================

if __name__ == "__main__":

    print("\n--- MYSQL CONNECTION TEST ---")

    if test_connection():

        print("\n--- DATABASE INFORMATION ---")

        try:
            database_info = get_database_info()
            print(
                "Connected database:",
                database_info["database_name"]
            )

        except RuntimeError as error:
            print(error)

        print("\n--- DATABASE HEALTH CHECK ---")

        try:
            counts = get_table_counts()

            for table, count in counts.items():
                print(f"{table}: {count}")

        except RuntimeError as error:
            print(error)