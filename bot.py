from pandas import DataFrame
from telegram import ReplyKeyboardRemove, Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, CallbackContext
import database.db_interactor as db_interactor
from database.db_tools import db_connect, db_disconnect
import bot_functions
from globals import *

#HERBIE TELEGRAM BOT

#GLOBALS:
#conversation states:
START, SET_AUTH = range(0, 2)
PICK_WH, PROCESS_MENU, PROCESS_PCODE, ASK_ALIQUOTA, INIT_ADD = range(0, 5)
PROCESS_SUPPLIER, ASK_DISCOUNT, SAVE_SUPPLIER, PROCESS_PNAME, PROCESS_CATEGORY = range(5, 10)
ASK_ALIQUOTA, SAVE_CATEGORY, PROCESS_PRICE, PROCESS_PIECES, SAVE_EDIT = range(10, 15)
NEXT_STEP, EDIT_INFO, PROCESS_VEGAN, PROCESS_NOLACTOSE, PROCESS_NOGLUTEN = range(15, 20)
PROCESS_NOSUGAR, PROCESS_FILTER, CLEAN_DB = range(20, 23)
CONV_END = -1 #value of ConversationHandler.END

#default messages:
ask_register = f"Per poter utilizzare il bot è necessario richiedere l'OTP di accesso relativo alla tua licenza all'amministratore. Quando lo avrai ricevuto, utilizza il comando /registrami per registrarti."
welcome = f"\n🤖 <b>Lancia un comando per iniziare!</b>"+\
            f"\n- /aggiorna - Registra nuovo o aggiorna il magazzino"+\
            f"\n- /vista - Scarica vista del magazzino in formato stampa"+\
            f"\n- /registrami - Registra una nuova autorizzazione"+\
            f"\n- /start - Scarica autorizzazioni aggiornate"+\
            f"\n- /esci - Annulla l'operazione corrente"

#reset functions:
def end_open_query(update, context):
    try:
        update.callback_query.answer()
        context.user_data['last_answered'] = update.update_id
    except:
        pass

def remove_open_keyboards(update, context):
    try:
        toend = context.user_data.get("last_sent")
        if toend != None:
            context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id, message_id=toend, reply_markup=None)
    except:
        pass

def reset_priors(update, context):
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    context.user_data['to_edit'] = None
    context.user_data['caller'] = None
    context.user_data["NEW_SUPPLIER"] = None
    context.user_data["NEW_CATEGORY"] = None
    context.user_data['Matches'] = None

def answer_query(update, context, delete=False):
    #get open query:
    query = update.callback_query
    choice = query.data
    if delete == True:
        query.delete_message()
    else:
        query.edit_message_reply_markup(reply_markup=None)
    context.user_data['last_answered'] = update.update_id
    query.answer()
    return choice

def code_to_int(p_code):
    #try conversion to int (there might be some initial letters, to be cut):
    try:
        try:
            p_code = int(p_code)
        except:
            p_code = int(p_code[1:])
    except:
        p_code = int(p_code[2:])
    return p_code


#COMMANDS & HELPERS

#"/start":
#start - 1) check & get user auth:
def start(update, context):
    #reset:
    reset_priors(update, context)
    #check user authorizations:
    chat_id = update.effective_chat.id
    tlog.info(f"/start launched by user: {chat_id}")
    #download updated user authorizations:
    msg = f"Autenticazione in corso..."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    auths = db_interactor.get_auths(chat_id)
    context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    #message:
    if auths == []:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
    else:
        context.user_data['auths'] = auths
        authlist = ", ".join(auths)
        msg = f"Ciao, sono Herbie! Sei registrato nei magazzini di:\n<b>{authlist.upper()}</b>.\n{welcome}"
        tlog.info(f"Downloaded updated auths for user: {chat_id}")
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return CONV_END

#"/registrami":
#registrami - 1) ask OTP:
def registrami(update, context):
    #reset:
    reset_priors(update, context)
    #asks user to send the OTP:
    chat_id = update.effective_chat.id
    msg = f"Inviami l'OTP di accesso al tuo magazzino. Se non hai l'OTP, richiedilo all'amministratore."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SET_AUTH

#2) match OTP with related License in DB: if found, register auth for the user:
def set_auth(update, context):
    chat_id = update.effective_chat.id
    #get received OTP:
    otp = update.message.text
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    msg = f"OTP ricevuto. Verifica in corso..."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    context.user_data["last_sent"] = message.message_id
    #match OTP with Schemi list:
    schema = db_interactor.register_auth(chat_id, otp)
    #a) no match -> conv_end:
    if schema == -1:
        msg = f"Registrazione non avvenuta. Controlla le tue autorizzazioni usando /start.\n\n{ask_register}"
        message.edit_text(msg)
        return CONV_END
    else:
        #b) match found -> launch "/start":
        context.user_data['schema'] = schema
        msg = f"Ciao, sono Herbie! Benvenuto nel magazzino di <b>{schema.upper()}</b>.\n{welcome}"
        message.edit_text(msg, parse_mode=ParseMode.HTML)
        return CONV_END

