import threading
import time
import ctypes
import sys
from datetime import datetime

import psutil

import database


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def get_idle_duration_seconds():
    if sys.platform != 'win32':
        return 0
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ok = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    if not ok:
        return 0
    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    return millis / 1000.0


class Tracker:

    def __init__(self, settings, on_state_change=None, on_limit_exceeded=None):
        self.settings = settings
        self.on_state_change = on_state_change
        self.on_limit_exceeded = on_limit_exceeded
        self.paused = False
        self._stop_event = threading.Event()
        self.conn = database.init_db(settings['db_path'])

        self.current_session_id = None
        self.current_process_name = None
        self.current_app_name = None
        self.current_window_title = None
        self.session_start_time = None
        self.continuous_seconds_current_app = 0
        self.notified_for_current_session = False
        self.is_idle = False

        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self._stop_event.set()
        self._close_current_session()
        try:
            self.conn.close()
        except Exception:
            pass

    def set_paused(self, value):
        self.paused = value
        if value:
            self._close_current_session()

    def _get_active_window_info(self):
        if sys.platform != 'win32':
            return None, None, None

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd == 0:
            return None, None, None

        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        if pid.value == 0:
            return None, None, None

        try:
            proc = psutil.Process(pid.value)
            process_name = proc.name()
        except Exception:
            return None, None, None

        if not process_name:
            return None, None, None

        app_name = process_name
        if app_name.lower().endswith('.exe'):
            app_name = app_name[:-4]

        return app_name, process_name, title

    def _close_current_session(self):
        if self.current_session_id is None:
            return
        now = datetime.now()
        duration = (now - self.session_start_time).total_seconds()
        database.end_session(self.conn, self.current_session_id, now, duration)
        self.current_session_id = None
        self.current_process_name = None
        self.current_app_name = None
        self.current_window_title = None
        self.session_start_time = None
        self.continuous_seconds_current_app = 0
        self.notified_for_current_session = False

    def _run(self):
        poll_interval = self.settings.get('poll_interval_seconds', 5)
        idle_threshold = self.settings.get('idle_threshold_seconds', 5)

        while not self._stop_event.is_set():
            if self.paused:
                time.sleep(poll_interval)
                continue

            idle_seconds = get_idle_duration_seconds()
            if idle_seconds > idle_threshold:
                self.is_idle = True
            else:
                self.is_idle = False

            app_name, process_name, title = self._get_active_window_info()

            ignore_list = self.settings.get('ignore_list', [])
            ignored = False
            if process_name and process_name in ignore_list:
                ignored = True

            if self.is_idle or app_name is None or ignored:
                self._close_current_session()
            elif process_name != self.current_process_name:
                self._close_current_session()
                self.session_start_time = datetime.now()
                self.current_session_id = database.start_session(
                    self.conn, app_name, process_name, title, self.session_start_time
                )
                self.current_process_name = process_name
                self.current_app_name = app_name
                self.current_window_title = title
                self.continuous_seconds_current_app = 0
                self.notified_for_current_session = False
            else:
                self.current_window_title = title
                now = datetime.now()
                duration = (now - self.session_start_time).total_seconds()
                database.end_session(self.conn, self.current_session_id, now, duration)
                self.continuous_seconds_current_app = self.continuous_seconds_current_app + poll_interval

                limits = self.settings.get('limits', {})
                if process_name in limits and not self.notified_for_current_session:
                    limit_minutes = limits[process_name]
                    if self.continuous_seconds_current_app >= limit_minutes * 60:
                        self.notified_for_current_session = True
                        if self.on_limit_exceeded:
                            self.on_limit_exceeded(app_name)

            if self.on_state_change:
                state = {}
                state['app_name'] = self.current_app_name
                state['process_name'] = self.current_process_name
                state['window_title'] = self.current_window_title
                state['is_idle'] = self.is_idle
                state['paused'] = self.paused
                self.on_state_change(state)

            time.sleep(poll_interval)
