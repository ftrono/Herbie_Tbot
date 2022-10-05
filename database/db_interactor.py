from globals import *
from database.db_tools import db_connect, db_disconnect

#DB_INTERACTOR:
#Low-level DB interfaces:
# - get_auths()
# - register_auth()
# - get_column()
# - match_product()
# - add_prod()
# - register_prodinfo()
# - add_detail()
# - get_storicoordini()
# - delete_prod()
# - clean_db()


#get all items in a column of Prodotti table:
def get_auths(schema, chat_id):
    try:
        conn, cursor = db_connect()
        query = f"SELECT * FROM utenti WHERE chatid = {int(chat_id)} AND nomeschema = '{schema}'"
        auths = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
        if auths.empty == True:
            return -1
        else:
            return 0
    except Exception as e:
        dlog.error(f"get_auths(): DB query error for Utenti. {e}")
        return -1


#register new user authorization:
def register_auth(schema, chat_id, otp):
    try:
        conn, cursor = db_connect()
        #1) query for Schema corresponding to the OTP:
        query = f"SELECT * FROM schemi WHERE nomeschema = '{schema}' AND hashotp = sha224('{otp}')"
        match = pd.read_sql(query, conn)
        #2) register user auth for the Schema:
        if match.empty == False:
            #check if user already registered to the schema:
            query = F"SELECT * FROM utenti WHERE nomeschema = '{schema}' AND ChatID = {chat_id}"
            match = pd.read_sql(query, conn)
            if match.empty == True:
                query = f"INSERT INTO utenti (ChatID, nomeschema) VALUES ({chat_id}, '{schema}')"
                dlog.info(f"register_auth(): Added authorization for user {chat_id} to Schema: {schema}")
            else:
                dlog.info(f"register_auth(): User {chat_id} already registered to Schema: {schema}")
            cursor.execute(query)
            conn.commit()
        db_disconnect(conn, cursor)
        return 0
    except Exception as e:
        dlog.error(f"register_auth(): DB query error in registering user {chat_id}. {e}")
        return -1


#get all suppliers, categories or items in a column of the Prodotti table:
def get_column(schema, column_name):
    try:
        conn, cursor = db_connect()
        query = f"SELECT DISTINCT {column_name} FROM {schema}.prodotti"
        items = pd.read_sql(query, conn)
        items = items[column_name].to_list()
        db_disconnect(conn, cursor)
    except Exception as e:
        items = []
        dlog.error(f"get_column(): DB query error for all '{column_name}' items for schema {schema}. {e}")
    return items


#find matching product and get info (ret -> DataFrame):
def match_product(schema, p_code=None, p_text=None):
    Prodotti = pd.DataFrame()
    if not p_code and not p_text:
        dlog.error("match_product(): no args for query.")
        return Prodotti
    
    #a) if p_code is available -> directly extract the matching product (direct match):
    if p_code != None:
        p_code = int(p_code)
        try:
            conn, cursor = db_connect()
            query = f"SELECT * FROM {schema}.prodotti WHERE codiceprod = '{p_code}'"
            Prodotti = pd.read_sql(query, conn)
            db_disconnect(conn, cursor)
        except Exception as e:
            dlog.error(f"match_product(): DB query error for 'p_code'. {e}")
        return Prodotti
    
    #b) tokenize p_text to extract p_name and find best matches in DB:
    else:
        try:
            conn, cursor = db_connect()
            query = f"SELECT * FROM {schema}.prodotti"
            Prodotti = pd.read_sql(query, conn)
            db_disconnect(conn, cursor)
        except Exception as e:
            dlog.error(f"match_product(): DB query error for 'p_code'. {e}")
            return Prodotti
        
        #count matches for each name:
        p_text = p_text.strip()
        tokens = p_text.split()
        matches = {}
        for ind in Prodotti.index:
            cnt = 0
            missed = 0
            name = []
            #search jointly in columns supplier and name:
            name = Prodotti['produttore'].iloc[ind].split()
            name = name + Prodotti['nome'].iloc[ind].split()
            for tok in tokens:
                if tok in name:
                    cnt = cnt+1
                else:
                    missed = missed+1
                    #max 3 consecutive missed:
                    if cnt <=1 and missed == 3:
                        break
            if cnt >= 1:
                matches[ind] = cnt
        
        #fiter the dict keeping only the 3 items with the maximum frequency found:
        matches = dict(filter(lambda elem: elem[1] == max(matches.values()), matches.items()))
        Matches = Prodotti.iloc[list(matches.keys())[0:3]]
        Matches.reset_index(drop=True, inplace=True)
        return Matches