#GET SCHEMA:
#HELPER: get Schema(s) from DB auths:
def get_schema(update, context):
    #get user authorizations:
    chat_id = update.effective_chat.id
    auths = context.user_data.get('auths')
    if auths == None:
        #get auths from DB:
        msg = f"Autenticazione in corso..."
        message = context.bot.send_message(chat_id=chat_id, text=msg)
        auths = db_interactor.get_auths(chat_id)
        context.user_data['auths'] = auths
        context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)

    #a) no auths:
    if auths == []:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
        message = context.bot.send_message(chat_id=chat_id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    #b) one auth only:
    elif len(auths) == 1:
        schema = auths[0]
        context.user_data['schema'] = schema
        tlog.info(f"Got schema: {schema}")
        return schema
    #c) more auths -> get picker:
    else:
        keyboard = []
        for auth in auths:
            keyboard.append([InlineKeyboardButton(auth, callback_data=auth)])
        msg = f"📌 Dimmi quale magazzino usare:"
        message = context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PICK_WH

#start - 2) if more auths -> pick a warehouse:
def pick_wh(update, context):
    #get pick from open query:
    schema = answer_query(update, context, delete=True)
    tlog.info(schema)
    context.user_data['schema'] = schema
    return main_menu(update, context, schema)


#MAIN MENU:
#main menu for both "/aggiorna" and "/vista":
def main_menu(update, context, schema):
    #keyboard:
    if context.user_data.get('caller') == 'aggiorna':
        #/aggiorna:
        actionstr = f"Cosa vuoi aggiornare?"
        buttons = ['Prodotto', 'Produttore', 'Categoria', 'Pulisci magazzino', 'Esci']
    else:
        #/vista:
        actionstr = f"Quale vista vuoi estrarre?"
        buttons = ['Prodotti', 'Recap', 'Storico ordini', 'Lista ordine', 'Esci']
    msg = f"Ciao! Sei nel magazzino di <b>{schema.upper()}</b>.\n\n🤖📦✏ <b>{actionstr}</b>"
    keyboard = []
    for button in buttons:
        keyboard. append([InlineKeyboardButton(button, callback_data=button)])
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_MENU

#process choice after main menu:
def process_menu(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    caller = context.user_data.get('caller')
    #sorter:
    if caller == 'aggiorna':
        if choice == 'Prodotto':
            context.user_data['caller'] = 'upd_prod'
            return prodotto(update, context)
        elif choice == 'Produttore':
            context.user_data['caller'] = 'upd_supp'
            return ask_supplier(update, context)
        elif choice == 'Categoria':
            context.user_data['caller'] = 'upd_cat'
            return ask_category(update, context)
        elif choice == 'Pulisci magazzino':
            return ask_clean(update, context)
        else:
            msg = f"Ok. A presto!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        if choice == 'Esci':
            msg = f"Ok. A presto!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
        else:
            context.user_data['vista'] = choice.lower()
            return ask_filter(update, context)

#"/aggiorna":
def aggiorna(update, context):
    #reset:
    reset_priors(update, context)
    #get Schema:
    context.user_data['caller'] = 'aggiorna'
    schema = get_schema(update, context)
    if schema == CONV_END or schema == PICK_WH:
        return schema
    else:
        return main_menu(update, context, schema)

#"/vista":
def vista(update, context):
    #reset:
    reset_priors(update, context)
    #get Schema:
    context.user_data['caller'] = 'vista'
    schema = get_schema(update, context)
    if schema == CONV_END or schema == PICK_WH:
        return schema
    else:
        return main_menu(update, context, schema)


#"/prodotto":
#prodotto - 1) ask p_code mode: text or photo:
def prodotto(update, context):
    msg = f"Per iniziare, mi serve un <b>codice a barre</b>. Puoi:\n"+\
            f"- Inviarmi una <b>FOTO</b> del barcode, oppure\n"+\
            f"- Trascrivermi il codice via <b>TESTO</b> (SENZA spazi).\n\n"+\
            f"Se il prodotto è già registrato, puoi anche inviarmi in alternativa il <b>nome</b> del prodotto, te lo cercherò nel magazzino."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PCODE

#prodotto - 2) process p_code:
def process_pcode(update, context):
    p_code = None
    from_match = False
    schema = context.user_data.get('schema')
    photo_message = update.message.message_id
    msg = f"Sto estraendo i dati..."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id

    #get product reference:
    #A) FROM PHOTO -> P_CODE:
    if update.message.photo != []:
        #extract and store barcode from image:
        try:
            image = update.message.photo[-1].get_file()
            p_code = bot_functions.extract_barcode(image)
            #delete photo to save space:
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=photo_message)
            #store barcode in bot memory:
            tlog.info(f"Letto codice {p_code}.")
            p_code = code_to_int(p_code)
            context.user_data['p_code'] = p_code
            msg = f"Ho letto il codice {p_code}. "
        except:
            #no barcodes found:
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=photo_message)
            msg = f"Non ho trovato codici.\n\nProva con un'altra foto, o in alternativa trascrivimi il nome o il codice a barre.\n\nOppure usa /esci per uscire."
            message.edit_text(text=msg)
            context.user_data['Matches'] = None
            return PROCESS_PCODE
    
    else:
        #B) FROM TEXT SENT BY THE USER -> EITHER P_CODE OR P_TEXT:
        p_text = update.message.text.lower()

        #CASE B.1) NUMERICAL CODE:
        try:
            p_code = code_to_int(p_text)
            #check if the code is the index of a Matches list already sent:
            if p_code in [1, 2, 3]:
                Matches = context.user_data.get('Matches')
                tlog.info(f"Converted code {p_code}")
                if Matches is not None:
                    try:
                        ind = p_code-1
                        #if found -> get the reference row and proceed to edit info / add info:
                        Matches = Matches.iloc[[ind]]
                        Matches.reset_index(drop=True, inplace=True)
                        #if found -> proceed to edit info / add info:
                        p_code = Matches['codiceprod'].iloc[0]
                        tlog.info(f"Trovato codice {p_code}.")
                        from_match = True
                    except:
                        tlog.info(f"Index {ind} not found in previous Matches list.")

            #else -> the code is a barcode. Store barcode in bot memory:
            context.user_data['p_code'] = p_code
            tlog.info(f"Trovato codice {p_code}.")
            msg = f"Ho trovato il codice {p_code}. "

        #CASE B.2) TENTATIVE PRODUCT TEXT (P_TEXT):
        except:
            #match existing product names in DB:
            Matches = db_interactor.match_product(schema, p_text=p_text)

            #if not found -> ask retry:
            if Matches.empty == True:
                msg = f"Non ho trovato prodotti con questo nome.\n\nRiprova a inviarmi il nome o il codice a barre, oppure una foto del barcode.\n\nOppure usa /esci per uscire."
                message.edit_text(text=msg)
                context.user_data['Matches'] = None
                return PROCESS_PCODE

            #if more matches -> show list of best matches, each with an index:
            elif len(Matches.index) > 1:
                msg = f"Ho trovato più di un prodotto simile. Se il prodotto che cerchi è uno di questi, inviami il <b><i>numero</i></b>:"
                for ind in Matches.index:
                    msg = f"{msg}\n   ' <b><i>{ind+1}</i></b> ' per:  <i>{Matches['produttore'].iloc[ind]} {Matches['nome'].iloc[ind]}</i>"
                msg = f"{msg}\n\nAltrimenti riprova a inviarmi il nome o il codice a barre, oppure una foto del barcode.\n\nOppure usa /esci per uscire."
                message.edit_text(text=msg, parse_mode=ParseMode.HTML)
                context.user_data['Matches'] = Matches
                return PROCESS_PCODE

            else:
                #if found -> proceed to edit info / add info:
                p_code = Matches['codiceprod'].iloc[0]
                context.user_data['p_code'] = p_code
                tlog.info(f"Trovato codice {p_code}.")
                msg = f"Ho trovato il codice {p_code}. "
                from_match = True
    
    #check if the p_code is new or already registered in the DB:
    if from_match == False:
        try:
            conn, cursor = db_connect()
            Matches = db_interactor.match_product(schema, p_code=p_code)
            db_disconnect(conn, cursor)
            #if product not found -> new product:
            if Matches.empty == True:
                msg = f"{msg}Questo prodotto non è nel mio magazzino. Lo inseriamo ora?"
                keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                            InlineKeyboardButton('No', callback_data='No')]]
                message.edit_text(msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(keyboard))
                context.user_data['Matches'] = None
                return INIT_ADD
        except:
            #DB error:
            msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            context.user_data['Matches'] = None
            return CONV_END
        
    #show recap message of product found:
    try:
        #store all match info in bot memory:
        context.user_data['supplier'] = Matches['produttore'].iloc[0]
        context.user_data['p_name'] = Matches['nome'].iloc[0]
        context.user_data['category'] = Matches['categoria'].iloc[0]
        context.user_data['price'] = Matches['prezzo'].iloc[0]
        context.user_data['pieces'] = Matches['quantita'].iloc[0]
        #ask what to do:
        msg = f"{msg}Ti invio il recap del prodotto:\n"+\
            f"- Produttore: <i>{Matches['produttore'].iloc[0]}</i>\n"+\
            f"- Nome: <i>{Matches['nome'].iloc[0]}</i>\n"+\
            f"- Categoria: <i>{Matches['categoria'].iloc[0]}</i>\n"+\
            f"- Prezzo: <i>{Matches['prezzo'].iloc[0]:.2f}€</i>\n"+\
            f"- Numero di pezzi: <i>{Matches['quantita'].iloc[0]}</i>\n"+\
            f"\nCosa vuoi fare?"
        keyboard = [[InlineKeyboardButton('Modifica info di base', callback_data='Modifica info')],
                    [InlineKeyboardButton('Questionario dettagli', callback_data='Aggiungi info')],
                    [InlineKeyboardButton('Annulla', callback_data='Annulla')]]
        message.edit_text(msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        #reset matches:
        context.user_data['Matches'] = None
        return NEXT_STEP

    except:
        #DB error:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        context.user_data['Matches'] = None
        return CONV_END

#ADD 1) init:
def init_add(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    if choice == 'No':
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        return ask_supplier(update, context)

#common helper:
def ask_supplier(update, context):
    schema = context.user_data.get('schema')
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Iniziamo. "
    #supplier picker:
    keyboard = bot_functions.inline_picker(schema, 'produttore')
    msg = f"{msg}Dimmi il nome del <b>produttore</b>. Oppure usa /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_SUPPLIER

#ADD 2) / PRODUTTORE 1) process supplier and ask next:
def process_supplier(update, context):
    caller = context.user_data.get('caller')
    try:
        #IF ALREADY IN DB -> get from query:
        supplier = answer_query(update, context)
        tlog.info(f"Letto produttore {supplier}.")
        context.user_data['supplier'] = supplier
        #ask next:
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
        elif caller == 'upd_supp':
            return rename_supplier(update, context, supplier)
        else:
            return ask_pname(update, context, supplier)
    except:
        #IF NEW -> get from user message:
        supplier = update.message.text.lower()
        context.user_data['supplier'] = supplier
        tlog.info(f"Letto produttore {supplier}.")
        remove_open_keyboards(update, context)
        #check if supplier not in Produttori table:
        schema = context.user_data.get('schema')
        suppliers = db_interactor.get_column(schema, 'produttore')
        if supplier not in suppliers:
            #register new supplier -> ask discount on orders:
            msg = f"Il produttore '{supplier}' è nuovo: te lo registro. Scrivimi la percentuale di sconto sugli ordini applicata in media da {supplier} (es. 30%).\n\nOppure usa /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_SUPPLIER"] = True
            return SAVE_SUPPLIER
        else:
            #if caller is edit info -> return to state Recap:
            if context.user_data.get('to_edit') != None:
                return process_pieces(update, context)
            elif caller == 'upd_supp':
                return rename_supplier(update, context, supplier)
            else:
                #ask next:
                return ask_pname(update, context, supplier)

#produttore - 1) rename supplier:
def rename_supplier(update, context, supplier):
    #ask rename:
    msg = f"Scrivimi il nuovo nome del produttore {supplier}.\nSe non vuoi modificarlo inviami <b>NO</b>.\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return ASK_DISCOUNT

#produttore - 2) ask typical discount on orders from supplier:
def ask_discount(update, context):
    #store supplier from user message:
    choice = update.message.text.lower()
    if choice == 'no':
        supplier = context.user_data['supplier']
        msg = f"Ok, mantengo il nome '{supplier}'. "
    else:
        supplier = choice
        context.user_data['new_supplier_name'] = supplier
        msg = f"Ok, salverò il nuovo nome '{supplier}'. "
    #ask discount:
    msg = f"{msg}Ora scrivimi la percentuale di sconto sugli ordini applicata in media da {supplier} (es. 30%).\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SAVE_SUPPLIER

#produttore - 3) save new supplier and its typical discount rate on orders:
def save_supplier(update, context):
    #store average discount from user message:
    discount = update.message.text.strip('%')
    discount = discount.replace(',', '.')
    try:
        discount = int(discount)
    except:
        msg = "Re-inviami soltanto la percentuale in cifre (es. 30%).\n\nOppure usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return SAVE_SUPPLIER

    #save new data to DB:
    supplier = context.user_data['supplier']
    schema = context.user_data['schema']
    new_name = context.user_data.get('new_supplier_name')
    ret = db_interactor.register_supplier(schema, supplier, discount, new_name=new_name)
    if ret == 0:
        if new_name != None:
            supplier = new_name
        context.user_data['new_supplier_name'] = None
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
        msg = f"Fatto! Ti ho salvato produttore {supplier} e relativo sconto medio {discount}% nel magazzino {schema}."
        #check if this state has been reached from the "/product" conversatiion: if so, continue there:
        if context.user_data.get("NEW_SUPPLIER") == True:
            #ask next:
            msg = f"{msg}\n\nOra scrivimi il nome dettagliato del <b>prodotto</b>. Aggiungi tutte le info necessarie, es.:\n\n<i>Grintuss pediatric sciroppo 12 flaconcini</i>\n\nOppure usa /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_SUPPLIER"] = None
            return PROCESS_PNAME
        else:
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#common helper:
def ask_pname(update, context, supplier=None):
    #ask product name:
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f"Scrivimi"
    else:
        msg = f"Segnato produttore '{supplier}'! Ora scrivimi"
    msg = f"{msg} il nome dettagliato del <b>prodotto</b>. Aggiungi tutte le info necessarie, es.:\n\n<i>Grintuss pediatric sciroppo 12 flaconcini</i>\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PNAME

