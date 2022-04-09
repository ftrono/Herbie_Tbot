import random
from globals import *
from database.db_tools import db_connect, db_disconnect, create_schema_tables

#ADMIN TOOLS:
# - admin_add_schema()
# - admin_delete_auths()


#add new Schema, generating the related OTP:
def admin_add_schema(name):
    try:
        conn, cursor = db_connect()
        #1) create Schema tables:
        create_schema_tables(conn, cursor, name)
        #2) register Schema and OTP:
        pw = random.randrange(12345678, 98765432)
        query = f"INSERT INTO Schemi (NomeSchema, HashOTP) VALUES ('{name}', sha224('{pw}'))"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Registered Schema and OTP for Schema {name}.")
        print(f"Registered Schema and OTP: {name} - {pw}")
        db_disconnect(conn, cursor)
        return 0
    except Exception as e:
        dlog.error(f"DB query error in creating Schema {name}. {e}")
        return -1

#delete authorization for a user:
def admin_delete_auths(chat_id, name=None):
    try:
        conn, cursor = db_connect()
        specstr = f" AND nomeschema = '{name}'" if name else ""
        query = f"DELETE FROM utenti WHERE chatid = {chat_id}{specstr}"
        cursor.execute(query)
        conn.commit()
        dlog.info(f"Deleted authorization for user: {chat_id}, schema: {name if name else 'all'}.")
        db_disconnect(conn, cursor)
        return 0
    except:
        dlog.error(f"DB query error: user auth not deleted.")
    return -1
