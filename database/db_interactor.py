from globals import *
from database.db_tools import db_connect

#DB_INTERACTOR:
#Low-level DB interfaces:
# - get_prodinfo()
# - get_supplier()
# - get_pieces()
# - update_pieces()
# - delete_ordlist()
# - get_existing_ordlist()
# - get_new_ordlist()
# - get_suggestion_list()
# - add_prod()
# - delete_prod()


#get all items in a column of produttore table:
def get_column(column_name):
    try:
        conn, cursor = db_connect()
        query = f"SELECT DISTINCT {column_name} FROM {SCHEMA}.Prodotti"
        items = pd.read_sql(query, conn)
        items = items[column_name].to_list()
        conn.close()
    except psycopg2.Error as e:
        items = []
        log.error(f"DB query error for all '{column_name}' items. {e}")
    return items


#get basic product info:
def get_prodinfo(conn, utts):
    #vars:
    resp = []
    buf = {}
    to_pop = []
    suppl_tok = ''

    #if p_code is available:
    if utts['p_code'] != None:
        print(utts['p_code'])
        try:
            #directly extract the matching product (direct match):
            query = f"SELECT codiceprod, produttore, nome, categoria, quantita FROM {SCHEMA}.Prodotti WHERE codiceprod = {utts['p_code']}"
            Prodotti = pd.read_sql(query, conn)
        except psycopg2.Error as e:
            log.error(f"DB query error for 'p_code'. {e}")

    else:
        #tokenize p_text to extract p_name:
        p_text = utts['p_text'].strip()
        tokens = p_text.split()
        print(tokens)

        if utts['supplier'] == None:
            #get list of suppliers:
            try:
                query = f"SELECT DISTINCT produttore FROM {SCHEMA}.Prodotti"
                Suppliers = pd.read_sql(query, conn)
            except psycopg2.Error as e:
                log.error(f"DB query error for 'supplier'. {e}")

            #CASES:
            #1) find the tokens for the supplier (if any - must be consecutive matches) and remove them from tokens list:
            for token in tokens:
                Suppl = Suppliers[Suppliers['produttore'].str.contains(token, na=False)]
                #if match found:
                if Suppl.empty == False:
                    #store tokens (keep appending while consecutive matches are found):
                    if suppl_tok == '':
                        suppl_tok = token
                    else:
                        suppl_tok = suppl_tok + " " + token
                    to_pop.append(tokens.index(token))
                elif suppl_tok != '':
                    #break as soon as the consecutive matches end:
                    break
            
            #reduce tokens list:
            if to_pop != []:
                for item in reversed(to_pop):
                    tokens.pop(item)
                to_pop = []
            
            #FALLBACK: if no words left:
            if len(tokens) == 0:
                return []

        #prepare query:
        if utts['supplier'] != None:
            suppstr = f" AND produttore = '{utts['supplier']}'"
        elif suppl_tok != '':
            suppstr = f" AND produttore LIKE '%{suppl_tok}%'"
        else:
            suppstr = ""
        
        #2) query DB for p_name (get first series of matches) and reduce residual tokens list:
        for token in tokens:
            try:
                #DB extract:
                query = f"SELECT codiceprod, produttore, nome, categoria, quantita FROM {SCHEMA}.Prodotti WHERE nome LIKE '%{token}%'{suppstr}"
                Prodotti = pd.read_sql(query, conn)
                to_pop.append(tokens.index(token))
                #if matches found:
                if Prodotti.empty == False:
                    break
            except psycopg2.Error as e:
                log.error(f"DB query error for p_name. {e}")

        #reduce tokens list:
        if to_pop != []:
            for item in reversed(to_pop):
                tokens.pop(item)
            to_pop = []

        #3) if first matching word found, progressively refine search in Pandas (word by word):
        if Prodotti.empty == False and len(tokens) != 0:
            #refine extraction:
            for token in tokens:
                Extr = Prodotti[Prodotti['nome'].str.contains(token, na=False)]
                #replace with refined table:
                if Extr.empty == False:
                    Prodotti = Extr
        
    #COMMON: extract needed prod info to return:
    if Prodotti.empty == False:
        for ind in Prodotti.index:
            buf['p_code'] = Prodotti['codiceprod'][ind]
            buf['supplier'] = Prodotti['produttore'][ind]
            buf['p_name'] = Prodotti['nome'][ind]
            buf['category'] = Prodotti['categoria'][ind]
            buf['pieces'] = Prodotti['quantita'][ind]
            resp.append(buf)
            buf = {}

    return resp


