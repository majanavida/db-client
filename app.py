import tkinter as tk
from tkinter import messagebox, ttk

import database


class DatabaseClient:
    def __init__(self, root):
        root.title('Клиент PostgreSQL')
        root.geometry('1050x700')
        self.connection = None
        self.editors = {}

        connection_frame = ttk.LabelFrame(root, text='Подключение')
        connection_frame.pack(fill='x', padx=10, pady=8)
        self.connection_fields = {}
        for index, (name, default) in enumerate((
            ('Хост', 'localhost'), ('Порт', '5432'), ('База данных', ''),
            ('Пользователь', ''), ('Пароль', ''),
        )):
            ttk.Label(connection_frame, text=name).grid(row=0, column=index * 2, padx=4, pady=6)
            field = ttk.Entry(connection_frame, width=16, show='*' if name == 'Пароль' else '')
            field.insert(0, default)
            field.grid(row=0, column=index * 2 + 1, padx=4, pady=6)
            self.connection_fields[name] = field
        ttk.Button(connection_frame, text='Подключиться', command=self.connect_db).grid(
            row=0, column=10, padx=6)

        toolbar = ttk.Frame(root)
        toolbar.pack(fill='x', padx=10, pady=4)
        ttk.Label(toolbar, text='Таблица:').pack(side='left', padx=(0, 5))
        self.table_box = ttk.Combobox(toolbar, values=tuple(database.TABLE_IDS), state='readonly', width=14)
        self.table_box.current(0)
        self.table_box.pack(side='left', padx=4)
        self.table_box.bind('<<ComboboxSelected>>', self.change_table)
        for title, command in (
            ('Обновить', self.load_table), ('Добавить', self.add_row),
            ('Сохранить', self.save_row), ('Удалить', self.delete_row),
        ):
            ttk.Button(toolbar, text=title, command=command).pack(side='left', padx=4)

        search_bar = ttk.Frame(root)
        search_bar.pack(fill='x', padx=10, pady=4)
        ttk.Label(search_bar, text='Искать по полю:').pack(side='left')
        self.search_column = ttk.Combobox(search_bar, state='readonly', width=14)
        self.search_column.pack(side='left', padx=4)
        self.search_entry = ttk.Entry(search_bar, width=28)
        self.search_entry.pack(side='left', padx=4)
        self.search_entry.bind('<Return>', self.load_table)
        ttk.Button(search_bar, text='Найти', command=self.load_table).pack(side='left', padx=4)
        ttk.Button(search_bar, text='Сбросить поиск', command=self.reset_search).pack(side='left', padx=4)

        table_frame = ttk.Frame(root)
        table_frame.pack(fill='both', expand=True, padx=10, pady=6)
        self.grid = ttk.Treeview(table_frame, show='headings', selectmode='browse')
        vertical_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.grid.yview)
        horizontal_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.grid.xview)
        self.grid.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)
        self.grid.grid(row=0, column=0, sticky='nsew')
        vertical_scroll.grid(row=0, column=1, sticky='ns')
        horizontal_scroll.grid(row=1, column=0, sticky='ew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.grid.bind('<<TreeviewSelect>>', self.select_row)

        self.form = ttk.LabelFrame(root, text='Поля записи')
        self.form.pack(fill='x', padx=10, pady=6)
        self.status = tk.StringVar(value='Укажите параметры подключения')
        ttk.Label(root, textvariable=self.status, anchor='w').pack(fill='x', padx=10, pady=(0, 8))

    def connect_db(self):
        try:
            values = {name: field.get().strip() for name, field in self.connection_fields.items()}
            connection = database.connect(
                host=values['Хост'], port=values['Порт'], dbname=values['База данных'],
                user=values['Пользователь'], password=self.connection_fields['Пароль'].get(),
            )
            if self.connection:
                self.connection.close()
            self.connection = connection
            self.change_table()
        except Exception as error:
            messagebox.showerror('Ошибка', str(error))

    def change_table(self, _event=None):
        self.search_column.set('')
        self.reset_search()

    def reset_search(self):
        self.search_entry.delete(0, 'end')
        self.load_table()

    def load_table(self, _event=None):
        if not self.connection:
            return
        table = self.table_box.get()
        search_column = self.search_column.get()
        term = self.search_entry.get().strip()
        self.grid.delete(*self.grid.get_children())
        self.clear_form()
        try:
            columns, rows = database.load_rows(self.connection, table, search_column, term)
        except Exception as error:
            self.grid['columns'] = ()
            self.search_column['values'] = ()
            self.search_column.set('')
            self.status.set(f'Не удалось загрузить таблицу {table}')
            messagebox.showerror('Ошибка', str(error))
            return

        self.search_column['values'] = columns
        if not search_column:
            self.search_column.current(0)
        self.grid['columns'] = columns
        for column in columns:
            self.grid.heading(column, text=column)
            self.grid.column(column, width=130, minwidth=70)
        for row in rows:
            self.grid.insert('', 'end', values=tuple('' if value is None else value for value in row))
        action = 'найдено строк' if term and search_column else 'загружено строк'
        self.status.set(f'{table}: {action} — {len(rows)} (максимум 1000)')

    def clear_form(self):
        for child in self.form.winfo_children():
            child.destroy()
        self.editors = {}

    def select_row(self, _event=None):
        selected = self.grid.selection()
        if selected:
            self.show_form(self.grid.set(selected[0]))

    def show_form(self, values=None):
        self.clear_form()
        primary_key = database.TABLE_IDS[self.table_box.get()]
        columns = self.grid['columns']
        if values is None:
            columns = [column for column in columns if column != primary_key]
        for index, column in enumerate(columns):
            ttk.Label(self.form, text=column).grid(row=index // 4 * 2, column=index % 4, sticky='w', padx=6, pady=(5, 0))
            field = ttk.Entry(self.form, width=24)
            if values is not None:
                field.insert(0, values[column])
            if column == primary_key:
                field.configure(state='readonly')
            field.grid(row=index // 4 * 2 + 1, column=index % 4, sticky='ew', padx=6, pady=(0, 5))
            self.editors[column] = field

    def add_row(self):
        if not self.grid['columns']:
            return
        self.grid.selection_remove(self.grid.selection())
        self.show_form()
        self.status.set('Заполните поля новой записи и нажмите «Сохранить»')

    def save_row(self):
        if not self.editors:
            messagebox.showwarning('Нет записи', 'Выберите запись или нажмите «Добавить»')
            return
        table = self.table_box.get()
        primary_key = database.TABLE_IDS[table]
        values = {}
        for column, field in self.editors.items():
            if column != primary_key:
                values[column] = field.get().strip() or None
        try:
            if primary_key in self.editors:
                key = self.editors[primary_key].get()
                database.update_row(self.connection, table, values, key)
            else:
                database.insert_row(self.connection, table, values)
            self.load_table()
        except Exception as error:
            messagebox.showerror('Ошибка', str(error))

    def delete_row(self):
        selected = self.grid.selection()
        if not selected:
            messagebox.showwarning('Нет записи', 'Сначала выберите запись в таблице')
            return
        table = self.table_box.get()
        primary_key = database.TABLE_IDS[table]
        key = self.grid.set(selected[0], primary_key)
        if not messagebox.askyesno('Удалить запись', f'Удалить запись {primary_key}={key}?'):
            return
        try:
            database.delete_row(self.connection, table, key)
            self.load_table()
        except Exception as error:
            messagebox.showerror('Ошибка', str(error))


if __name__ == '__main__':
    root = tk.Tk()
    DatabaseClient(root)
    root.mainloop()
