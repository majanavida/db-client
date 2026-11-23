from psycopg2 import connect, sql


TABLE_IDS = {
    'main': 'u_id',
    'fam': 'f_id',
    'name': 'n_id',
    'otc': 'o_id',
    'street': 's_id',
}


def load_rows(connection, table, search_column, term):
    query = sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))
    params = ()
    if term and search_column:
        query += sql.SQL(' WHERE strpos(lower(CAST({} AS text)), lower(%s)) > 0').format(
            sql.Identifier(search_column))
        params = (term,)
    query += sql.SQL(' ORDER BY {} LIMIT 1000').format(sql.Identifier(TABLE_IDS[table]))
    with connection, connection.cursor() as cursor:
        cursor.execute(query, params)
        columns = [column.name for column in cursor.description]
        return columns, cursor.fetchall()


def insert_row(connection, table, values):
    query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
        sql.Identifier(table),
        sql.SQL(', ').join(sql.Identifier(column) for column in values),
        sql.SQL(', ').join(sql.Placeholder() for _ in values),
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(query, list(values.values()))


def update_row(connection, table, values, key):
    query = sql.SQL('UPDATE {} SET {} WHERE {} = %s').format(
        sql.Identifier(table),
        sql.SQL(', ').join(
            sql.SQL('{} = %s').format(sql.Identifier(column)) for column in values
        ),
        sql.Identifier(TABLE_IDS[table]),
    )
    with connection, connection.cursor() as cursor:
        cursor.execute(query, list(values.values()) + [key])


def delete_row(connection, table, key):
    query = sql.SQL('DELETE FROM {} WHERE {} = %s').format(
        sql.Identifier(table), sql.Identifier(TABLE_IDS[table]))
    with connection, connection.cursor() as cursor:
        cursor.execute(query, (key,))