#ADD 3) process p_name and ask_category:
def process_pname(update, context):
    #get prod name sent by user:
    p_name = update.message.text.lower()
    p_name = p_name.replace("'", "")
    #store in bot memory:
    context.user_data['p_name'] = p_name
    tlog.info(f"Letto nome prodotto {p_name}.")
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        #else -> next message:
        return ask_category(update, context, p_name)


#common helper:
def ask_category(update, context, p_name=None):
    caller = context.user_data.get('caller')
    #if caller is edit info:
    if caller == 'upd_cat':
        msg = f"Scrivimi il nome della <b>categoria prodotti</b> a cui ti riferisci"
    elif context.user_data.get('to_edit') != None:
        msg = f"Scrivimi a quale <b>categoria</b> appartiene il prodotto"
    else:
        msg = f"Segnato nome '{p_name}'! Ora dimmi a quale <b>categoria</b> appartiene il prodotto"
    msg = f"{msg} (es. cosmesi, alimentazione, ...). Oppure usa /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    #category picker:
    schema = context.user_data.get('schema')
    keyboard = bot_functions.inline_picker(schema, 'categoria')
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_CATEGORY

#ADD 4) / CATEGORIA 1) process category and ask next:
def process_category(update, context):
    caller = context.user_data.get('caller')
    try:
        #IF ALREADY IN DB -> get from query:
        category = answer_query(update, context)
        tlog.info(f"Letta categoria {category}.")
        context.user_data['category'] = category
        #ask next:
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
        elif caller == 'upd_cat':
            return rename_category(update, context, category)
        else:
            return ask_price(update, context, category)
    except:
        #IF NEW -> get from user message:
        category = update.message.text.lower()
        context.user_data['category'] = category
        tlog.info(f"Letta categoria {category}.")
        remove_open_keyboards(update, context)
        #check if supplier not in Produttori table:
        schema = context.user_data.get('schema')
        categories = db_interactor.get_column(schema, 'categoria')
        if category not in categories:
            #register new category -> ask applicable vat rate:
            msg = f"La categoria '{category}' è nuova: te la registro. Scrivimi l'aliquota IVA applicabile alla categoria {category} (es. 10%).\n\nOppure usa /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_CATEGORY"] = True
            return SAVE_CATEGORY
        else:
            #if caller is edit info -> return to state Recap:
            if context.user_data.get('to_edit') != None:
                return process_pieces(update, context)
            elif caller == 'upd_cat':
                return rename_category(update, context, category)
            else:
                #ask next:
                return ask_price(update, context, category)


