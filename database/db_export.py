from globals import *
from database.db_tools import db_connect, db_disconnect


#get Products view from DB:
def get_view_prodotti(schema, supplier=None):
    suppstr = ""
    FullList = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        if supplier:
            suppstr = f"WHERE produttore = '{supplier}'"
        query = f"SELECT * FROM {schema}.prodotti {suppstr} ORDER BY produttore, categoria, nome"
        FullList = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"Unable to perform get view Prodotti for supplier: {supplier if supplier else 'all'}. {e}")
    return FullList

#get Order List view from DB:
def get_view_listaordine(schema, codiceord):
    OrdList = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        query = f"SELECT listeordini.codiceprod, prodotti.produttore, prodotti.nome, prodotti.categoria, prodotti.aliquota, listeordini.quantita, prodotti.prezzo, prodotti.costo FROM {schema}.listeordini INNER JOIN {schema}.prodotti ON listeordini.codiceprod = prodotti.codiceprod WHERE listeordini.codiceord = {codiceord} ORDER BY prodotti.produttore, prodotti.categoria, prodotti.nome"
        OrdList = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"Unable to perform get view Lista Ordine for codiceord: {codiceord}. {e}")
    return OrdList

