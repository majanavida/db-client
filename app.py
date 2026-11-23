import tkinter as tk
from collections import Counter
from sys import platform
from tkinter import messagebox, ttk

import database


SECTIONS = {
    'main': 'Контакты',
    'fam': 'Фамилии',
    'name': 'Имена',
    'otc': 'Отчества',
    'street': 'Улицы',
}

CONTACT_FIELDS = {
    'fam': 'Фамилия',
    'name': 'Имя',
    'otc': 'Отчество',
    'street': 'Улица',
    'bldn': 'Дом',
    'bldn_k': 'Корпус',
    'appr': 'Квартира',
    'telef': 'Телефон',
}


def set_dark_title(root):
    if platform != 'win32':
        return

    from ctypes import byref, c_int, sizeof, windll
    from ctypes.wintypes import HWND, UINT

    get_ancestor = windll.user32.GetAncestor
    get_ancestor.argtypes = (HWND, UINT)
    get_ancestor.restype = HWND
    window = HWND(get_ancestor(root.winfo_id(), 2))

    # параметры windows для тёмного заголовка, чёрного фона и светлого текста
    for attribute, value in ((20, 1), (35, 0x000000), (36, 0xf2f3f4)):
        setting = c_int(value)
        windll.dwmapi.DwmSetWindowAttribute(window, attribute, byref(setting), sizeof(setting))


