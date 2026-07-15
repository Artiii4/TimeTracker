import sqlite3
import json
import os
import sys
from datetime import datetime


DB_FILENAME = 'timetracker.db'
SETTINGS_FILENAME = "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "autostart": False,
    "ignore_list": ["explorer.exe", "taskmgr.exe", "LockApp.exe", "SearchHost.exe"],
    "limits": {},
    "db_path": "",
    "idle_threshold_seconds": 5,
    "poll_interval_seconds": 5
}


def get_app_data_dir():
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base = os.path.expanduser('~')
    app_dir = os.path.join(base, 'TimeTracker')
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return app_dir


def get_settings_path():
    return os.path.join(get_app_data_dir(), SETTINGS_FILENAME)


def load_settings():
    path = get_settings_path()

    if not os.path.exists(path):
        s = dict(DEFAULT_SETTINGS)
        s['db_path'] = os.path.join(get_app_data_dir(), DB_FILENAME)
        save_settings(s)
        return s

    try:
        f = open(path, 'r', encoding='utf-8')
        settings = json.load(f)
        f.close()
    except (json.JSONDecodeError, OSError):
        settings = dict(DEFAULT_SETTINGS)
        settings['db_path'] = os.path.join(get_app_data_dir(), DB_FILENAME)

    for key in DEFAULT_SETTINGS:
        if key not in settings:
            settings[key] = DEFAULT_SETTINGS[key]

    if not settings.get('db_path'):
        settings['db_path'] = os.path.join(get_app_data_dir(), DB_FILENAME)

    save_settings(settings)
    return settings


def save_settings(settings):
    path = get_settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)


def get_connection(db_path):
    return sqlite3.connect(db_path, check_same_thread=False)


def init_db(db_path):
    conn = get_connection(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT NOT NULL,
        process_name TEXT NOT NULL,
        window_title TEXT,
        start_time TEXT NOT NULL,
        end_time TEXT,
        duration_seconds REAL NOT NULL DEFAULT 0
    )''')
    conn.commit()
    return conn


def start_session(conn, app_name, process_name, window_title, start_time):
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (app_name, process_name, window_title, start_time, end_time, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
        (app_name, process_name, window_title, start_time.isoformat(), None, 0)
    )
    conn.commit()
    return c.lastrowid


def end_session(conn, session_id, end_time, duration_seconds):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET end_time = ?, duration_seconds = ? WHERE id = ?",
        (end_time.isoformat(), duration_seconds, session_id)
    )
    conn.commit()


def get_sessions_for_date(conn, date_obj):
    start = datetime.combine(date_obj, datetime.min.time())
    end = datetime.combine(date_obj, datetime.max.time())
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, app_name, process_name, window_title, start_time, end_time, duration_seconds "
        "FROM sessions WHERE start_time >= ? AND start_time <= ? ORDER BY start_time ASC",
        (start.isoformat(), end.isoformat())
    )
    rows = cursor.fetchall()
    result = []
    for row in rows:
        item = {
            'id': row[0],
            'app_name': row[1],
            'process_name': row[2],
            'window_title': row[3],
            'start_time': row[4],
            'end_time': row[5],
            'duration_seconds': row[6]
        }
        result.append(item)
    return result


def get_total_seconds_today(conn, date_obj):
    start = datetime.combine(date_obj, datetime.min.time())
    end = datetime.combine(date_obj, datetime.max.time())
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(duration_seconds) FROM sessions WHERE start_time >= ? AND start_time <= ?",
        (start.isoformat(), end.isoformat())
    )
    row = cursor.fetchone()
    total = row[0]
    if total is None:
        total = 0
    return total
