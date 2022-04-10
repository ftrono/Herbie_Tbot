from globals import *
from database.db_tools import db_connect, db_disconnect

#DB_INTERACTOR:
#Low-level DB interfaces:
# - get_auths()
# - register_auth()
# - get_column()
# - match_product()
# - add_prod()
# - delete_prod()
# - get_view_prodotti()


#get all items in a column of Prodotti table:
def get_auths(chat_id):
    try:
        conn, cursor = db_connect()
        query = f"SELECT nomeschema FROM utenti WHERE chatid = {int(chat_id)}"
        auths = pd.read_sql(query, conn)
        auths = auths['nomeschema'].unique().tolist()
        db_disconnect(conn, cursor)
    except:
        auths = []
        dlog.error(f"DB query error for Utenti.")
    return auths


#register new user authorization:
def register_auth(chat_id, otp):
    try:
        conn, cursor = db_connect()
        #1) query for Schema corresponding to the OTP:
        query = f"SELECT nomeschema FROM schemi WHERE hashotp = sha224('{otp}')"
        match = pd.read_sql(query, conn)
        #2) register user auth for the Schema:
        if match.empty == False:
            schema = match['nomeschema'].iloc[0]
            query = f"INSERT INTO utenti (ChatID, nomeschema) VALUES ({chat_id}, '{schema}')"
            dlog.info(f"Added authorization for user {chat_id} to Schema: {schema}")
            cursor.execute(query)
            conn.commit()
        db_disconnect(conn, cursor)
        return schema
    except Exception as e:
        dlog.error(f"DB query error in registering user {chat_id}. {e}")
        return -1


#get all suppliers, categories or items in a column of the Prodotti table:
def get_column(schema, column_name):
    try:
        conn, cursor = db_connect()
        if column_name == 'produttore':
            query = f"SELECT produttore FROM {schema}.produttori"
        elif column_name == 'categoria':
            query = f"SELECT categoria FROM {schema}.categorie"
        else:
            query = f"SELECT DISTINCT {column_name} FROM {schema}.prodotti"
        items = pd.read_sql(query, conn)
        items = items[column_name].to_list()
        db_disconnect(conn, cursor)
    except:
        items = []
        dlog.error(f"DB query error for all '{column_name}' items for schema {schema}.")
    return items


#find matching product and get info (ret -> DataFrame):
def match_product(schema, p_code=None, p_text=None):
    Prodotti = pd.DataFrame()
    if not p_code and not p_text:
        dlog.error("match_product: no args for query.")
        return Prodotti
    
    #a) if p_code is available -> directly extract the matching product (direct match):
    if p_code != None:
        p_code = int(p_code)
        try:
            conn, cursor = db_connect()
            query = f"SELECT * FROM {schema}.prodotti WHERE codiceprod = {p_code}"
            Prodotti = pd.read_sql(query, conn)
            db_disconnect(conn, cursor)
        except Exception as e:
            dlog.error(f"DB query error for 'p_code'. {e}")
        return Prodotti
    
    #b) tokenize p_text to extract p_name and find best matches in DB:
    else:
        try:
            conn, cursor = db_connect()
            query = f"SELECT * FROM {schema}.prodotti"
            Prodotti = pd.read_sql(query, conn)
            db_disconnect(conn, cursor)
        except Exception as e:
            dlog.error(f"DB query error for 'p_code'.")
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


#add a new product:
def add_prod(conn, cursor, schema, info):
    try:
        query = f"INSERT INTO {schema}.prodotti (codiceprod, produttore, nome, categoria, quantita) VALUES ({info['p_code']}, '{info['supplier']}', '{info['p_name']}', '{info['category']}', {info['pieces']})"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Added product {info['p_code']} to table {schema}.prodotti.")
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to add product {info['p_code']} to table {schema}.prodotti. {e}")
        return -1


#add a detail info for a product:
def add_detail(schema, p_code, colname, value):
    try:
        conn, cursor = db_connect()
        query = f"UPDATE {schema}.prodotti SET {colname} = {value} WHERE codiceprod = {p_code}"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Set {colname} = {value} for product {p_code} in table {schema}.prodotti.")
        db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to update detail for product {p_code} in table {schema}.prodotti. {e}")
        return -1


#delete a product:
def delete_prod(conn, cursor, schema, p_code):
    try:
        query = f"DELETE FROM {schema}.prodotti WHERE codiceprod = {p_code}"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Deleted product {p_code} from table {schema}.prodotti.")
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to delete product {p_code} from table {schema}.prodotti. {e}")
        return -1

#register a new supplier:
def add_supplier(schema, supplier, discount):
    try:
        conn, cursor = db_connect()
        #1) check if supplier already in DB:
        query = f"SELECT produttore, scontomedio FROM {schema}.produttori WHERE produttore = '{supplier}'"
        Match = pd.read_sql(query, conn)
        if Match.empty == True:
            #if not exists yet -> register supplier:
            query = f"INSERT INTO {schema}.produttori (produttore, scontomedio) VALUES ('{supplier}', {discount})"
            cursor.execute(query)
            conn.commit()
            dlog.info(f"Registered supplier {supplier}, discount {discount}%, to table {schema}.produttori.")
        else:
            #if already in DB -> update discount:
            query = f"UPDATE {schema}.produttori SET scontomedio = {discount} WHERE produttore = '{supplier}'"
            cursor.execute(query)
            conn.commit()
            dlog.info(f"Updated discount rate for supplier {supplier} to {discount}%, table {schema}.produttori.")
            db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to register supplier {supplier} and discount {discount}% to table {schema}.produttori. {e}")
        return -1

#register a new category:
def add_category(schema, category, vat):
    try:
        conn, cursor = db_connect()
        #1) check if category already in DB:
        query = f"SELECT categoria, aliquota FROM {schema}.categorie WHERE categoria = '{category}'"
        Match = pd.read_sql(query, conn)
        if Match.empty == True:
            #if not exists yet -> register category:
            query = f"INSERT INTO {schema}.categorie (categoria, aliquota) VALUES ('{category}', {vat})"
            cursor.execute(query)
            conn.commit()
            dlog.info(f"Registered category {category}, vat rate {vat}%, to table {schema}.categorie.")
        else:
            #if already in DB -> update vat rate:
            query = f"UPDATE {schema}.categorie SET aliquota = {vat} WHERE categoria = '{category}'"
            cursor.execute(query)
            conn.commit()
            dlog.info(f"Updated vat rate for category {category} to {vat}%, table {schema}.categorie.")
            db_disconnect(conn, cursor)
        return 0
    except psycopg2.Error as e:
        dlog.error(f"Unable to register category {category} and vat rate {vat} to table {schema}.categorie. {e}")
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
        dlog.error(f"Unable to perform get_suggestion_list for supplier {supplier}. {e}")
    return FullList