class DatabaseClient:
    def __init__(self, root):
        root.title('Телефонный справочник')
        root.geometry('1180x700')
        root.minsize(960, 540)
        root.configure(background='#292b2e')
        root.after_idle(set_dark_title, root)
        self.connection = None
        self.table = 'main'
        self.fields = {}
        self.options = {}
        self.rows = {}

        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background='#292b2e', foreground='#f2f3f4',
                        fieldbackground='#202225', bordercolor='#4b4e52',
                        lightcolor='#4b4e52', darkcolor='#4b4e52', font=('Segoe UI', 10))
        style.configure('TEntry', padding=5, insertcolor='#f2f3f4')
        style.configure('TCombobox', padding=5, arrowcolor='#f2f3f4', insertcolor='#f2f3f4')
        style.map('TCombobox', fieldbackground=[('readonly', '#202225')],
                  foreground=[('readonly', '#f2f3f4')], selectbackground=[('readonly', '#202225')],
                  selectforeground=[('readonly', '#f2f3f4')])
        style.configure('TButton', padding=(8, 6), background='#43464a')
        style.map('TButton', background=[('pressed', '#555a60'), ('active', '#50555a')])
        style.configure('Search.TButton', background='#406080')
        style.map('Search.TButton', background=[('pressed', '#3a5671'), ('active', '#4e7399')])
        style.configure('Treeview', background='#202225', fieldbackground='#202225', rowheight=31)
        style.configure('Treeview.Heading', background='#34373a', padding=7)
        style.map('Treeview', background=[('selected', '#40586e')], foreground=[('selected', '#ffffff')])
        root.option_add('*TCombobox*Listbox.background', '#202225')
        root.option_add('*TCombobox*Listbox.foreground', '#f2f3f4')

        section_bar = ttk.Frame(root)
        section_bar.pack(fill='x', padx=16, pady=(10, 4))
        ttk.Label(section_bar, text='Раздел').pack(side='left', padx=(0, 8))
        self.section = ttk.Combobox(section_bar, values=tuple(SECTIONS.values()), state='readonly', width=14)
        self.section.current(0)
        self.section.pack(side='left')
        self.section.bind('<<ComboboxSelected>>', self.change_section)

        ttk.Separator(root).pack(fill='x', padx=16, pady=10)
        self.form = ttk.Frame(root)
        self.form.pack(fill='x', padx=16)

        actions = ttk.Frame(root)
        actions.pack(fill='x', padx=16, pady=12)
        for column, (label, command) in enumerate((
            ('Поиск', self.search), ('Добавить', lambda: self.save()),
            ('Изменить', self.edit), ('Удалить', self.delete),
            ('Очистить', self.clear),
        )):
            button_style = 'Search.TButton' if column == 0 else 'TButton'
            ttk.Button(actions, text=label, command=command, style=button_style).grid(
                row=0, column=column, sticky='ew', padx=(0 if column == 0 else 8, 0))
            actions.columnconfigure(column, weight=1, uniform='actions')

        self.grid = ttk.Treeview(root, show='headings', selectmode='browse')
        self.grid.pack(fill='both', expand=True, padx=16)
        self.grid.bind('<<TreeviewSelect>>', self.select_row)

        self.status = tk.StringVar(value='Подключение к PostgreSQL…')
        ttk.Label(root, textvariable=self.status).pack(fill='x', padx=16, pady=7)
        self.open_section('main')
        root.after_idle(self.connect_db)

    def connect_db(self):
        try:
            self.connection = database.connect_db()
        except Exception as error:
            self.status.set('Нет подключения к PostgreSQL')
            messagebox.showerror('Подключение', str(error))
            return
        self.open_section(self.table)

    def change_section(self, _event):
        self.open_section(tuple(SECTIONS)[self.section.current()])

    def open_section(self, table):
        self.table = table
        self.section.set(SECTIONS[table])
        for widget in self.form.winfo_children():
            widget.destroy()
        self.fields = {}
        self.options = {}
        fields = CONTACT_FIELDS if table == 'main' else {
            database.LOOKUP_COLUMNS[table]: CONTACT_FIELDS[table],
        }
        columns = ('id', *fields)
        self.grid['columns'] = columns
        self.grid.heading('id', text='Код')
        self.grid.column('id', width=60, minwidth=55, stretch=False, anchor='center')
        for column, label in fields.items():
            self.grid.heading(column, text=label)
            width = 75 if column in ('bldn', 'bldn_k', 'appr') else 125
            self.grid.column(column, width=width, minwidth=65)

        try:
            for index, (column, label) in enumerate(fields.items()):
                row, position = divmod(index, 7)
                if row == 0:
                    self.form.columnconfigure(position, weight=2 if position < 4 else 1)
                box = ttk.Frame(self.form)
                box.grid(row=row, column=position, padx=(0, 8), pady=(0, 8), sticky='ew')
                ttk.Label(box, text=label).pack(anchor='w', pady=(0, 4))
                if column in database.LOOKUP_COLUMNS:
                    field = ttk.Combobox(box, width=12,
                                         postcommand=lambda name=column: self.refresh_options(name))
                    ttk.Button(box, text='…', width=2, command=lambda name=column: self.open_section(name)).pack(
                        side='right', padx=(4, 0))
                else:
                    field = ttk.Entry(box, width=10 if table == 'main' else 24)
                field.pack(fill='x')
                self.fields[column] = field
                if column in database.LOOKUP_COLUMNS:
                    self.refresh_options(column)
        except Exception as error:
            self.grid.delete(*self.grid.get_children())
            self.rows = {}
            self.fields = {}
            self.status.set('Не удалось загрузить справочники')
            messagebox.showerror('Ошибка', str(error))
            return

        self.load_table()

    def refresh_options(self, column):
        field = self.fields[column]
        text = field.get()
        index = field.current()
        selected = self.options[column][index][0] if index >= 0 else None
        try:
            rows = database.load_options(self.connection, column) if self.connection else []
        except Exception as error:
            messagebox.showerror('Справочник', str(error))
            rows = self.options.get(column, [])[1:]

        names = Counter(value for _, value in rows)
        labels = ['']
        for key, value in rows:
            if not value:
                value = f'Код {key}'
            elif names[value] > 1:
                value = f'{value} ({key})'
            labels.append(value)

        self.options[column] = [(None, None)] + rows
        field['values'] = labels
        ids = [key for key, _ in self.options[column]]
        if selected is not None and selected in ids:
            field.current(ids.index(selected))
        else:
            field.set(text)

    def form_values(self):
        values = {}
        for column, field in self.fields.items():
            value = field.get().strip() or None
            if column in self.options:
                index = field.current()
                if index >= 0:
                    value = self.options[column][index][0]
            values[column] = value
        return values

    def load_table(self, filters=None):
        self.grid.delete(*self.grid.get_children())
        self.rows = {}
        if not self.connection:
            return
        try:
            rows = database.load_rows(self.connection, self.table, filters or {})
        except Exception as error:
            self.status.set('Не удалось загрузить записи')
            messagebox.showerror('Ошибка', str(error))
            return

        for row in rows:
            key = str(row[0])
            self.rows[key] = row
            shown = row[:9] if self.table == 'main' else row
            self.grid.insert('', 'end', iid=key, values=['' if value is None else value for value in shown])
        self.status.set(f'Строк в таблице: {len(rows)} (до 1000)')

    def select_row(self, _event):
        selected = self.grid.selection()
        if not selected:
            return
        row = self.rows[selected[0]]
        if self.table == 'main':
            # последние четыре значения — id для выпадающих списков
            values = row[9:] + row[5:9]
        else:
            values = row[1:]
        for (column, field), value in zip(self.fields.items(), values):
            if column in self.options:
                ids = [key for key, _ in self.options[column]]
                if value not in ids:
                    self.refresh_options(column)
                    ids = [key for key, _ in self.options[column]]
                field.current(ids.index(value) if value in ids else 0)
            else:
                field.delete(0, 'end')
                if value is not None:
                    field.insert(0, str(value))

    def search(self):
        if self.fields:
            self.load_table(self.form_values())

    def clear(self):
        self.grid.selection_remove(self.grid.selection())
        for column, field in self.fields.items():
            if column in self.options:
                field.current(0)
            else:
                field.delete(0, 'end')
        self.load_table()

    def edit(self):
        selected = self.grid.selection()
        if not selected:
            messagebox.showwarning('Изменение', 'Выберите запись в таблице')
            return
        self.save(selected[0])

    def save(self, key=None):
        if not self.connection or not self.fields:
            return
        values = self.form_values()
        if all(value is None for value in values.values()):
            messagebox.showwarning('Поля записи', 'Заполните хотя бы одно поле')
            return
        try:
            if key is None:
                database.insert_row(self.connection, self.table, values)
            else:
                database.update_row(self.connection, self.table, values, key)
        except Exception as error:
            messagebox.showerror('Ошибка', str(error))
            return
        self.clear()

    def delete(self):
        selected = self.grid.selection()
        if not selected:
            messagebox.showwarning('Удаление', 'Выберите запись в таблице')
            return
        key = selected[0]
        if not messagebox.askyesno('Удаление', f'Удалить запись с кодом {key}?'):
            return
        try:
            database.delete_row(self.connection, self.table, key)
        except Exception as error:
            messagebox.showerror('Ошибка', str(error))
            return
        self.clear()


if __name__ == '__main__':
    root = tk.Tk()
    DatabaseClient(root)
    root.mainloop()
