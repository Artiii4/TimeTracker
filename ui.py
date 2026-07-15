import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import date, datetime
import json
import os
import sys

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import database
from tracker import Tracker

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

MONTHS_RU = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
]


def format_hms(total_seconds):
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return '%02d:%02d:%02d' % (hours, minutes, seconds)


def format_hm(total_seconds):
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}ч {minutes:02d}м"


class LimitPopup(ctk.CTkToplevel):
    def __init__(self, master, app_name):
        super().__init__(master)
        self.title('Превышен лимит времени')
        self.geometry('420x220')
        self.configure(fg_color='#8b0000')
        self.attributes('-topmost', True)
        self.resizable(False, False)

        msg = f"Вы слишком долго сидите в {app_name}!\nСделайте перерыв."
        label = ctk.CTkLabel(
            self, text=msg, font=ctk.CTkFont(size=16, weight='bold'),
            text_color='white', wraplength=380, justify='center'
        )
        label.pack(expand=True, padx=20, pady=20)

        ok_button = ctk.CTkButton(self, text='Ок', command=self.destroy, fg_color='white', text_color='#8b0000')
        ok_button.pack(pady=10)

        self.after(100, self.lift)
        self.grab_set()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = database.load_settings()
        ctk.set_appearance_mode(self.settings.get('theme', 'dark'))

        self.title("TimeTracker")
        self.geometry('1000x700')
        self.minsize(850, 600)

        self.db_conn = database.init_db(self.settings['db_path'])

        self.tracker = Tracker(
            self.settings,
            on_state_change=self._on_tracker_state_change,
            on_limit_exceeded=self._on_limit_exceeded
        )
        self.tracker.start()

        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self._build_ui()
        self._update_now_tab_indicator()
        self._update_now_tab_window_info()
        self._update_today_timer()

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self, width=960, height=660)
        self.tabview.pack(padx=15, pady=15, fill='both', expand=True)

        self.tab_now = self.tabview.add('Сейчас')
        self.tab_stats = self.tabview.add('Статистика')
        self.tab_settings = self.tabview.add('Настройки')

        self._build_now_tab()
        self._build_stats_tab()
        self._build_settings_tab()

    def _build_now_tab(self):
        frame = self.tab_now

        self.indicator_canvas = tk.Canvas(frame, width=30, height=30, highlightthickness=0)
        self.indicator_canvas.place(x=30, y=30)
        self.indicator_oval = self.indicator_canvas.create_oval(2, 2, 28, 28, fill='grey')

        self.label_window_title = ctk.CTkLabel(frame, text='Активное окно: -', font=ctk.CTkFont(size=18, weight='bold'))
        self.label_window_title.place(x=75, y=25)

        self.label_process = ctk.CTkLabel(frame, text='Процесс: -', font=ctk.CTkFont(size=14))
        self.label_process.place(x=75, y=60)

        self.label_status = ctk.CTkLabel(frame, text='Статус: -', font=ctk.CTkFont(size=14))
        self.label_status.place(x=75, y=90)

        self.label_today_timer = ctk.CTkLabel(frame, text='Сегодня: 00:00:00', font=ctk.CTkFont(size=28, weight='bold'))
        self.label_today_timer.place(x=30, y=160)

        self.pause_button = ctk.CTkButton(
            frame, text='⏸ Пауза', width=180, height=50, font=ctk.CTkFont(size=16), command=self._toggle_pause
        )
        self.pause_button.place(relx=1.0, rely=1.0, x=-30, y=-30, anchor='se')

    def _build_stats_tab(self):
        frame = self.tab_stats

        top_bar = ctk.CTkFrame(frame, fg_color='transparent')
        top_bar.pack(fill='x', padx=10, pady=10)

        today = date.today()
        self.day_var = tk.StringVar(value=str(today.day))
        self.month_var = tk.StringVar(value=MONTHS_RU[today.month - 1])
        self.year_var = tk.StringVar(value=str(today.year))

        ctk.CTkLabel(top_bar, text='Дата:').pack(side='left', padx=(0, 5))

        day_values = []
        for d in range(1, 32):
            day_values.append(str(d))
        self.day_menu = ctk.CTkOptionMenu(top_bar, values=day_values, variable=self.day_var, width=70)
        self.day_menu.pack(side='left', padx=5)

        self.month_menu = ctk.CTkOptionMenu(top_bar, values=MONTHS_RU, variable=self.month_var, width=130)
        self.month_menu.pack(side='left', padx=5)

        years = [str(y) for y in range(today.year - 3, today.year + 1)]
        self.year_menu = ctk.CTkOptionMenu(top_bar, values=years, variable=self.year_var, width=90)
        self.year_menu.pack(side='left', padx=5)

        ctk.CTkButton(top_bar, text='Обновить', command=self._refresh_stats).pack(side='left', padx=15)
        ctk.CTkButton(top_bar, text='Экспорт JSON', command=self._export_json).pack(side='left', padx=5)

        charts_frame = ctk.CTkFrame(frame, fg_color='transparent')
        charts_frame.pack(fill='both', expand=False, padx=10, pady=5)

        self.pie_figure = Figure(figsize=(4.3, 3.3), dpi=90)
        self.pie_ax = self.pie_figure.add_subplot(111)
        self.pie_canvas = FigureCanvasTkAgg(self.pie_figure, master=charts_frame)
        self.pie_canvas.get_tk_widget().pack(side='left', fill='both', expand=True, padx=5)

        self.line_figure = Figure(figsize=(5.3, 3.3), dpi=90)
        self.line_ax = self.line_figure.add_subplot(111)
        self.line_canvas = FigureCanvasTkAgg(self.line_figure, master=charts_frame)
        self.line_canvas.get_tk_widget().pack(side='left', fill='both', expand=True, padx=5)

        ctk.CTkLabel(frame, text='Приложения за день', font=ctk.CTkFont(size=14, weight='bold')).pack(anchor='w', padx=15, pady=(10, 0))

        self.table_frame = ctk.CTkScrollableFrame(frame, height=180)
        self.table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self._refresh_stats()

    def _build_settings_tab(self):
        frame = self.tab_settings

        left = ctk.CTkFrame(frame, fg_color='transparent')
        left.pack(side='left', fill='both', expand=True, padx=10, pady=10)

        right = ctk.CTkFrame(frame, fg_color='transparent')
        right.pack(side='left', fill='both', expand=True, padx=10, pady=10)

        ctk.CTkLabel(left, text='Игнорируемые процессы', font=ctk.CTkFont(size=15, weight='bold')).pack(anchor='w')

        self.ignore_listbox = tk.Listbox(left, height=10)
        self.ignore_listbox.pack(fill='x', pady=5)
        for proc in self.settings.get('ignore_list', []):
            self.ignore_listbox.insert('end', proc)

        ignore_entry_frame = ctk.CTkFrame(left, fg_color='transparent')
        ignore_entry_frame.pack(fill='x', pady=5)

        self.ignore_entry = ctk.CTkEntry(ignore_entry_frame, placeholder_text='например: chrome.exe')
        self.ignore_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        ctk.CTkButton(ignore_entry_frame, text='Добавить', width=90, command=self._add_ignore).pack(side='left')
        ctk.CTkButton(left, text='Удалить выбранное', command=self._remove_ignore).pack(anchor='w', pady=5)

        ctk.CTkLabel(left, text='Лимиты времени (минуты)', font=ctk.CTkFont(size=15, weight='bold')).pack(anchor='w', pady=(20, 0))

        self.limits_listbox = tk.Listbox(left, height=8)
        self.limits_listbox.pack(fill='x', pady=5)
        for proc, minutes in self.settings.get('limits', {}).items():
            self.limits_listbox.insert('end', proc + ' — ' + str(minutes) + ' мин')

        limit_entry_frame = ctk.CTkFrame(left, fg_color='transparent')
        limit_entry_frame.pack(fill='x', pady=5)

        self.limit_process_entry = ctk.CTkEntry(limit_entry_frame, placeholder_text='процесс, например steam.exe')
        self.limit_process_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))

        self.limit_minutes_entry = ctk.CTkEntry(limit_entry_frame, placeholder_text='минуты', width=80)
        self.limit_minutes_entry.pack(side='left', padx=(0, 5))

        ctk.CTkButton(limit_entry_frame, text='Добавить', width=90, command=self._add_limit).pack(side='left')
        ctk.CTkButton(left, text='Удалить выбранный лимит', command=self._remove_limit).pack(anchor='w', pady=5)

        ctk.CTkLabel(right, text='Общие настройки', font=ctk.CTkFont(size=15, weight='bold')).pack(anchor='w')

        theme_frame = ctk.CTkFrame(right, fg_color='transparent')
        theme_frame.pack(fill='x', pady=15)
        ctk.CTkLabel(theme_frame, text='Тёмная тема').pack(side='left')
        self.theme_switch_var = tk.BooleanVar(value=self.settings.get('theme') == 'dark')
        self.theme_switch = ctk.CTkSwitch(theme_frame, text='', variable=self.theme_switch_var, command=self._toggle_theme)
        self.theme_switch.pack(side='left', padx=10)

        autostart_frame = ctk.CTkFrame(right, fg_color='transparent')
        autostart_frame.pack(fill='x', pady=5)
        self.autostart_var = tk.BooleanVar(value=self.settings.get('autostart', False))
        self.autostart_checkbox = ctk.CTkCheckBox(
            autostart_frame, text='Запускать при старте Windows', variable=self.autostart_var, command=self._toggle_autostart
        )
        self.autostart_checkbox.pack(side='left')

        info_frame = ctk.CTkFrame(right, fg_color='transparent')
        info_frame.pack(fill='x', pady=20)
        db_info_text = 'База данных:\n' + self.settings['db_path']
        ctk.CTkLabel(info_frame, text=db_info_text, wraplength=350, justify='left', font=ctk.CTkFont(size=12)).pack(anchor='w')

    def _add_ignore(self):
        value = self.ignore_entry.get().strip()
        if not value:
            return
        ignore_list = self.settings.get('ignore_list', [])
        if value not in ignore_list:
            ignore_list.append(value)
            self.settings['ignore_list'] = ignore_list
            self.ignore_listbox.insert('end', value)
            database.save_settings(self.settings)
        self.ignore_entry.delete(0, 'end')

    def _remove_ignore(self):
        selection = self.ignore_listbox.curselection()
        if not selection:
            return
        value = self.ignore_listbox.get(selection[0])
        ignore_list = self.settings.get('ignore_list', [])
        if value in ignore_list:
            ignore_list.remove(value)
            self.settings['ignore_list'] = ignore_list
            database.save_settings(self.settings)
        self.ignore_listbox.delete(selection[0])

    def _add_limit(self):
        process = self.limit_process_entry.get().strip()
        minutes_text = self.limit_minutes_entry.get().strip()
        if not process or not minutes_text:
            return
        try:
            minutes = int(minutes_text)
        except ValueError:
            messagebox.showerror('Ошибка', 'Минуты должны быть числом')
            return
        limits = self.settings.get('limits', {})
        limits[process] = minutes
        self.settings['limits'] = limits
        database.save_settings(self.settings)
        self._refresh_limits_listbox()
        self.limit_process_entry.delete(0, 'end')
        self.limit_minutes_entry.delete(0, 'end')

    def _remove_limit(self):
        selection = self.limits_listbox.curselection()
        if not selection:
            return
        text = self.limits_listbox.get(selection[0])
        process = text.split(' — ')[0]
        limits = self.settings.get('limits', {})
        if process in limits:
            del limits[process]
            self.settings['limits'] = limits
            database.save_settings(self.settings)
        self._refresh_limits_listbox()

    def _refresh_limits_listbox(self):
        self.limits_listbox.delete(0, 'end')
        for proc, minutes in self.settings.get('limits', {}).items():
            self.limits_listbox.insert('end', proc + ' — ' + str(minutes) + ' мин')

    def _toggle_theme(self):
        is_dark = self.theme_switch_var.get()
        if is_dark:
            mode = 'dark'
        else:
            mode = 'light'
        ctk.set_appearance_mode(mode)
        self.settings['theme'] = mode
        database.save_settings(self.settings)

    def _toggle_autostart(self):
        enabled = self.autostart_var.get()
        success = self._set_autostart(enabled)
        if not success:
            messagebox.showwarning(
                'Автозагрузка',
                'Не удалось автоматически настроить автозагрузку.\n'
                'Добавьте ярлык приложения вручную в папку:\n'
                'shell:startup'
            )
            self.autostart_var.set(not enabled)
            return
        self.settings['autostart'] = enabled
        database.save_settings(self.settings)

    def _set_autostart(self, enabled):
        if sys.platform != 'win32':
            return False
        try:
            startup_dir = os.path.join(
                os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
            )
            shortcut_path = os.path.join(startup_dir, 'TimeTracker.bat')
            if enabled:
                exe_path = sys.executable
                script_path = os.path.abspath(sys.argv[0])
                f = open(shortcut_path, 'w', encoding='utf-8')
                f.write('@echo off\nstart "" "' + exe_path + '" "' + script_path + '"\n')
                f.close()
            else:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
            return True
        except Exception:
            return False

    def _get_selected_date(self):
        try:
            day = int(self.day_var.get())
            month = MONTHS_RU.index(self.month_var.get()) + 1
            year = int(self.year_var.get())
            return date(year, month, day)
        except (ValueError, IndexError):
            return date.today()

    def _refresh_stats(self):
        selected_date = self._get_selected_date()
        sessions = database.get_sessions_for_date(self.db_conn, selected_date)

        app_totals = {}
        for s in sessions:
            name = s['app_name']
            if name in app_totals:
                app_totals[name] = app_totals[name] + s['duration_seconds']
            else:
                app_totals[name] = s['duration_seconds']

        sorted_apps = sorted(app_totals.items(), key=lambda x: x[1], reverse=True)
        total_seconds = 0
        for name in app_totals:
            total_seconds += app_totals[name]

        self.pie_ax.clear()
        if len(sorted_apps) > 0:
            top5 = sorted_apps[:5]
            rest = sorted_apps[5:]
            labels = [a[0] for a in top5]
            values = [a[1] for a in top5]
            if rest:
                other_total = 0
                for item in rest:
                    other_total += item[1]
                labels.append('Другое')
                values.append(other_total)
            self.pie_ax.pie(values, labels=labels, autopct='%1.1f%%', textprops={'fontsize': 8})
        else:
            self.pie_ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center')
        self.pie_ax.set_title('Топ-5 приложений', fontsize=10)
        self.pie_figure.tight_layout()
        self.pie_canvas.draw()

        hourly_minutes = [0.0] * 24
        for s in sessions:
            try:
                start_dt = datetime.fromisoformat(s['start_time'])
                hour = start_dt.hour
                hourly_minutes[hour] += s['duration_seconds'] / 60.0
            except (ValueError, TypeError):
                continue

        self.line_ax.clear()
        self.line_ax.plot(range(24), hourly_minutes, marker='o', markersize=3)
        self.line_ax.set_xlabel('Час', fontsize=8)
        self.line_ax.set_ylabel('Минуты', fontsize=8)
        self.line_ax.set_title('Активность по часам', fontsize=10)
        self.line_ax.set_xticks(range(0, 24, 2))
        self.line_ax.tick_params(labelsize=7)
        self.line_figure.tight_layout()
        self.line_canvas.draw()

        for widget in self.table_frame.winfo_children():
            widget.destroy()

        header_font = ctk.CTkFont(size=13, weight='bold')
        headers = ['Приложение', 'Время', '% от общего']
        col = 0
        for text in headers:
            ctk.CTkLabel(self.table_frame, text=text, font=header_font).grid(row=0, column=col, padx=10, pady=5, sticky='w')
            col += 1

        row_index = 1
        for app_name, seconds in sorted_apps:
            if total_seconds > 0:
                percent = seconds / total_seconds * 100
            else:
                percent = 0
            ctk.CTkLabel(self.table_frame, text=app_name).grid(row=row_index, column=0, padx=10, pady=3, sticky='w')
            ctk.CTkLabel(self.table_frame, text=format_hm(seconds)).grid(row=row_index, column=1, padx=10, pady=3, sticky='w')
            ctk.CTkLabel(self.table_frame, text='%.1f%%' % percent).grid(row=row_index, column=2, padx=10, pady=3, sticky='w')
            row_index += 1

    def _export_json(self):
        selected_date = self._get_selected_date()
        sessions = database.get_sessions_for_date(self.db_conn, selected_date)

        app_totals = {}
        for s in sessions:
            name = s['app_name']
            if name in app_totals:
                app_totals[name] = app_totals[name] + s['duration_seconds']
            else:
                app_totals[name] = s['duration_seconds']

        apps_list = []
        for name, seconds in sorted(app_totals.items(), key=lambda x: x[1], reverse=True):
            apps_list.append({'app_name': name, 'duration_seconds': seconds})

        report = {
            'date': selected_date.isoformat(),
            'total_seconds': sum(app_totals.values()),
            'apps': apps_list,
            'sessions': sessions
        }

        export_dir = os.path.dirname(self.settings['db_path'])
        filename = 'report_' + selected_date.isoformat() + '.json'
        export_path = os.path.join(export_dir, filename)

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=4)
            messagebox.showinfo('Экспорт завершён', 'Отчёт сохранён:\n' + export_path)
        except OSError as e:
            messagebox.showerror('Ошибка экспорта', str(e))

    def _toggle_pause(self):
        new_paused = not self.tracker.paused
        self.tracker.set_paused(new_paused)
        if new_paused:
            self.pause_button.configure(text='▶ Возобновить')
        else:
            self.pause_button.configure(text='⏸ Пауза')

    def _on_tracker_state_change(self, state):
        pass

    def _update_now_tab_window_info(self):
        if self.tracker.paused:
            title_text = 'На паузе'
            process_text = 'Процесс: -'
        else:
            title_text = self.tracker.current_window_title or '-'
            process_name = self.tracker.current_process_name or '-'
            process_text = 'Процесс: ' + process_name

        self.label_window_title.configure(text='Активное окно: ' + title_text)
        self.label_process.configure(text=process_text)

        self.after(5000, self._update_now_tab_window_info)

    def _update_now_tab_indicator(self):
        if self.tracker.paused:
            color = '#e53935'
            status_text = 'Статус: На паузе'
        elif self.tracker.is_idle:
            color = '#fdd835'
            status_text = 'Статус: Бездействие'
        else:
            color = '#43a047'
            status_text = 'Статус: Активен'

        self.indicator_canvas.itemconfig(self.indicator_oval, fill=color)
        self.label_status.configure(text=status_text)

        self.after(1000, self._update_now_tab_indicator)

    def _update_today_timer(self):
        total_seconds = database.get_total_seconds_today(self.db_conn, date.today())
        self.label_today_timer.configure(text='Сегодня: ' + format_hms(total_seconds))
        self.after(5000, self._update_today_timer)

    def _on_limit_exceeded(self, app_name):
        self.after(0, lambda: self._show_limit_popup(app_name))

    def _show_limit_popup(self, app_name):
        LimitPopup(self, app_name)

    def _on_close(self):
        self.tracker.stop()
        try:
            self.db_conn.close()
        except Exception:
            pass
        self.destroy()
