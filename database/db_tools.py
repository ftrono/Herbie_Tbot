from globals import *

#DB TOOLS (BASICS):
# - db_connect()
# - create_dbo_tables()
# - create_schema_tables()
# - empty_table()
# - drop_table()
# - drop_schema()


#open DB connection:
def db_connect():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
    except psycopg2.Error as e:
        dlog.error(e)
    return conn, cursor

#close DB connection:
def db_disconnect(conn, cursor):
    try:
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        dlog.error(e)

#create dbo tables:
def create_dbo_tables(conn, cursor):
    #dict of queries:
    queries = {
        'Schemi': f'''CREATE TABLE Schemi (
            NomeSchema VARCHAR(20) UNIQUE NOT NULL,
            HashOTP BYTEA NOT NULL,
            PRIMARY KEY (NomeSchema)
            )''',

        'Utenti': f'''CREATE TABLE Utenti (
            ID SERIAL NOT NULL,
            ChatID BIGINT NOT NULL,
            NomeSchema VARCHAR(20) NOT NULL,
            PRIMARY KEY (ID),
            FOREIGN KEY (NomeSchema) REFERENCES Schemi (NomeSchema) ON DELETE CASCADE ON UPDATE CASCADE
            )'''}

    #create:  
    for t in queries.keys():
        try:
            cursor.execute(queries[t])
            conn.commit()
            dlog.info(f"Created table {t}.")
        except psycopg2.Error as e:
            dlog.error(f"Unable to create table {t}. {e}")
    return 0

#create tables:
def create_schema_tables(conn, cursor, schema):
    #dict of queries:
    queries = {
        'Prodotti': f'''CREATE TABLE {schema}.Prodotti (
            CodiceProd BIGINT NOT NULL, 
            Produttore VARCHAR(50) NOT NULL,
            Nome TEXT NOT NULL, 
            Categoria VARCHAR(50) NOT NULL,
            Aliquota NUMERIC(3,1) NOT NULL DEFAULT 22,
            Prezzo NUMERIC(5,2) NOT NULL DEFAULT 0,
            Costo NUMERIC(5,2) NOT NULL DEFAULT 0,
            Quantita SMALLINT NOT NULL DEFAULT 0,
            ValoreTotale DECIMAL (8, 2) GENERATED ALWAYS AS (Prezzo * Quantita) STORED,
            CostoTotale DECIMAL (8, 2) GENERATED ALWAYS AS (Costo * Quantita) STORED,
            DispMedico BOOLEAN NOT NULL DEFAULT FALSE,
            Vegano BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaLattosio BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaGlutine BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaZucchero BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (CodiceProd)
            )''',
        
        'StoricoOrdini': f'''CREATE TABLE {schema}.StoricoOrdini (
            CodiceOrd BIGINT NOT NULL,
            Produttore VARCHAR(50) NOT NULL,
            DataModifica VARCHAR(10) NOT NULL,
            Definitiva BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (CodiceOrd)
            )''',
        
        'ListeOrdini': f'''CREATE TABLE {schema}.ListeOrdini (
            ID SERIAL NOT NULL,
            CodiceOrd BIGINT NOT NULL, 
            CodiceProd BIGINT NOT NULL,
            Quantita SMALLINT NOT NULL DEFAULT 1,
            PRIMARY KEY (ID),
            FOREIGN KEY (CodiceOrd) REFERENCES {schema}.StoricoOrdini (CodiceOrd) ON DELETE CASCADE ON UPDATE CASCADE
            )'''
    }

    #execute:
    #1) create schema:
    try:
        cursor.execute(f"CREATE SCHEMA {schema}")
        conn.commit()
        dlog.info(f"Created schema {schema}.")
    except psycopg2.Error as e:
        dlog.error(f"Unable to create schema {schema}. {e}")
        return -1

    #2) create tables for the schema:
    for t in queries.keys():
        try:
            cursor.execute(queries[t])
            conn.commit()
            dlog.info(f"Created table {schema}.{t}.")
        except psycopg2.Error as e:
            dlog.error(f"Unable to create table {schema}.{t}. {e}")
    return 0

#empty a specific table:
def empty_table(conn, cursor, tablename, schema=None):
    loc = f"{schema}." if schema else ""
    try:
        query = f"DELETE FROM {loc}{tablename}"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Table {loc}{tablename} successfully reset.")
        return 0
    except psycopg2.Error as e:
        dlog.error(f"ERROR: unable to reset {loc}{tablename} table.")
        return -1

#drop a specific table:
def drop_table(conn, cursor, tablename, schema=None):
    loc = f"{schema}." if schema else ""
    try:
        query = f"DROP TABLE {loc}{tablename}"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Dropped table {loc}{tablename}.")
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to drop table {loc}{tablename}.")
        return -1

#drop all tables in a schema:
def drop_schema(conn, cursor, schema):
    try:
        query = f"DELETE FROM Schemi WHERE NomeSchema = '{schema}'"
        cursor.execute(query)
        query = f"DROP SCHEMA {schema} CASCADE"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Dropped schema {schema}.")
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to drop schema {schema}.")
        return -1