#look for supplier:
def get_supplier(conn, s_text):
    #vars:
    resp = []
    to_pop = []

    #tokenize p_text to extract supplier:
    s_text = s_text.strip()
    tokens = s_text.split()
    print(tokens)

    #get full list of suppliers from DB:
    try:
        query = f"SELECT DISTINCT produttore FROM {SCHEMA}.Prodotti"
        Suppliers = pd.read_sql(query, conn)
    except psycopg2.Error as e:
        log.error(f"DB query error for 'supplier'. {e}")

    #CASES:
    #1) query DB for supplier (get first series of matches) and reduce residual tokens list:
    for token in tokens:
        Suppl = Suppliers[Suppliers['produttore'].str.contains(token, na=False)]
        to_pop.append(tokens.index(token))
        if Suppl.empty == False:
            break

    #reduce tokens list:
    if to_pop != []:
        for item in reversed(to_pop):
            tokens.pop(item)
        to_pop = []
    
    #2) if first matching word found, progressively refine search in Pandas (word by word):
    if Suppl.empty == False and len(tokens) != 0:
        #refine extraction:
        for token in tokens:
            Extr = Suppl[Suppl['produttore'].str.contains(token, na=False)]
            #replace with refined table:
            if Extr.empty == False:
                Suppl = Extr
        
    #3) extract full matching supplier name(s) to return:
    if Suppl.empty == False:
        for ind in Suppl.index:
            resp.append(str(Suppl['produttore'][ind]))

    return resp


def get_pieces(cursor, p_code):
    #check products already in DB:
        query = f"SELECT quantita FROM {SCHEMA}.Prodotti WHERE codiceprod = {p_code}"
        try:
            cursor.execute(query)
            quant = int(cursor.fetchall()[0][0])
            return quant
                        
        except psycopg2.Error as e:
            log.error(f"Unable to check quantity boundary for product code {p_code}. {e}")
            return -1


def update_pieces(conn, cursor, utts):
    #compose query:
    if utts['variation'] == 'add':
        str1 = "+ " + str(utts['pieces'])
    elif utts['variation'] == 'decrease':
        str1 = "- " + str(utts['pieces'])
    else:
        return -1
    query = f"UPDATE {SCHEMA}.Prodotti SET quantita = quantita {str1} WHERE codiceprod = {utts['p_code']}"

    #DB update:
    try: 
        cursor.execute(query)
        changes = cursor.rowcount
        if changes != 0:
            conn.commit()
            log.info(f"Success: {utts['variation']} {utts['pieces']} pieces to product code {utts['p_code']}.")
            return 0
        else:
            log.error(f"DB: No match for p_code {utts['p_code']}.")
            return -1
    except psycopg2.Error as e:
        log.error(f"Unable to perform operation {utts['variation']} to product code {utts['p_code']}. {e}")
        return -1


#delete an existent ord_list:
def delete_ordlist(conn, cursor, ord_code):
    try:
        query = f"DELETE FROM {SCHEMA}.ListeOrdini WHERE codiceord = {ord_code}"
        cursor.execute(query)
        query = f"DELETE FROM {SCHEMA}.StoricoOrdini WHERE codiceord = {ord_code}"
        cursor.execute(query)
        conn.commit()
        log.info(f"Success: deleted ord_list code {ord_code} from both tables ListeOrdini and StoricoOrdini.")
    except psycopg2.Error as e:
        log.error(f"Unable to delete ord_list code {ord_code}. {e}")
    return 0


#a) extract from DB latest open order list for the current supplier (if any):
def get_existing_ordlist(conn, supplier):
    latest_code = None
    latest_date = None
    full_list = None
    num_prods = 0
    try:
        query = f"SELECT codiceord, datamodifica FROM {SCHEMA}.StoricoOrdini WHERE produttore = '{supplier}' AND datainoltro IS NULL ORDER BY datamodifica DESC LIMIT 1"
        Latest = pd.read_sql(query, conn)
        if Latest.empty == False:
            #extract references:
            latest_code = int(Latest['codiceord'].iloc[0])
            latest_date = str(Latest['datamodifica'].iloc[0])
            #get full order list (if any) - inner join with table Prodotti:
            query = f"SELECT ListeOrdini.codiceprod, Prodotti.nome, ListeOrdini.quantita FROM {SCHEMA}.ListeOrdini INNER JOIN {SCHEMA}.Prodotti ON ListeOrdini.codiceprod = Prodotti.codiceprod WHERE ListeOrdini.codiceord = {latest_code}"
            FullList = pd.read_sql(query, conn)
            if FullList.empty == False:
                num_prods = int(len(FullList.index))
                #convert to string:
                full_list = FullList.to_dict()
                full_list = json.dumps(full_list)

    except psycopg2.Error as e:
        log.error(f"Unable to perform get_existing_ordlist for supplier {supplier}. {e}")
        
    return latest_code, latest_date, full_list, num_prods


#b) create new order list from scratch in both DB tables:
def get_new_ordlist(conn, cursor, supplier):
    latest_code = None
    latest_date = None
    try:
        dt = datetime.now(pytz.timezone('Europe/Rome'))
        latest_code = int(dt.strftime('%Y%m%d%H%M%S')) #codiceord = current datetime
        latest_date = str(dt.strftime('%Y-%m-%d')) #datamodifica initialized as current datetime
        #create order in StoricoOrdini:
        query = f"INSERT INTO {SCHEMA}.StoricoOrdini (codiceord, produttore, datamodifica) VALUES ({latest_code}, '{supplier}', '{latest_date}')"
        cursor.execute(query)
        conn.commit()
        log.info(f"Success: created list ord_code {latest_code} into table StoricoOrdini.")

    except psycopg2.Error as e:
        log.error(f"Unable to perform get_new_ordlist for supplier {supplier}. {e}")
        
    return latest_code, latest_date


