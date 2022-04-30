from globals import *
from database.db_tools import db_connect, db_disconnect


#get Products view from DB:
def get_view_prodotti(schema, supplier=None):
    suppstr = ""
    FullList = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        if supplier:
            suppstr = f"WHERE prodotti.produttore = '{supplier}'"
        query = f"SELECT prodotti.*, produttori.scontomedio, categorie.aliquota FROM {schema}.prodotti INNER JOIN {schema}.produttori ON prodotti.produttore = produttori.produttore INNER JOIN {schema}.categorie ON prodotti.categoria = categorie.categoria {suppstr} ORDER BY prodotti.produttore, prodotti.categoria, prodotti.nome"
        FullList = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"Unable to perform get view Prodotti for supplier: {supplier if supplier else 'all'}. {e}")
    return FullList

#get Recap view from DB:
def get_view_recap(schema):
    Recap = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        query = f"SELECT produttori.produttore, categorie.categoria, SUM(prodotti.quantita) AS quantita, SUM(prodotti.valoretotale) AS valoretotale, produttori.scontomedio, categorie.aliquota FROM {schema}.produttori INNER JOIN {schema}.prodotti ON prodotti.produttore = produttori.produttore INNER JOIN {schema}.categorie ON prodotti.categoria = categorie.categoria GROUP BY produttori.produttore, categorie.categoria ORDER BY produttori.produttore, categorie.categoria"
        Recap = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"Unable to perform get view Recap from schema {schema}. {e}")
    return Recap

#get Order List view from DB:
def get_view_listaordine(schema, codiceord):
    OrdList = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        query = f"SELECT listeordini.codiceprod, prodotti.produttore, prodotti.nome, prodotti.categoria, listeordini.quantita, prodotti.prezzo, produttori.scontomedio, categorie.aliquota FROM {schema}.listeordini INNER JOIN {schema}.prodotti ON listeordini.codiceprod = prodotti.codiceprod INNER JOIN {schema}.produttori ON prodotti.produttore = produttori.produttore INNER JOIN {schema}.categorie ON prodotti.categoria = categorie.categoria WHERE listeordini.codiceord = {codiceord} ORDER BY prodotti.produttore, prodotti.categoria, prodotti.nome"
        OrdList = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"Unable to perform get view Lista Ordine for codiceord: {codiceord}. {e}")
    return OrdList

