from globals import *

#DB TOOLS (BASICS):
# - db_connect()
# - create_tables()
# - drop_all()
# - empty_table()


#open DB connection:
def db_connect():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()
    except psycopg2.Error as e:
        log.error(e)
    return conn, cursor


#create tables:
def create_tables(conn, cursor):
    #dict of queries:
    queries = {
        'Produttori': f'''CREATE TABLE {SCHEMA}.Produttori (
            Produttore VARCHAR(50) NOT NULL,
            ScontoMedio SMALLINT NOT NULL DEFAULT 0,
            PRIMARY KEY (Produttore)
            )''',

        'Categorie': f'''CREATE TABLE {SCHEMA}.Categorie (
            Categoria VARCHAR(50) NOT NULL,
            Aliquota NUMERIC(3,1) NOT NULL DEFAULT 22,
            PRIMARY KEY (Categoria)
            )''',

        'Prodotti': f'''CREATE TABLE {SCHEMA}.Prodotti (
            CodiceProd BIGINT NOT NULL, 
            Produttore VARCHAR(50) NOT NULL,
            Nome TEXT NOT NULL, 
            Categoria VARCHAR(50) NOT NULL,
            Quantita SMALLINT NOT NULL DEFAULT 0,
            Prezzo NUMERIC(5,2) NOT NULL DEFAULT 0,
            DispMedico BOOLEAN NOT NULL DEFAULT FALSE,
            EtaMinima SMALLINT NOT NULL DEFAULT 18,
            Bio BOOLEAN NOT NULL DEFAULT FALSE,
            Vegano BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaGlutine BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaLattosio BOOLEAN NOT NULL DEFAULT FALSE,
            SenzaZucchero BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (CodiceProd),
            FOREIGN KEY (Produttore) REFERENCES {SCHEMA}.Produttori (Produttore) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (Categoria) REFERENCES {SCHEMA}.Categorie (Categoria) ON DELETE CASCADE ON UPDATE CASCADE
            )''',
        
        'StoricoOrdini': f'''CREATE TABLE {SCHEMA}.StoricoOrdini (
            CodiceOrd VARCHAR(10) NOT NULL,
            Produttore VARCHAR(50) NOT NULL,
            Riferimento TEXT,
            DataModifica VARCHAR(10) NOT NULL,
            DataInoltro VARCHAR(10),
            DataRicezione VARCHAR(10),
            PRIMARY KEY (CodiceOrd)
            )''',
            
        'ListeOrdini': f'''CREATE TABLE {SCHEMA}.ListeOrdini (
            ID SERIAL NOT NULL,
            CodiceOrd VARCHAR(10) NOT NULL, 
            CodiceProd BIGINT NOT NULL,
            Quantita SMALLINT NOT NULL DEFAULT 1,
            PRIMARY KEY (ID),
            FOREIGN KEY (CodiceOrd) REFERENCES {SCHEMA}.StoricoOrdini (CodiceOrd) ON DELETE CASCADE ON UPDATE CASCADE
            )'''
    }

    #execute:
    #1) create schema:
    try:
        cursor.execute(f"CREATE SCHEMA {SCHEMA}")
        conn.commit()
        log.info(f"Created schema {SCHEMA}.")
    except psycopg2.Error as e:
        log.error(f"Unable to create schema {SCHEMA}. {e}")
        return -1

    for t in queries.keys():
        try:
            cursor.execute(queries[t])
            conn.commit()
            log.info(f"Created table {t}.")
        except psycopg2.Error as e:
            log.error(f"Unable to create table {t}. {e}")
    return 0


#drop all tables in the schema (in globals):
def drop_all(conn, cursor):
    try:
        query = f"DROP SCHEMA {SCHEMA} CASCADE"
        cursor.execute(query)
        conn.commit()
        log.info(f"Dropped schema {SCHEMA}.")
        return 0
    except psycopg2.Error as e:
        log.error(f"Unable to drop schema {SCHEMA}.")
        return -1


#empty a specific table:
def empty_table(tablename, conn, cursor):
    try:
        query = f"DELETE FROM {SCHEMA}.{tablename}"
        cursor.execute(query)
        conn.commit()
        log.info(f"Table {SCHEMA}.{tablename} successfully reset.")
        return 0
    except psycopg2.Error as e:
        log.error(f"ERROR: unable to reset {SCHEMA}.{tablename} table.")
        return -1