#categoria - 1) rename categoria:
def rename_category(update, context, categoria):
    #ask rename:
    msg = f"Scrivimi il nuovo nome della categoria {categoria}.\nSe non vuoi modificarlo inviami <b>NO</b>.\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return ASK_ALIQUOTA

#categoria - 2) ask applicable VAT rate on this category:
def ask_aliquota(update, context):
    #store category / choice from user message:
    choice = update.message.text.lower()
    if choice == 'no':
        category = context.user_data['category']
        msg = f"Ok, mantengo il nome '{category}'. "
    else:
        category = choice
        context.user_data['new_category_name'] = category
        msg = f"Ok, salverò il nuovo nome '{category}'. "
    #ask discount:
    msg = f"{msg}Ora scrivimi l'aliquota IVA applicabile alla categoria {category} (es. 10%).\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SAVE_CATEGORY

#categoria - 3) save new category and its applicable VAT rate:
def save_category(update, context):
    #store average discount from user message:
    vat = update.message.text.strip('%')
    vat = vat.replace(',', '.')
    try:
        vat = float(vat)
    except:
        msg = "Re-inviami soltanto l'aliquota in cifre (es. 10%).\n\nOppure usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return SAVE_CATEGORY

    #save new data to DB:
    category = context.user_data['category']
    schema = context.user_data['schema']
    new_name = context.user_data.get('new_category_name')
    ret = db_interactor.register_category(schema, category, vat, new_name=new_name)
    if ret == 0:
        if new_name != None:
            category = new_name
        context.user_data['new_category_name'] = None
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
        msg = f"Fatto! Ti ho salvato categoria {category} e relativa aliquota IVA applicabile {vat}% nel magazzino {schema}."
        #check if this state has been reached from the "/product" conversatiion: if so, continue there:
        if context.user_data.get("NEW_CATEGORY") == True:
            #ask next:
            msg = f"{msg}\n\nQual è il <b>prezzo al pubblico</b> del prodotto?\n"+\
                    f"Scrivi solo la <i>cifra</i> in Euro (es. 10 o 10,50)."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_CATEGORY"] = None
            return PROCESS_PRICE
        else:
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#common helper:
def ask_price(update, context, category=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnata categoria '{category}'! "
    msg = f"{msg}Qual è il <b>prezzo al pubblico</b> del prodotto?\n"+\
            f"Scrivi solo la <i>cifra</i> in Euro (es. 10 o 10,50)."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PRICE

#ADD 5) process price and ask quantity:
def process_price(update, context):
    #store answer from user message:
    price = update.message.text.strip('€')
    price = price.replace(',', '.')
    try:
        price = float(price)
    except:
        msg = "Re-inviami soltanto le cifre del prezzo (es. 10 o 10,50), senza simboli o parole.\n\nOppure usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_PRICE

    #store in bot memory:
    context.user_data['price'] = price
    tlog.info(f"Letto prezzo {price:.2f} €.")
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        #ask next:
        return ask_pieces(update, context, price)

#common helper:
def ask_pieces(update, context, price=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnato prezzo {price:.2f}€! "
    msg = f"{msg}Mi dici il <b>numero di pezzi</b> che hai in magazzino?\n\nScrivi solo la <i>cifra</i>, es. 1, 10, ...\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PIECES

#ADD 6) process quantity and show Recap:
def process_pieces(update, context):
    #1) check caller function:
    to_edit = context.user_data.get('to_edit')
    if (to_edit == None) or (to_edit == 'Quantita'):
        #a) if pieces:
        try:
            pieces = int(update.message.text)
        except:
            msg = "Re-inviami soltanto il numero in cifre (es. 1, 10, ...).\n\nOppure usa /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return PROCESS_PIECES
        #store in bot memory:
        context.user_data['pieces'] = pieces
        tlog.info(f"Letti {pieces} pezzi.")
        msg = f"Segnato {pieces} pezzi. "
    else:
        #b) if to_edit (no pieces):
        context.user_data['to_edit'] = None
        msg = f"Aggiornato. "
    
    #prepare product recap:
    info = {
        'p_code': context.user_data['p_code'],
        'supplier': context.user_data['supplier'],
        'p_name': context.user_data['p_name'],
        'category': context.user_data['category'],
        'price': float(context.user_data['price']),
        'pieces': int(context.user_data['pieces']),
    }
    msg = f"{msg}Ti invio il recap del prodotto:\n"+\
            f"- Codice: <i>{info['p_code']}</i>\n"+\
            f"- Produttore: <i>{info['supplier']}</i>\n"+\
            f"- Nome: <i>{info['p_name']}</i>\n"+\
            f"- Categoria: <i>{info['category']}</i>\n"+\
            f"- Prezzo: <i>{info['price']:.2f}€</i>\n"+\
            f"- Numero di pezzi: <i>{info['pieces']}</i>\n"+\
            f"\nPosso salvare nel magazzino?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return SAVE_EDIT

#prodotto - 7) store to DB or go to EDIT:
def save_to_db(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)

    #trigger STORE TO DB:
    if choice == 'Sì':
        msg = f"Salvataggio in corso..."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        schema = context.user_data.get('schema')
        p_code = context.user_data['p_code']
        info = {
            'p_code': p_code,
            'supplier': context.user_data['supplier'],
            'p_name': context.user_data['p_name'],
            'category': context.user_data['category'],
            'price': float(context.user_data['price']),
            'pieces': int(context.user_data['pieces']),
        }
        #save to DB:
        ret = db_interactor.register_prodinfo(schema, info)
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)
        if ret == -1:
            msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
        else:
            msg = f"Ti ho salvato il prodotto nel magazzino!\n\nVuoi che ti faccia qualche altra domanda per categorizzare meglio il prodotto?"
            keyboard = [[InlineKeyboardButton('Sì', callback_data='Aggiungi info'),
                        InlineKeyboardButton('No', callback_data='No')]]
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["last_sent"] = message.message_id
            return NEXT_STEP
    #trigger EDIT INFO:
    else:
        return edit_picker(update, context)

#prodotto - 8) if no EDIT -> decide next step to do:
def next_step(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)

    #"next_step" is called either by:
    # - process_pcode() -> asks options "Edit info", "Add info", "Cancel"
    # - save_to_db() -> asks options "Yes" or "No" to the question "Add info"

    #trigger ADD INFO -> start asking the details:
    if choice == "Sì" or choice == "Aggiungi info":
        return ask_vegan(update, context)
    
    #trigger EXIT:
    elif choice == "No" or choice == "Annulla":
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    
    #trigger EDIT INFO:
    else:
        return edit_picker(update, context)


#EDIT - common helper:
def edit_picker(update, context):
    keyboard = [[InlineKeyboardButton('Produttore', callback_data='Produttore'),
                InlineKeyboardButton('Nome', callback_data='Nome')],
                [InlineKeyboardButton('Categoria', callback_data='Categoria'),
                InlineKeyboardButton('Prezzo', callback_data='Prezzo')],
                [InlineKeyboardButton('Quantita', callback_data='Quantita'),
                InlineKeyboardButton('ESCI', callback_data='Esci')]]
    msg = f"Cosa vuoi modificare?"
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return EDIT_INFO

#EDIT:
def edit_info(update, context):
    #get open query:
    choice = answer_query(update, context, delete=True)
    tlog.info(choice)
    context.user_data['to_edit'] = choice
    #sorter:
    if choice == 'Produttore':
        return ask_supplier(update, context)
    elif choice == 'Nome':
        return ask_pname(update, context)
    elif choice == 'Categoria':
        return ask_category(update, context)
    elif choice == 'Prezzo':
        return ask_price(update, context)
    elif choice == 'Quantita':
        return ask_pieces(update, context)
    else:
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        context.user_data["to_edit"] = None
        return CONV_END


#ADD EXTRA INFO:
#extra - 1) ask bool vegan:
def ask_vegan(update, context):
    msg = f"Ti farò una serie di brevi domande. Puoi interrompere quando vuoi cliccando su /esci.\n\n"+\
            f"1) Il prodotto è <b>vegano</b>?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_VEGAN

#extra - 2) save vegan and ask bool nolactose:
def process_vegan(update, context):
    #get answer from open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'vegano'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. Prossima:\n\n2) Il prodotto è <b>senza lattosio</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOLACTOSE

#extra - 3) save nolactose and ask bool nogluten:
def process_nolactose(update, context):
    #get answer from open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'senzalattosio'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. Prossima:\n\n3) Il prodotto è <b>senza glutine</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOGLUTEN

#extra - 4) save nogluten and ask bool nosugar:
def process_nogluten(update, context):
    #get answer from open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'senzaglutine'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. Prossima:\n\n4) Il prodotto è <b>senza zucchero</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOSUGAR

#extra - 5) save nosugar and end:
def process_nosugar(update, context):
    #get answer from open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'senzazucchero'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}.\n\nHo completato l'aggiornamento del prodotto. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#"viste":
#viste - 1) main sorter:
def ask_filter(update, context):
    choice = context.user_data.get('vista')
    schema = context.user_data.get('schema')
    if choice == 'prodotti':
        msg = f"Vuoi estrarre le giacenze solo di uno specifico <b>produttore</b> o vuoi la <b>vista intera</b> delle giacenze?\n\nOppure usa /esci per uscire."
        #supplier picker:
        keyboard = [[InlineKeyboardButton('VISTA COMPLETA', callback_data='all')]]
        temp = bot_functions.inline_picker(schema, 'produttore')
        keyboard = keyboard + temp
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_FILTER
    elif choice == 'lista ordine':
        msg = f"Vuoi l'ultima lista ordini di uno specifico <b>produttore</b>? Se sì, seleziona un produttore dai suggerimenti.\n\n"+\
                f"Altrimenti inviami un <b>codice ordine</b>. Se non conosci il codice ordine, puoi estrarre lo <B>storico degli ordini</b> intero.\n\nOppure usa /esci per uscire."
        #supplier picker:
        keyboard = [[InlineKeyboardButton('STORICO ORDINI', callback_data='storico')]]
        temp = bot_functions.inline_picker(schema, 'produttore')
        keyboard = keyboard + temp
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_FILTER
    else:
        return get_vista(update, context)

#viste - 2) process user filter:
def process_filter(update, context):
    try:
        choice = answer_query(update, context, delete=True)
        tlog.info(f"filter_supp: {choice}")
    except:
        choice = update.message.text.lower()
    if choice == 'storico':
            context.user_data['vista'] = 'storico ordini'
    else:
        context.user_data['filter'] = choice
    return get_vista(update, context)

#viste - 3) extract vista:
def get_vista(update, context):
    choice = context.user_data.get('vista')
    msg = f"Estrazione vista in corso..."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    #get vista:
    schema = context.user_data.get('schema')
    filter = context.user_data.get('filter')
    filter = filter if filter != 'all' else None
    filterstr = f"_{filter}" if filter else ""
    filename = f'./data_cache/{schema}.{choice}{filterstr}.xlsx'
    #forker:
    if choice == 'prodotti':
        ret = bot_functions.create_view_prodotti(schema, filename, filter)
    elif choice == 'recap':
        ret = bot_functions.create_view_recap(schema, filename)
    elif choice == 'storico ordini':
        ret = bot_functions.create_view_storicoordini(schema, filename)
    elif choice == 'lista ordine':
        try:
            ordcode = int(filter)
            supplier = None
        except:
            ordcode = None
            supplier = filter
        ret = bot_functions.create_view_listaordine(schema, filename, supplier=supplier, codiceord=ordcode)
    else:
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        context.user_data['filter'] = None
        return CONV_END
    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)
    context.user_data['filter'] = None
    if ret == 0:
        #3) send file to user:
        try:
            xlsx = open(filename, 'rb')
            chat_id=update.effective_chat.id
            context.bot.send_document(chat_id, xlsx)
            os.remove(filename)
        except:
            msg = f"Non ho trovato dati. Rilancia il comando /vista per riprovare."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        msg = f"Non ho trovato viste corrispondenti. Rilancia il comando /vista per riprovare."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#CLEAN DB:
