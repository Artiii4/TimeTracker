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
    'Январь','Февраль','Март','Апрель','Май','Июнь',
    'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'
]

RU = {
    'limit_title':'Превышен лимит времени',
    'limit_message':'Вы слишком долго сидите в {app_name}!\nСделайте перерыв.',
    'ok':'Ок',
    'tab_now':'Сейчас','tab_stats':'Статистика','tab_settings':'Настройки',
    'active_window':'Активное окно:','process':'Процесс:','status':'Статус:',
    'today':'Сегодня:','pause':'⏸ Пауза','resume':'▶ Возобновить',
    'date_label':'Дата:','refresh':'Обновить','export_json':'Экспорт JSON',
    'apps_today':'Приложения за день','ignore_processes':'Игнорируемые процессы',
    'add':'Добавить','remove_selected':'Удалить выбранное',
    'time_limits':'Лимиты времени (минуты)','minutes':'минуты',
    'add_limit':'Добавить','remove_selected_limit':'Удалить выбранный лимит',
    'general_settings':'Общие настройки','dark_theme':'Тёмная тема',
    'autostart':'Запускать при старте Windows','database':'База данных:',
    'error':'Ошибка','minutes_must_be_number':'Минуты должны быть числом',
    'export_success':'Экспорт завершён','report_saved':'Отчёт сохранён:\n',
    'export_error':'Ошибка экспорта','autostart_title':'Автозагрузка',
    'autostart_fail':'Не удалось настроить автозагрузку.\nДобавьте ярлык вручную в:\nshell:startup',
    'pie_title':'Топ-5 приложений','no_data':'Нет данных','other':'Другое',
    'app_column':'Приложение','time_column':'Время','percent_column':'% от общего',
    'paused_status':'На паузе','idle_status':'Бездействие','active_status':'Активен',
    'language':'Язык','restart_required':'Требуется перезапуск',
    'restart_message':'Для смены языка нужен перезапуск.\nПерезапустить сейчас?',
    'yes':'Да','no':'Нет',
    'hour':'Час',
    'minutes_label':'Минуты',
    'activity_by_hour':'Активность по часам'
}
EN = {
    'limit_title':'Time limit exceeded',
    'limit_message':'You have been using {app_name} for too long!\nTake a break.',
    'ok':'OK',
    'tab_now':'Now','tab_stats':'Statistics','tab_settings':'Settings',
    'active_window':'Active window:','process':'Process:','status':'Status:',
    'today':'Today:','pause':'⏸ Pause','resume':'▶ Resume',
    'date_label':'Date:','refresh':'Refresh','export_json':'Export JSON',
    'apps_today':'Apps for today','ignore_processes':'Ignored processes',
    'add':'Add','remove_selected':'Remove selected',
    'time_limits':'Time limits (minutes)','minutes':'minutes',
    'add_limit':'Add','remove_selected_limit':'Remove selected limit',
    'general_settings':'General settings','dark_theme':'Dark theme',
    'autostart':'Launch at Windows startup','database':'Database:',
    'error':'Error','minutes_must_be_number':'Minutes must be a number',
    'export_success':'Export completed','report_saved':'Report saved to:\n',
    'export_error':'Export error','autostart_title':'Autostart',
    'autostart_fail':'Failed to set autostart.\nAdd a shortcut manually to:\nshell:startup',
    'pie_title':'Top 5 apps','no_data':'No data','other':'Other',
    'app_column':'App','time_column':'Time','percent_column':'% of total',
    'paused_status':'Paused','idle_status':'Idle','active_status':'Active',
    'language':'Language','restart_required':'Restart required',
    'restart_message':'Restart needed to apply language.\nRestart now?',
    'yes':'Yes','no':'No',
    'hour':'Hour',
    'minutes_label':'Minutes',
    'activity_by_hour':'Activity by hour'
}

def fmt_hms(sec):
    sec=int(sec)
    h=sec//3600
    m=(sec%3600)//60
    s=sec%60
    return f'{h:02d}:{m:02d}:{s:02d}'

