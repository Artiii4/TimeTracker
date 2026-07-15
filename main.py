import os
import sys
import atexit
import database

def acquire_single_instance_lock():
    if sys.platform == 'win32':
        try:
            import ctypes
            mutex_name = 'Global\\TimeTrackerAppMutex'
            mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            last_error = ctypes.windll.kernel32.GetLastError()
            if last_error == 183:
                return False
            atexit.register(lambda: ctypes.windll.kernel32.CloseHandle(mutex))
            return True
        except Exception:
            pass
    lock_dir = database.get_app_data_dir()
    lock_path = os.path.join(lock_dir, 'timetracker.lock')
    if os.path.exists(lock_path):
        try:
            f = open(lock_path, 'r')
            old_pid = int(f.read().strip())
            f.close()
            os.kill(old_pid, 0)
            return False
        except (ValueError, OSError, ProcessLookupError):
            pass
    f = open(lock_path, 'w')
    f.write(str(os.getpid()))
    f.close()
    def cleanup():
        try:
            os.remove(lock_path)
        except OSError:
            pass
    atexit.register(cleanup)
    return True

def main():
    if not acquire_single_instance_lock():
        print('Application already running.')
        sys.exit(0)
    from ui import App
    app = App()
    app.mainloop()

if __name__ == '__main__':
    main()