#pulisci - 1) ask confirmation:
def ask_clean(update, context):
    #reset:
    reset_priors(update, context)
    schema = context.user_data.get('schema')
    msg = f"<b>Pulizia magazzino:</b>\nIl comando rimuoverà dal magazzino virtuale <b>{schema.upper()}</b> tutti i prodotti che hanno zero pezzi e tutti i produttori e le categorie prodotto non utilizzate. Sarà necessario reinserirle in futuro se dovessero servire.\n\nSei sicuro di voler procedere?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return CLEAN_DB

#pulisci - 2) perform cleaning:
def pulisci(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    if choice == 'No':
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        #clean:
        chat_id = update.effective_chat.id
        schema = context.user_data.get('schema')
        tlog.info(f"DB cleaning launched by user: {chat_id} on schema: {schema}")
        msg = f"Pulizia in corso..."
        message = context.bot.send_message(chat_id=chat_id, text=msg)
        ret = db_interactor.clean_db(schema)
        if ret == 0:
            msg = f"Pulizia del magazzino {schema.upper()} completata! Ho eliminato i prodotti con zero pezzi e i produttori/categorie non utilizzati."
            message.edit_text(msg)
        else:
            msg = f"C'è stato un problema, ti chiedo scusa! Pulizia del magazzino {schema.upper()} non completata."
            message.edit_text(msg)
        return CONV_END


#GENERIC HANDLERS:
#default reply:
def default_reply(update, context):
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    update.message.reply_text(f"{welcome}", parse_mode=ParseMode.HTML)

#cancel and end:
def esci(update, context):
    #reset:
    reset_priors(update, context)
    msg = "Esco. A presto!"
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    return CONV_END

#error handler: log errors caused by updates:
def error(update, context):
    #reset:
    reset_priors(update, context)
    tlog.exception(f"{Exception}")
    #tlog.warning('Update "%s" caused error "%s"', update, context.error)
    msg = f"C'è stato un problema, ti chiedo scusa!"
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return CONV_END


#MAIN:
def main() -> None:
    #create the Updater and pass it the bot's token:
    updater = Updater(TOKEN, use_context=True)
    #get the dispatcher to register handlers:
    dispatcher = updater.dispatcher

    #command handlers:
    dispatcher.add_handler(CommandHandler('start', start))

    #conversation handlers:
    #/registrami:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('registrami', registrami),
            MessageHandler(Filters.regex("^(Registrami|registrami)$"), registrami)],
        states={
            SET_AUTH: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.regex(r'\d+'), set_auth)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #"/aggiorna":
    conv_handler = ConversationHandler(
        entry_points=[
                CommandHandler('aggiorna', aggiorna),
                MessageHandler(Filters.regex("^(Aggiorna|aggiorna)$"), prodotto)],
        states={
            PICK_WH: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(pick_wh, pattern='.*')],
            PROCESS_MENU: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_menu, pattern='.*')],
            PROCESS_PCODE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.photo, process_pcode),
                MessageHandler(Filters.text, process_pcode)],
            INIT_ADD: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(init_add, pattern='.*')],
            PROCESS_SUPPLIER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_supplier, pattern='.*'),
                MessageHandler(Filters.text, process_supplier)],
            ASK_DISCOUNT: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, ask_discount)],
            SAVE_SUPPLIER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, save_supplier)],
            PROCESS_PNAME: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_pname)],
            PROCESS_CATEGORY: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_category, pattern='.*'),
                MessageHandler(Filters.text, process_category)],
            ASK_ALIQUOTA: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, ask_aliquota)],
            SAVE_CATEGORY: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, save_category)],
            PROCESS_PRICE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_price)],
            PROCESS_PIECES: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_pieces)],
            SAVE_EDIT: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(save_to_db, pattern='.*')],
            NEXT_STEP: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(next_step, pattern='.*')],
            EDIT_INFO: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(edit_info, pattern='.*')],
            PROCESS_VEGAN: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_vegan, pattern='.*')],
            PROCESS_NOLACTOSE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nolactose, pattern='.*')],
            PROCESS_NOGLUTEN: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nogluten, pattern='.*')],
            PROCESS_NOSUGAR: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nosugar, pattern='.*')],
            CLEAN_DB: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(pulisci, pattern='.*')],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)
    
    #/vista:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('vista', vista),
            MessageHandler(Filters.regex("^(Vista|vista)$"), vista)],
        states={
            PICK_WH: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(pick_wh, pattern='.*')],
            PROCESS_MENU: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_menu, pattern='.*')],
            PROCESS_FILTER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_filter, pattern='.*'),
                MessageHandler(Filters.text, process_filter)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #message handlers:
    dispatcher.add_handler(MessageHandler((Filters.text | Filters.photo), default_reply))

    #log all errors:
    dispatcher.add_error_handler(error)

    #webhook:
    if ENV == 'heroku':
        updater.start_webhook(
            listen="0.0.0.0",
            port=int(PORT),
            url_path=TOKEN,
            webhook_url = HOOK_URL + TOKEN
        )
    else:
        #start polling:
        updater.start_polling()

    #idle:
    updater.idle()


if __name__ == '__main__':
    main()