#c) edit order list:
def edit_ord_list(conn, cursor, ord_code, p_code, pieces, write_mode=False):
    try:
        #a) write_mode ("insert into"):
        if write_mode == True:
            #check first: avoid double inclusion of a product:
            query = f"SELECT codiceprod FROM {SCHEMA}.ListeOrdini WHERE codiceord = {ord_code} AND codiceprod = {p_code}"
            Prod = pd.read_sql(query, conn)
            if Prod.empty == False:
                #if product already there, update quantity:
                query = f"UPDATE {SCHEMA}.ListeOrdini SET quantita = {pieces} WHERE codiceord = {ord_code} AND codiceprod = {p_code}"
            else:
                #insert new row with the product:
                query = f"INSERT INTO {SCHEMA}.ListeOrdini (codiceord, codiceprod, quantita) VALUES ({ord_code}, {p_code}, {pieces})"

        #b) update mode ("update set" or "delete from"):
        elif pieces == 0:
            query = f"DELETE FROM {SCHEMA}.ListeOrdini WHERE codiceord = {ord_code} AND codiceprod = {p_code}"
        else:
            query = f"UPDATE {SCHEMA}.ListeOrdini SET quantita = {pieces} WHERE codiceord = {ord_code} AND codiceprod = {p_code}"
            
        cursor.execute(query)
        #update last_modified date:
        dt = datetime.now(pytz.timezone('Europe/Rome'))
        latest_date = str(dt.strftime('%Y-%m-%d')) #datamodifica initialized as current datetime
        query = f"UPDATE {SCHEMA}.StoricoOrdini SET datamodifica = '{latest_date}' WHERE codiceord = {ord_code}"
        cursor.execute(query)
        conn.commit()
        log.info(f"Success: updated list ord_code {ord_code} into table ListeOrdini.")
    except psycopg2.Error as e:
        log.error(f"Unable to edit ord_list {ord_code} for product {p_code}. {e}")
        return -1
    return 0


#d) get list of suggestions from DB:
def get_suggestion_list(conn, supplier, ord_code):
    full_list = None
    num_prods = 0
    try:
        #extract list of prods from the requested suppliers, with Quantità <= threshold and that have not been added yet to the order list under preparation:
        query = f"SELECT Prodotti.codiceprod, Prodotti.nome, Prodotti.quantita FROM {SCHEMA}.Prodotti WHERE Prodotti.produttore = '{supplier}' AND Prodotti.quantita <= {THRESHOLD_TO_ORD} AND NOT EXISTS (SELECT ListeOrdini.codiceprod FROM {SCHEMA}.ListeOrdini WHERE ListeOrdini.codiceord = {ord_code} AND ListeOrdini.codiceprod = Prodotti.codiceprod) ORDER BY Prodotti.quantita"
        FullList = pd.read_sql(query, conn)
        if FullList.empty == False:
            num_prods = int(len(FullList.index))
            #convert to string:
            full_list = FullList.to_dict()
            full_list = json.dumps(full_list)

    except psycopg2.Error as e:
        log.error(f"Unable to perform get_suggestion_list for supplier {supplier}. {e}")
        
    return full_list, num_prods


#add a new product:
def add_prod(conn, cursor, utts):
    try:
        query = f"INSERT INTO {SCHEMA}.Prodotti (codiceprod, produttore, nome, categoria, quantita) VALUES ({utts['p_code']}, '{utts['supplier']}', '{utts['p_name']}', '{utts['category']}', {utts['pieces']})"
        cursor.execute(query)
        conn.commit()
        log.info(f"Added product {utts['p_code']} to table Prodotti.")
        return 0
    except psycopg2.Error as e:
        log.error(f"Unable to add product {utts['p_code']} to table Prodotti. {e}")
        return -1


#delete a product:
def delete_prod(conn, cursor, p_code):
    try:
        query = f"DELETE FROM {SCHEMA}.Prodotti WHERE codiceprod = {p_code}"
        cursor.execute(query)
        conn.commit()
        log.info(f"Deleted product {p_code} from DB.")
        return 0
    except psycopg2.Error as e:
        log.error(f"Unable to delete product {p_code} from DB. {e}")
        return -1


#get list of products from DB:
def get_view_prodotti(conn, supplier=None):
    suppstr = ""
    FullList = pd.DataFrame()
    try:
        if supplier:
            suppstr = f" WHERE produttore = {supplier}"
        query = f"SELECT * FROM {SCHEMA}.Prodotti{suppstr}"
        FullList = pd.read_sql(query, conn)
    except psycopg2.Error as e:
        log.error(f"Unable to perform get_suggestion_list for supplier {supplier}. {e}")
    return FullList