def fmt_hm(sec):
    sec=int(sec)
    if sec<60: return f"{sec}с"
    h=sec//3600
    m=(sec%3600)//60
    return f"{h}ч {m:02d}м"

class LimitPopup(ctk.CTkToplevel):
    def __init__(self, master, app_name):
        super().__init__(master)
        self.master=master
        self.title(master.T('limit_title'))
        self.geometry('420x220')
        self.configure(fg_color='#8b0000')
        self.attributes('-topmost',True)
        self.resizable(False,False)
        msg=master.T('limit_message').format(app_name=app_name)
        label=ctk.CTkLabel(self,text=msg,font=ctk.CTkFont(size=16,weight='bold'),
                           text_color='white',wraplength=380,justify='center')
        label.pack(expand=True,padx=20,pady=20)
        btn=ctk.CTkButton(self,text=master.T('ok'),command=self.destroy,
                          fg_color='white',text_color='#8b0000')
        btn.pack(pady=10)
        self.after(100,self.lift)
        self.grab_set()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings=database.load_settings()
        ctk.set_appearance_mode(self.settings.get('theme','dark'))
        self.lang=self.settings.get('language','ru')
        self.title('TimeTracker')
        self.geometry('1000x700')
        self.minsize(850,600)
        self.db_conn=database.init_db(self.settings['db_path'])
        self.tracker=Tracker(self.settings,
                             on_state_change=self._on_state_change,
                             on_limit_exceeded=self._on_limit_exceeded)
        self.tracker.start()
        self.protocol('WM_DELETE_WINDOW',self._on_close)

        self.tv=ctk.CTkTabview(self,width=960,height=660)
        self.tv.pack(padx=15,pady=15,fill='both',expand=True)
        self.tab_now=self.tv.add(self.T('tab_now'))
        self.tab_stats=self.tv.add(self.T('tab_stats'))
        self.tab_settings=self.tv.add(self.T('tab_settings'))

        f=self.tab_now
        self.ind=tk.Canvas(f,width=30,height=30,highlightthickness=0)
        self.ind.place(x=30,y=30)
        bg=self._get_bg()
        self.ind.configure(bg=bg)
        self.ind_oval=self.ind.create_oval(2,2,28,28,fill='grey')
        self.lbl_win=ctk.CTkLabel(f,text=self.T('active_window')+' -',
                                  font=ctk.CTkFont(size=18,weight='bold'))
        self.lbl_win.place(x=75,y=25)
        self.lbl_proc=ctk.CTkLabel(f,text=self.T('process')+' -',font=ctk.CTkFont(size=14))
        self.lbl_proc.place(x=75,y=60)
        self.lbl_stat=ctk.CTkLabel(f,text=self.T('status')+' -',font=ctk.CTkFont(size=14))
        self.lbl_stat.place(x=75,y=90)
        self.lbl_today=ctk.CTkLabel(f,text=self.T('today')+' 00:00:00',
                                    font=ctk.CTkFont(size=28,weight='bold'))
        self.lbl_today.place(x=30,y=160)
        self.pbtn=ctk.CTkButton(f,text=self.T('pause'),width=180,height=50,
                                font=ctk.CTkFont(size=16),command=self._toggle_pause)
        self.pbtn.place(relx=1.0,rely=1.0,x=-30,y=-30,anchor='se')

        f=self.tab_stats
        top=ctk.CTkFrame(f,fg_color='transparent')
        top.pack(fill='x',padx=10,pady=10)
        today=date.today()
        self.day_var=tk.StringVar(value=str(today.day))
        self.month_var=tk.StringVar(value=MONTHS_RU[today.month-1])
        self.year_var=tk.StringVar(value=str(today.year))
        ctk.CTkLabel(top,text=self.T('date_label')).pack(side='left',padx=(0,5))
        self.day_menu=ctk.CTkOptionMenu(top,values=[str(d) for d in range(1,32)],
                                        variable=self.day_var,width=70)
        self.day_menu.pack(side='left',padx=5)
        self.month_menu=ctk.CTkOptionMenu(top,values=MONTHS_RU,
                                          variable=self.month_var,width=130)
        self.month_menu.pack(side='left',padx=5)
        self.year_menu=ctk.CTkOptionMenu(top,values=[str(y) for y in range(today.year-3,today.year+1)],
                                         variable=self.year_var,width=90)
        self.year_menu.pack(side='left',padx=5)
        ctk.CTkButton(top,text=self.T('refresh'),command=self._refresh_stats).pack(side='left',padx=15)
        ctk.CTkButton(top,text=self.T('export_json'),command=self._export_json).pack(side='left',padx=5)

        chf=ctk.CTkFrame(f,fg_color='transparent')
        chf.pack(fill='both',expand=False,padx=10,pady=5)
        self.pie_fig=Figure(figsize=(4.3,3.3),dpi=90)
        self.pie_ax=self.pie_fig.add_subplot(111)
        self.pie_canvas=FigureCanvasTkAgg(self.pie_fig,master=chf)
        self.pie_canvas.get_tk_widget().pack(side='left',fill='both',expand=True,padx=5)
        self.line_fig=Figure(figsize=(5.3,3.3),dpi=90)
        self.line_ax=self.line_fig.add_subplot(111)
        self.line_canvas=FigureCanvasTkAgg(self.line_fig,master=chf)
        self.line_canvas.get_tk_widget().pack(side='left',fill='both',expand=True,padx=5)

        ctk.CTkLabel(f,text=self.T('apps_today'),font=ctk.CTkFont(size=14,weight='bold')).pack(anchor='w',padx=15,pady=(10,0))
        self.table_frame=ctk.CTkScrollableFrame(f,height=180)
        self.table_frame.pack(fill='both',expand=True,padx=10,pady=10)
        self._refresh_stats()

        f=self.tab_settings
        left=ctk.CTkFrame(f,fg_color='transparent')
        left.pack(side='left',fill='both',expand=True,padx=10,pady=10)
        right=ctk.CTkFrame(f,fg_color='transparent')
        right.pack(side='left',fill='both',expand=True,padx=10,pady=10)

        ctk.CTkLabel(left,text=self.T('ignore_processes'),font=ctk.CTkFont(size=15,weight='bold')).pack(anchor='w')
        self.ignore_listbox=tk.Listbox(left,height=10)
        self.ignore_listbox.pack(fill='x',pady=5)
        for p in self.settings.get('ignore_list',[]):
            self.ignore_listbox.insert('end',p)
        ie_frame=ctk.CTkFrame(left,fg_color='transparent')
        ie_frame.pack(fill='x',pady=5)
        self.ignore_entry=ctk.CTkEntry(ie_frame,placeholder_text='например: chrome.exe')
        self.ignore_entry.pack(side='left',fill='x',expand=True,padx=(0,5))
        ctk.CTkButton(ie_frame,text=self.T('add'),width=90,command=self._add_ignore).pack(side='left')
        ctk.CTkButton(left,text=self.T('remove_selected'),command=self._remove_ignore).pack(anchor='w',pady=5)

        ctk.CTkLabel(left,text=self.T('time_limits'),font=ctk.CTkFont(size=15,weight='bold')).pack(anchor='w',pady=(20,0))
        self.limits_listbox=tk.Listbox(left,height=8)
        self.limits_listbox.pack(fill='x',pady=5)
        for proc, mins in self.settings.get('limits',{}).items():
            self.limits_listbox.insert('end',f"{proc} — {mins} {self.T('minutes')}")
        lim_frame=ctk.CTkFrame(left,fg_color='transparent')
        lim_frame.pack(fill='x',pady=5)
        self.limit_proc_entry=ctk.CTkEntry(lim_frame,placeholder_text='процесс, например steam.exe')
        self.limit_proc_entry.pack(side='left',fill='x',expand=True,padx=(0,5))
        self.limit_min_entry=ctk.CTkEntry(lim_frame,placeholder_text=self.T('minutes'),width=80)
        self.limit_min_entry.pack(side='left',padx=(0,5))
        ctk.CTkButton(lim_frame,text=self.T('add_limit'),width=90,command=self._add_limit).pack(side='left')
        ctk.CTkButton(left,text=self.T('remove_selected_limit'),command=self._remove_limit).pack(anchor='w',pady=5)

        ctk.CTkLabel(right,text=self.T('general_settings'),font=ctk.CTkFont(size=15,weight='bold')).pack(anchor='w')
        th_frame=ctk.CTkFrame(right,fg_color='transparent')
        th_frame.pack(fill='x',pady=15)
        ctk.CTkLabel(th_frame,text=self.T('dark_theme')).pack(side='left')
        self.theme_switch_var=tk.BooleanVar(value=self.settings.get('theme')=='dark')
        self.theme_switch=ctk.CTkSwitch(th_frame,text='',variable=self.theme_switch_var,
                                        command=self._toggle_theme)
        self.theme_switch.pack(side='left',padx=10)

        autostart_frame=ctk.CTkFrame(right,fg_color='transparent')
        autostart_frame.pack(fill='x',pady=5)
        self.autostart_var=tk.BooleanVar(value=self.settings.get('autostart',False))
        self.autostart_cb=ctk.CTkCheckBox(autostart_frame,text=self.T('autostart'),
                                          variable=self.autostart_var,command=self._toggle_autostart)
        self.autostart_cb.pack(side='left')

        lang_frame=ctk.CTkFrame(right,fg_color='transparent')
        lang_frame.pack(fill='x',pady=5)
        ctk.CTkLabel(lang_frame,text=self.T('language')).pack(side='left')
        lang_opts=['Русский','English']
        self.lang_var=tk.StringVar(value='Русский' if self.lang=='ru' else 'English')
        self.lang_menu=ctk.CTkOptionMenu(lang_frame,values=lang_opts,
                                         variable=self.lang_var,width=120,
                                         command=lambda v: self._change_lang(v))
        self.lang_menu.pack(side='left',padx=10)

        info_frame=ctk.CTkFrame(right,fg_color='transparent')
        info_frame.pack(fill='x',pady=20)
        ctk.CTkLabel(info_frame,text=self.T('database')+'\n'+self.settings['db_path'],
                     wraplength=350,justify='left',font=ctk.CTkFont(size=12)).pack(anchor='w')

        self._update_indicator()
        self._update_win_info()
        self._update_today()

    def T(self,key):
        return (EN if self.lang=='en' else RU).get(key,key)

    def _get_bg(self):
        mode=ctk.get_appearance_mode()
        fg=self.tab_now.cget('fg_color')
        if isinstance(fg, tuple):
            return fg[1] if mode=='dark' else fg[0]
        return fg

    def _change_lang(self,val):
        new='ru' if val=='Русский' else 'en'
        if new==self.lang: return
        self.lang=new
        self.settings['language']=new
        database.save_settings(self.settings)
        if messagebox.askyesno(self.T('restart_required'),self.T('restart_message')):
            os.execv(sys.executable,[sys.executable]+sys.argv)

    def _toggle_theme(self):
        mode='dark' if self.theme_switch_var.get() else 'light'
        ctk.set_appearance_mode(mode)
        self.settings['theme']=mode
        database.save_settings(self.settings)
        self.ind.configure(bg=self._get_bg())

    def _add_ignore(self):
        val=self.ignore_entry.get().strip()
        if not val: return
        lst=self.settings.get('ignore_list',[])
        if val not in lst:
            lst.append(val)
            self.settings['ignore_list']=lst
            self.ignore_listbox.insert('end',val)
            database.save_settings(self.settings)
        self.ignore_entry.delete(0,'end')

    def _remove_ignore(self):
        sel=self.ignore_listbox.curselection()
        if not sel: return
        val=self.ignore_listbox.get(sel[0])
        lst=self.settings.get('ignore_list',[])
        if val in lst:
            lst.remove(val)
            self.settings['ignore_list']=lst
            database.save_settings(self.settings)
        self.ignore_listbox.delete(sel[0])

    def _add_limit(self):
        proc=self.limit_proc_entry.get().strip()
        mins=self.limit_min_entry.get().strip()
        if not proc or not mins: return
        try:
            mins=int(mins)
        except ValueError:
            messagebox.showerror(self.T('error'),self.T('minutes_must_be_number'))
            return
        limits=self.settings.get('limits',{})
        limits[proc]=mins
        self.settings['limits']=limits
        database.save_settings(self.settings)
        self._refresh_limits()
        self.limit_proc_entry.delete(0,'end')
        self.limit_min_entry.delete(0,'end')

    def _remove_limit(self):
        sel=self.limits_listbox.curselection()
        if not sel: return
        txt=self.limits_listbox.get(sel[0])
        proc=txt.split(' — ')[0]
        limits=self.settings.get('limits',{})
        if proc in limits:
            del limits[proc]
            self.settings['limits']=limits
            database.save_settings(self.settings)
        self._refresh_limits()

    def _refresh_limits(self):
        self.limits_listbox.delete(0,'end')
        for p,m in self.settings.get('limits',{}).items():
            self.limits_listbox.insert('end',f"{p} — {m} {self.T('minutes')}")

    def _toggle_autostart(self):
        en=self.autostart_var.get()
        ok=self._set_autostart(en)
        if not ok:
            messagebox.showwarning(self.T('autostart_title'),self.T('autostart_fail'))
            self.autostart_var.set(not en)
            return
        self.settings['autostart']=en
        database.save_settings(self.settings)

    def _set_autostart(self,en):
        if sys.platform!='win32': return False
        try:
            startup=os.path.join(os.environ['APPDATA'],'Microsoft','Windows','Start Menu','Programs','Startup')
            path=os.path.join(startup,'TimeTracker.bat')
            if en:
                with open(path,'w',encoding='utf-8') as f:
                    f.write(f'@echo off\nstart "" "{sys.executable}" "{os.path.abspath(sys.argv[0])}"\n')
            else:
                if os.path.exists(path): os.remove(path)
            return True
        except:
            return False

    def _get_date(self):
        try:
            d=int(self.day_var.get())
            m=MONTHS_RU.index(self.month_var.get())+1
            y=int(self.year_var.get())
            return date(y,m,d)
        except:
            return date.today()

    def _refresh_stats(self):
        dt=self._get_date()
        sess=database.get_sessions_for_date(self.db_conn,dt)
        totals={}
        for s in sess:
            n=s['app_name']
            totals[n]=totals.get(n,0)+s['duration_seconds']
        sorted_apps=sorted(totals.items(),key=lambda x:x[1],reverse=True)
        total=sum(totals.values())

        self.pie_ax.clear()
        if sorted_apps:
            top5=sorted_apps[:5]
            rest=sorted_apps[5:]
            labels=[x[0] for x in top5]
            vals=[x[1] for x in top5]
            if rest:
                labels.append(self.T('other'))
                vals.append(sum(x[1] for x in rest))
            self.pie_ax.pie(vals,labels=labels,autopct='%1.1f%%',textprops={'fontsize':8})
        else:
            self.pie_ax.text(0.5,0.5,self.T('no_data'),ha='center',va='center')
        self.pie_ax.set_title(self.T('pie_title'),fontsize=10)
        self.pie_fig.tight_layout()
        self.pie_canvas.draw()

        hourly=[0.0]*24
        for s in sess:
            try:
                h=datetime.fromisoformat(s['start_time']).hour
                hourly[h]+=s['duration_seconds']/60.0
            except:
                continue
        self.line_ax.clear()
        self.line_ax.plot(range(24),hourly,marker='o',markersize=3)
        self.line_ax.set_xlabel(self.T('hour'), fontsize=8)
        self.line_ax.set_ylabel(self.T('minutes_label'), fontsize=8)
        self.line_ax.set_title(self.T('activity_by_hour'), fontsize=10)
        self.line_ax.set_xticks(range(0,24,2))
        self.line_ax.tick_params(labelsize=7)
        self.line_fig.tight_layout()
        self.line_canvas.draw()

        for w in self.table_frame.winfo_children(): w.destroy()
        hfont=ctk.CTkFont(size=13,weight='bold')
        for col,txt in enumerate([self.T('app_column'),self.T('time_column'),self.T('percent_column')]):
            ctk.CTkLabel(self.table_frame,text=txt,font=hfont).grid(row=0,column=col,padx=10,pady=5,sticky='w')
        row=1
        for name,sec in sorted_apps:
            pct=(sec/total*100) if total else 0
            ctk.CTkLabel(self.table_frame,text=name).grid(row=row,column=0,padx=10,pady=3,sticky='w')
            ctk.CTkLabel(self.table_frame,text=fmt_hm(sec)).grid(row=row,column=1,padx=10,pady=3,sticky='w')
            ctk.CTkLabel(self.table_frame,text=f'{pct:.1f}%').grid(row=row,column=2,padx=10,pady=3,sticky='w')
            row+=1

    def _export_json(self):
        dt=self._get_date()
        sess=database.get_sessions_for_date(self.db_conn,dt)
        totals={}
        for s in sess:
            n=s['app_name']
            totals[n]=totals.get(n,0)+s['duration_seconds']
        apps=[{'app_name':n,'duration_seconds':sec} for n,sec in sorted(totals.items(),key=lambda x:x[1],reverse=True)]
        report={'date':dt.isoformat(),'total_seconds':sum(totals.values()),'apps':apps,'sessions':sess}
        exp_path=os.path.join(os.path.dirname(self.settings['db_path']),f'report_{dt.isoformat()}.json')
        try:
            with open(exp_path,'w',encoding='utf-8') as f:
                json.dump(report,f,ensure_ascii=False,indent=4)
            messagebox.showinfo(self.T('export_success'),self.T('report_saved')+exp_path)
        except OSError as e:
            messagebox.showerror(self.T('export_error'),str(e))

    def _toggle_pause(self):
        p=not self.tracker.paused
        self.tracker.set_paused(p)
        self.pbtn.configure(text=self.T('resume') if p else self.T('pause'))

    def _on_state_change(self,state): pass

    def _update_win_info(self):
        if self.tracker.paused:
            title=self.T('paused_status')
            proc='-'
        else:
            title=self.tracker.current_window_title or '-'
            proc=self.tracker.current_process_name or '-'
        self.lbl_win.configure(text=self.T('active_window')+' '+title)
        self.lbl_proc.configure(text=self.T('process')+' '+proc)
        self.after(5000,self._update_win_info)

    def _update_indicator(self):
        if self.tracker.paused:
            color='#e53935'; stat=self.T('paused_status')
        elif self.tracker.is_idle:
            color='#fdd835'; stat=self.T('idle_status')
        else:
            color='#43a047'; stat=self.T('active_status')
        self.ind.itemconfig(self.ind_oval,fill=color)
        self.lbl_stat.configure(text=self.T('status')+' '+stat)
        self.after(1000,self._update_indicator)

    def _update_today(self):
        sec=database.get_total_seconds_today(self.db_conn,date.today())
        self.lbl_today.configure(text=self.T('today')+' '+fmt_hms(sec))
        self.after(5000,self._update_today)

    def _on_limit_exceeded(self,app_name):
        self.after(0,lambda: LimitPopup(self,app_name))

    def _on_close(self):
        self.tracker.stop()
        try: self.db_conn.close()
        except: pass
        self.destroy()