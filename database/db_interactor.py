from globals import *
from database.db_tools import db_connect

#DB_INTERACTOR:
#Low-level DB interfaces:
# - get_column()
# - get_prodinfo()
# - add_prod()
# - delete_prod()
# - get_view_prodotti()


#get all items in a column of Prodotti table:
def get_auths(chat_id):
    try:
        conn, cursor = db_connect()
        query = f"SELECT nomeutente, autorizzazione FROM utenti WHERE chatid = {int(chat_id)}"
        auths = pd.read_sql(query, conn)
        #select only first word in name:
        nome = auths['nomeutente'].iloc[0]
        nome = nome.split()
        nome = nome[0]
        #list of auths:
        auths = auths['autorizzazione'].to_list()
        conn.close()
    except:
        nome = ""
        auths = []
        log.error(f"DB query error for Utenti.")
    return nome, auths

#get all items in a column of Prodotti table:
def get_column(schema, column_name):
    try:
        conn, cursor = db_connect()
        query = f"SELECT DISTINCT {column_name} FROM {schema}.prodotti"
        items = pd.read_sql(query, conn)
        items = items[column_name].to_list()
        conn.close()
    except:
        items = []
        log.error(f"DB query error for all '{column_name}' items.")
    return items


#get basic product info:
def get_product(conn, schema, p_code):
    Prodotto = pd.DataFrame()
    try:
        #extract the matching product (direct match):
        query = f"SELECT codiceprod, produttore, nome, categoria, quantita FROM {schema}.prodotti WHERE codiceprod = {p_code}"
        Prodotto = pd.read_sql(query, conn)
    except psycopg2.Error as e:
        log.error(f"DB query error for 'p_code'. {e}")
    return Prodotto


#add a new product:
def add_prod(conn, cursor, schema, info):
    try:
        query = f"INSERT INTO {schema}.prodotti (codiceprod, produttore, nome, categoria, quantita) VALUES ({info['p_code']}, '{info['supplier']}', '{info['p_name']}', '{info['category']}', {info['pieces']})"
        cursor.execute(query)
        conn.commit()
        log.info(f"Added product {info['p_code']} to table prodotti.")
        return 0
    except psycopg2.Error as e:
        log.error(f"Unable to add product {info['p_code']} to table prodotti. {e}")
        return -1


#delete a product:
def delete_prod(conn, cursor, schema, p_code):
    try:
        query = f"DELETE FROM {schema}.prodotti WHERE codiceprod = {p_code}"
        cursor.execute(query)
        conn.commit()
        log.info(f"Deleted product {p_code} from DB.")
        return 0
    except psycopg2.Error as e:
        log.error(f"Unable to delete product {p_code} from DB. {e}")
        return -1


#get list of products from DB:
def get_view_prodotti(conn, schema, supplier=None):
    suppstr = ""
    FullList = pd.DataFrame()
    try:
        if supplier:
            suppstr = f" WHERE produttore = {supplier}"
        query = f"SELECT * FROM {schema}.prodotti{suppstr}"
        FullList = pd.read_sql(query, conn)
    except psycopg2.Error as e:
        log.error(f"Unable to perform get_suggestion_list for supplier {supplier}. {e}")
    return FullList