#add a new product to DB:
def add_prod(schema, info):
    try:
        conn, cursor = db_connect()
        query = f"INSERT INTO {schema}.prodotti (codiceprod, produttore, nome, categoria, aliquota, prezzo, costo, quantita, dispmedico) VALUES ('{info['p_code']}', '{info['supplier']}', '{info['p_name']}', '{info['category']}', {info['vat']}, {info['price']}, {info['cost']}, {info['pieces']}, {info['dispmedico']})"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"add_prod(): Added product {info['p_code']} to table {schema}.prodotti.")
        db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.warning(f"add_prod(): Product {info['p_code']} already existing in table {schema}.prodotti, or other exception. {e}")
        return -1


#add a new product or update basic product info:
def register_prodinfo(schema, info):
    try:
        #1) try to insert the new product to the DB:
        ret = add_prod(schema, info)

        #2) if adding fails -> product already existing, so update prod info in the DB instead:
        if ret == -1:
            try:
                conn, cursor = db_connect()
                query = f"UPDATE {schema}.prodotti SET produttore = '{info['supplier']}', nome = '{info['p_name']}', categoria = '{info['category']}', aliquota = {info['vat']}, prezzo = {info['price']}, costo = {info['cost']}, quantita = {info['pieces']}, dispmedico = {info['dispmedico']} WHERE codiceprod = '{info['p_code']}'"
                cursor.execute(query)
                conn.commit()
                dlog.info(f"register_prodinfo(): Updated basic info for product {info['p_code']} in table {schema}.prodotti.")
                ret = 0
                db_disconnect(conn, cursor)
            except psycopg2.Error as e:
                dlog.error(f"register_prodinfo(): Unable to update basic info for product {info['p_code']} in table {schema}.prodotti. {e}")
                ret = -1
        
    except psycopg2.Error as e:
        dlog.error(f"register_prodinfo(): Unable to update basic info for product {info['p_code']} in table {schema}.prodotti. {e}")
    return ret


#add a detail info for a product:
def add_detail(schema, p_code, colname, value):
    try:
        #if a product is vegan, it does not have lactose -> auto update senzalattosio:
        if colname == 'vegano' and value == True:
            addstr = f", senzalattosio = TRUE "
        else:
            addstr = ""
        #set values:
        conn, cursor = db_connect()
        query = f"UPDATE {schema}.prodotti SET {colname} = {value}{addstr} WHERE codiceprod = '{p_code}'"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"add_detail(): Set {colname} = {value}{addstr} for product {p_code} in table {schema}.prodotti.")
        db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.error(f"add_detail(): Unable to update detail for product {p_code} in table {schema}.prodotti. {e}")
        return -1


#get Storico Ordini from DB:
def get_storicoordini(schema):
    History = pd.DataFrame()
    try:
        conn, cursor = db_connect()
        query = f"SELECT * FROM {schema}.storicoordini ORDER BY datamodifica DESC"
        History = pd.read_sql(query, conn)
        db_disconnect(conn, cursor)
    except psycopg2.Error as e:
        dlog.error(f"get_storicoordini(): Unable to perform get Storico Ordini from schema {schema}. {e}")
    return History


#delete a product from DB:
def delete_prod(schema, p_code):
    try:
        conn, cursor = db_connect()
        query = f"DELETE FROM {schema}.prodotti WHERE codiceprod = '{p_code}'"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"delete_prod(): Deleted product {p_code} from table {schema}.prodotti.")
        db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.error(f"delete_prod(): Unable to delete product {p_code} from table {schema}.prodotti. {e}")
        return -1


#delete a product from DB:
def clean_db(schema):
    try:
        conn, cursor = db_connect()

        #1) clean table Prodotti from items with zero pieces:
        query = f"DELETE FROM {schema}.prodotti WHERE quantita = 0"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"clean_db(): Cleaned table {schema}.prodotti.")

        db_disconnect(conn, cursor)
        return 0

    except psycopg2.Error as e:
        dlog.error(f"clean_db(): Unable to clean tables in schema {schema} in the DB. {e}")
        return -1
