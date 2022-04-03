from globals import *

#DB TOOLS (BASICS):
# - db_connect()
# - create_tables()
# - drop_all()
# - empty_table()


#open DB connection:
def db_connect():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("PRAGMA foreign_keys = 1")
        cursor = conn.cursor()
    except sqlite3.Error as e:
        log.error(e)
    return conn, cursor


#create tables:
def create_tables(conn, cursor):
    #dict of queries:
    queries = {
        'Prodotti': '''CREATE TABLE Prodotti (
            CodiceProd INTEGER PRIMARY KEY, 
            Produttore TEXT NOT NULL,
            Nome TEXT NOT NULL, 
            Categoria TEXT NOT NULL,
            Quantita INTEGER NOT NULL DEFAULT 0,
            Prezzo REAL NOT NULL DEFAULT 0,
            ScontoMedio REAL NOT NULL DEFAULT 0,
            Aliquota REAL NOT NULL DEFAULT 0.22,
            Scaffale TEXT,
            DispMedico INTEGER NOT NULL DEFAULT 0,
            EtaMinima INTEGER NOT NULL DEFAULT 18,
            Bio INTEGER NOT NULL DEFAULT 0,
            Vegano INTEGER NOT NULL DEFAULT 0,
            SenzaGlutine INTEGER NOT NULL DEFAULT 0,
            SenzaLattosio INTEGER NOT NULL DEFAULT 0,
            SenzaZucchero INTEGER NOT NULL DEFAULT 0
            )''',
        
        'StoricoOrdini': '''CREATE TABLE StoricoOrdini (
            CodiceOrd INTEGER PRIMARY KEY,
            Produttore TEXT NOT NULL,
            Riferimento TEXT,
            DataModifica TEXT NOT NULL,
            DataInoltro TEXT,
            DataRicezione TEXT
            )''',
            
        'ListeOrdini': '''CREATE TABLE ListeOrdini (
            ID INTEGER PRIMARY KEY,
            CodiceOrd INTEGER NOT NULL, 
            CodiceProd INTEGER NOT NULL, 
            Quantita INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (CodiceOrd) REFERENCES StoricoOrdini (CodiceOrd) ON DELETE CASCADE ON UPDATE CASCADE
            )''',

        'ComponentiAmbiti': '''CREATE TABLE ComponentiAmbiti (
            ID INTEGER PRIMARY KEY,
            Componente TEXT NOT NULL,
            AmbitoUtilizzo TEXT NOT NULL,
            DettaglioAmbito TEXT
            )''',

        'ComponentiProdotto': '''CREATE TABLE ComponentiProdotto (
            ID INTEGER PRIMARY KEY,
            CodiceProd INTEGER NOT NULL, 
            Componente TEXT NOT NULL,
            FOREIGN KEY (CodiceProd) REFERENCES Prodotti (CodiceProd) ON DELETE CASCADE ON UPDATE CASCADE
            )''',
    }

    #execute:
    for t in queries.keys():
        try:
            cursor.execute(queries[t])
            conn.commit()
            log.info(f"Created table {t}.")
        except:
            log.error(f"Unable to create table {t}.")
    return 0


#drop all tables:
def drop_all(conn, cursor):
    #ordered list of tables:
    tables = ['ComponentiProdotto', 'ComponentiAmbiti', 'ListeOrdini', 'StoricoOrdini', 'Prodotti']
    #execute:
    for t in tables:
        try:
            query = 'DROP TABLE '+ t
            cursor.execute(query)
            conn.commit()
            log.info(f"Dropped table {t}.")
        except:
            log.error(f"Unable to drop table {t}.")
    return 0


#empty a specific table:
def empty_table(tablename, conn, cursor):
    try:
        query = "DELETE FROM "+tablename
        cursor.execute(query)
        conn.commit()
        log.info("Table "+tablename+" successfully reset.")
    except:
        log.error("ERROR: unable to reset "+tablename+" table.")
    return 0


#MAIN:
if __name__ == '__main__':
    conn, cursor = db_connect()
    drop_all(conn, cursor)
    create_tables(conn, cursor)
    conn.close()
