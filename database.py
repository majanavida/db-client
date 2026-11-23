from configparser import ConfigParser
from pathlib import Path

from psycopg2 import connect, sql


TABLE_IDS = {
    'main': 'u_id',
    'fam': 'f_id',
    'name': 'n_id',
    'otc': 'o_id',
    'street': 's_id',
}


LOOKUP_COLUMNS = {
    'fam': 'f_value',
    'name': 'n_value',
    'otc': 'o_value',
    'street': 's_value',
}


def connect_db():
    config = ConfigParser(interpolation=None)
    config.read(Path(__file__).with_name('database.ini'), encoding='utf-8')
    if 'postgresql' not in config:
        raise ValueError('Укажите параметры подключения в database.ini')
    return connect(**config['postgresql'])


def load_options(connection, table):
    query = sql.SQL('SELECT {}, {} FROM {} ORDER BY {}, {}').format(
        sql.Identifier(TABLE_IDS[table]), sql.Identifier(LOOKUP_COLUMNS[table]),
        sql.Identifier(table), sql.Identifier(LOOKUP_COLUMNS[table]),
        sql.Identifier(TABLE_IDS[table]),
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def load_rows(connection, table, filters):
    if table == 'main':
        query = sql.SQL('''
            SELECT m.u_id, fam.f_value, name.n_value, otc.o_value, street.s_value,
                   m.bldn, m.bldn_k, m.appr, m.telef,
                   m.fam, m.name, m.otc, m.street
            FROM main AS m
            LEFT JOIN fam ON m.fam = fam.f_id
            LEFT JOIN name ON m.name = name.n_id
            LEFT JOIN otc ON m.otc = otc.o_id
            LEFT JOIN street ON m.street = street.s_id
        ''')
    else:
        query = sql.SQL('SELECT {}, {} FROM {} AS m').format(
            sql.Identifier(TABLE_IDS[table]), sql.Identifier(LOOKUP_COLUMNS[table]),
            sql.Identifier(table),
        )

    conditions = []
    params = []
    for column, value in filters.items():
        if value is None:
            continue
        field = sql.Identifier('m', column)
        if column in LOOKUP_COLUMNS and isinstance(value, int):
            conditions.append(sql.SQL('{} = %s').format(field))
        else:
            if column in LOOKUP_COLUMNS:
                field = sql.Identifier(column, LOOKUP_COLUMNS[column])
            conditions.append(sql.SQL('strpos(lower(CAST({} AS text)), lower(%s)) > 0').format(field))
        params.append(value)
    if conditions:
        query += sql.SQL(' WHERE ') + sql.SQL(' AND ').join(conditions)
    query += sql.SQL(' ORDER BY {} LIMIT 1000').format(sql.Identifier('m', TABLE_IDS[table]))
    with connection, connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def contact_values(cursor, table, values):
    if table != 'main':
        return list(values.values())

    result = []
    for column, value in values.items():
        if column in LOOKUP_COLUMNS and isinstance(value, str):
            lookup_table = sql.Identifier(column)
            id_column = sql.Identifier(TABLE_IDS[column])
            text_column = sql.Identifier(LOOKUP_COLUMNS[column])
            cursor.execute(sql.SQL(
                'SELECT {} FROM {} WHERE lower(trim({})) = lower(%s) ORDER BY {} LIMIT 1'
            ).format(id_column, lookup_table, text_column, id_column), (value,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(sql.SQL(
                    'INSERT INTO {} ({}) VALUES (%s) RETURNING {}'
                ).format(lookup_table, text_column, id_column), (value,))
                row = cursor.fetchone()
            value = row[0]
        result.append(value)
    return result


def insert_row(connection, table, values):
    query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
        sql.Identifier(table),
        sql.SQL(', ').join(sql.Identifier(column) for column in values),
        sql.SQL(', ').join(sql.Placeholder() for _ in values),
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(query, contact_values(cursor, table, values))


def update_row(connection, table, values, key):
    query = sql.SQL('UPDATE {} SET {} WHERE {} = %s').format(
        sql.Identifier(table),
        sql.SQL(', ').join(
            sql.SQL('{} = %s').format(sql.Identifier(column)) for column in values
        ),
        sql.Identifier(TABLE_IDS[table]),
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(query, contact_values(cursor, table, values) + [key])
        if cursor.rowcount == 0:
            raise ValueError('Запись больше не существует')


def delete_row(connection, table, key):
    query = sql.SQL('DELETE FROM {} WHERE {} = %s').format(
        sql.Identifier(table), sql.Identifier(TABLE_IDS[table]))
    with connection, connection.cursor() as cursor:
        cursor.execute(query, (key,))
