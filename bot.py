from dataclasses import replace
from telegram import ReplyKeyboardRemove, Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, CallbackContext
import database.db_interactor as db_interactor
from database.db_tools import db_connect, db_disconnect
import bot_functions
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from globals import *

#HERBIE TELEGRAM BOT

#GLOBALS:
#conversation states:
START, PICK_WH, SET_AUTH = range(3)
PROCESS_PCODE, ASK_DISCOUNT, ASK_ALIQUOTA, INIT_ADD, PROCESS_SUPPLIER, SAVE_SUPPLIER, PROCESS_PNAME, PROCESS_CATEGORY, SAVE_CATEGORY, PROCESS_PIECES, SAVE_EDIT, NEXT_STEP, ASK_REWRITE, PROCESS_PRICE, PROCESS_DISP_MEDICO, PROCESS_MIN_AGE, PROCESS_BIO, PROCESS_VEGAN, PROCESS_NOGLUTEN, PROCESS_NOLACTOSE, PROCESS_NOSUGAR = range(21)
CONV_END = -1 #value of ConversationHandler.END

#default messages:
ask_register = f"Per poter utilizzare il bot è necessario richiedere l'OTP di accesso relativo alla tua licenza all'amministratore. Quando lo avrai ricevuto, utilizza il comando /registrami per registrarti."
welcome = f"Lancia un comando per iniziare.\n\n<b>Comandi disponibili:</b>"+\
                f"\n- /start - Scelta magazzino"+\
                f"\n- /prodotto - Inserisci un nuovo prodotto o aggiorna le informazioni"+\
                f"\n- /produttore - Registra un nuovo produttore o aggiornane lo sconto medio sugli ordini"+\
                f"\n- /categoria - Registra una nuova categoria prodotti o aggiornane l'aliquota IVA applicabile"+\
                f"\n- /registrami - Registra una nuova autorizzazione"+\
                f"\n- /esci - Annulla l'operazione corrente"

#reset functions:
def end_open_query(update: Update, context: CallbackContext):
    try:
        update.callback_query.answer()
    except:
        pass

def remove_open_keyboards(update: Update, context: CallbackContext):
    try:
        toend = context.user_data.get("last_sent")
        if toend != None:
            context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id, message_id=toend, reply_markup=None)
    except:
        pass


#COMMANDS & HELPERS:
#"/start":
#start - 1) check & get user auth:
def start(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    chat_id = update.effective_chat.id
    tlog.info(f"/start launched by user: {chat_id}")
    #check user authorizations:
    msg = f"Autenticazione in corso..."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    context.user_data["last_sent"] = message.message_id
    auths = db_interactor.get_auths(chat_id)
    #a) no auths -> user must launch "/registrami" command:
    if auths == []:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
        message.edit_text(msg)
        return CONV_END
    #b) store authorization for chosen WH:
    elif len(auths) == 1:
        schema = auths[0]
        tlog.info(schema)
        context.user_data['schema'] = schema
        msg = f"Ciao! Benvenuto nel mio magazzino di <b>{schema}</b>.\n{welcome}"
        message.edit_text(msg, parse_mode=ParseMode.HTML)
        return CONV_END
    else:
        keyboard = []
        for auth in auths:
            keyboard.append([InlineKeyboardButton(auth, callback_data=auth)])
        msg = f"Ciao! Su quale magazzino vuoi operare?"
        message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return PICK_WH

#start - 2) if more auths -> pick a warehouse:
def pick_wh(update: Update, context: CallbackContext) -> int:
    #get pick from open query:
    query = update.callback_query
    schema = query.data
    tlog.info(schema)
    query.delete_message()
    query.answer()
    context.user_data['schema'] = schema
    msg = f"Ciao! Benvenuto nel mio magazzino di <b>{schema}</b>.\n{welcome}"
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return CONV_END


#"/registrami":
#registrami - 1) ask OTP:
def registrami(update: Update, context: CallbackContext):
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    chat_id = update.effective_chat.id
    #asks user to send the OTP:
    msg = f"Inviami l'OTP di accesso al tuo magazzino. Se non hai l'OTP, richiedilo all'amministratore."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SET_AUTH

#2) match OTP with related License in DB: if found, register auth for the user:
def set_auth(update: Update, context: CallbackContext):
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
        msg = f"Non ho riconosciuto l'OTP.\n\n{ask_register}"
        message.edit_text(msg)
        return CONV_END
    else:
        #b) match found -> launch "/start":
        context.user_data['schema'] = schema
        msg = f"Ciao! Benvenuto nel mio magazzino di <b>{schema}</b>.\n{welcome}"
        message.edit_text(msg, parse_mode=ParseMode.HTML)
        return CONV_END


#HELPER: get previously chosen Schema (from "/start") or get Schema(s) from auths:
def get_schema(update: Update, context: CallbackContext) -> int:
    schema = context.user_data.get('schema')
    #if "/start" not launched yet:
    if schema == None:
        #get auths from DB:
        #check user authorizations:
        chat_id = update.effective_chat.id
        msg = f"Autenticazione in corso..."
        message = context.bot.send_message(chat_id=chat_id, text=msg)
        context.user_data["last_sent"] = message.message_id
        auths = db_interactor.get_auths(chat_id)
        #a) no auths:
        if auths == []:
            msg = "Non ho trovato autorizzazioni. Lancia il comando /start per verificare le tue autorizzazioni."
            message.edit_text(msg)
            return None
        #b) one auth only:
        elif len(auths) == 1:
            schema = auths[0]
            context.user_data['schema'] = schema
            tlog.info(f"Got schema: {schema}")
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)
            return schema
        #c) more auths (note: admin only, not for normal users):
        else:
            msg = "Ho trovato più di un'autorizzazione: lancia il comando /start per scegliere su quale magazzino operare."
            message.edit_text(msg)
            return None
    else:
        tlog.info(f"Schema: {schema}")
        return schema


#"/produttore":
#produttore - 1) ask name of new supplier:
def produttore(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    #get Schema:
    schema = get_schema(update, context)
    if schema == None:
        return CONV_END
    msg = f"Ciao! Registriamo un nuovo produttore, o aggiorniamone lo sconto medio sugli ordini, nel magazzino <b>{schema}</b>.\n\n"+\
            f"Inviami il nome del produttore. Oppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return ASK_DISCOUNT

#produttore - 2) ask typical discount on orders from supplier:
def ask_discount(update: Update, context: CallbackContext):
    #store supplier from user message:
    supplier = update.message.text.lower()
    context.user_data['supplier'] = supplier
    #ask discount:
    msg = f"Ricevuto! Ora scrivimi la percentuale di sconto sugli ordini applicata in media da {supplier} (es. 30%).\n\nOppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SAVE_SUPPLIER

#produttore - 3) save new supplier and its typical discount rate on orders:
def save_supplier(update: Update, context: CallbackContext) -> int:
    #store average discount from user message:
    discount = update.message.text.strip('%')
    discount = discount.replace(',', '.')
    try:
        discount = int(discount)
    except:
        msg = "Re-inviami soltanto la percentuale in cifre (es. 30%).\n\nOppure clicca su /esci per uscire."
        update.message.reply_text(msg)
        return SAVE_SUPPLIER

    #save new data to DB:
    supplier = context.user_data['supplier']
    schema = context.user_data['schema']
    ret = db_interactor.add_supplier(schema, supplier, discount)
    if ret == 0:
        msg = f"Fatto! Ti ho salvato produttore {supplier} e relativo sconto medio {discount}% nel magazzino {schema}."
        #check if this state has been reached from the "/product" conversatiion: if so, continue there:
        if context.user_data.get("NEW_SUPPLIER") == True:
            #ask product name:
            msg = f"{msg}\n\nOra scrivimi il nome dettagliato del <b>prodotto</b>. Aggiungi tutte le info necessarie, es.:\n\n<i>Grintuss pediatric sciroppo 12 flaconcini</i>\n\nOppure clicca su /esci per uscire."
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


#"/categoria":
#categoria - 1) ask name of new supplier:
def categoria(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    #get Schema:
    schema = get_schema(update, context)
    if schema == None:
        return CONV_END
    msg = f"Ciao! Registriamo una nuova categoria prodotti, o aggiorniamone l'aliquota IVA, nel magazzino <b>{schema}</b>.\n\n"+\
            f"Inviami il nome della categoria. Oppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return ASK_ALIQUOTA

#categoria - 2) ask typical discount on orders from supplier:
def ask_aliquota(update: Update, context: CallbackContext):
    #store supplier from user message:
    category = update.message.text.lower()
    context.user_data['category'] = category
    #ask discount:
    msg = f"Ricevuto! Ora scrivimi l'aliquota IVA applicabile alla categoria {category} (es. 10%).\n\nOppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SAVE_CATEGORY

#categoria - 3) save new supplier and its typical discount rate on orders:
def save_category(update: Update, context: CallbackContext) -> int:
    #store average discount from user message:
    vat = update.message.text.strip('%')
    vat = vat.replace(',', '.')
    try:
        vat = float(vat)
    except:
        msg = "Re-inviami soltanto l'aliquota in cifre (es. 10%).\n\nOppure clicca su /esci per uscire."
        update.message.reply_text(msg)
        return SAVE_CATEGORY

    #save new data to DB:
    category = context.user_data['category']
    schema = context.user_data['schema']
    ret = db_interactor.add_category(schema, category, vat)
    if ret == 0:
        msg = f"Fatto! Ti ho salvato categoria {category} e relativa aliquota IVA applicabile {vat}% nel magazzino {schema}."
        #check if this state has been reached from the "/product" conversatiion: if so, continue there:
        if context.user_data.get("NEW_CATEGORY") == True:
            #ask product name:
            msg = f"{msg}\n\nMi dici il <b>numero di pezzi</b> che hai in magazzino?\n\nScrivi solo la <i>cifra</i>, es. 1, 10, ...\n\nOppure clicca su /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_CATEGORY"] = None
            return PROCESS_PIECES
        else:
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#"/prodotto":
#prodotto - 1) ask p_code mode: text or photo:
def prodotto(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    #get Schema:
    schema = get_schema(update, context)
    if schema == None:
        return CONV_END
    msg = f"Ciao! Sei nel magazzino <b>{schema}</b>.\n\nPer iniziare, mi serve un <b>codice a barre</b>. Puoi:\n"+\
            f"- Inviarmi una <b>FOTO</b> del codice, oppure\n"+\
            f"- Trascrivermelo via <b>TESTO</b> (SENZA spazi)."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PCODE

#prodotto - 2) process p_code:
def process_pcode(update: Update, context: CallbackContext) -> int:
    p_code = None
    schema = context.user_data.get('schema')
    photo_message = update.message.message_id
    msg = f"Sto estraendo i dati..."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    #1) check if message sent by usercontains a photo:
    if update.message.photo != []:
        #a) extract and store barcode from image:
        try:
            image = update.message.photo[-1].get_file()
            p_code = bot_functions.extract_barcode(image)
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=photo_message)
        except:
            context.bot.delete_message(chat_id=update.effective_chat.id, message_id=photo_message)
            msg = f"Non ho trovato codici.\n\nProva con un'altra foto, o in alternativa trascrivimi il codice a barre.\n\nOppure clicca su /esci per uscire."
            message.edit_text(text=msg)
            return PROCESS_PCODE
    else:
        #b) get code from the text sent by user:
        p_code = update.message.text
        try:
            p_code = int(p_code)
        except:
            msg = f"Il codice deve essere una sequenza di cifre. Prova a reinviarmelo!"
            message.edit_text(text=msg)
            return PROCESS_PCODE

    #2) store barcode in bot memory:
    context.user_data['p_code'] = p_code
    tlog.info(f"Letto codice {p_code}.")
    msg = f"Ho letto il codice {p_code}. "

    #3) check if prod in DB:
    try:
        conn, cursor = db_connect()
        Prodotto = db_interactor.get_product(conn, schema, p_code)
        db_disconnect(conn, cursor)
        #a) if product not found -> new product:
        if Prodotto.empty == True:
            context.user_data['in_db'] = False
            msg = f"{msg}Questo prodotto non è nel mio magazzino. Lo inseriamo ora?"
            keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                        InlineKeyboardButton('No', callback_data='No')]]
            message.edit_text(msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard))
            return INIT_ADD

        #b) if product found -> edit info / add info:
        else:
            context.user_data['in_db'] = True
            #store additional info in bot memory:
            context.user_data['supplier'] = Prodotto['produttore'].iloc[0]
            context.user_data['p_name'] = Prodotto['nome'].iloc[0]
            context.user_data['category'] = Prodotto['categoria'].iloc[0]
            context.user_data['pieces'] = Prodotto['quantita'].iloc[0]
            #ask what to do:
            msg = f"{msg}Ti invio il recap del prodotto:\n"+\
                f"- Produttore: {Prodotto['produttore'].iloc[0]}\n"+\
                f"- Nome: {Prodotto['nome'].iloc[0]}\n"+\
                f"- Categoria: {Prodotto['categoria'].iloc[0]}\n"+\
                f"- Numero di pezzi: {Prodotto['quantita'].iloc[0]}\n"+\
                f"\nCosa vuoi fare?"
            keyboard = [[InlineKeyboardButton('Modifica info', callback_data='Modifica info')],
                        [InlineKeyboardButton('Aggiungi info', callback_data='Aggiungi info')],
                        [InlineKeyboardButton('Annulla', callback_data='Annulla')]]
            message.edit_text(msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard))
            return NEXT_STEP

    except:
        #c) DB error:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END

#ADD 1) init:
def init_add(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
    if choice == 'No':
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        schema = context.user_data.get('schema')
        #supplier picker:
        keyboard = bot_functions.inline_picker(schema, 'produttore')
        msg = f"Iniziamo. Dimmi il nome del <b>produttore</b>. Oppure clicca su /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_SUPPLIER

#common helper:
def ask_pname(update, context, supplier):
    #ask product name:
    msg = f"Segnato produttore '{supplier}'! Ora scrivimi il nome dettagliato del <b>prodotto</b>. Aggiungi tutte le info necessarie, es.:\n\n<i>Grintuss pediatric sciroppo 12 flaconcini</i>\n\nOppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PNAME

#ADD 2) process supplier and ask p_name:
def process_supplier(update: Update, context: CallbackContext) -> int:
    try:
        #IF ALREADY IN DB -> get from query:
        query = update.callback_query
        supplier = query.data
        tlog.info(supplier)
        query.edit_message_reply_markup(reply_markup=None)
        query.answer()
        tlog.info(f"Letto produttore {supplier}.")
        context.user_data['supplier'] = supplier
        #ask next:
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
            msg = f"Il produttore '{supplier}' è nuovo: te lo registro. Scrivimi la percentuale di sconto sugli ordini applicata in media da {supplier} (es. 30%).\n\nOppure clicca su /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_SUPPLIER"] = True
            return SAVE_SUPPLIER
        else:
            #ask next:
            return ask_pname(update, context, supplier)


#ADD 3) process p_name and ask_category:
def process_pname(update: Update, context: CallbackContext) -> int:
    #get prod name sent by user:
    p_name = update.message.text.lower()
    p_name = p_name.replace("'", "")
    #store in bot memory:
    context.user_data['p_name'] = p_name
    tlog.info(f"Letto nome prodotto {p_name}.")
    #next message:
    msg = f"Segnato nome '{p_name}'! Ora dimmi a quale <b>categoria</b> appartiene (es. cosmesi, alimentazione, ...). Oppure clicca su /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    #category picker:
    schema = context.user_data.get('schema')
    keyboard = bot_functions.inline_picker(schema, 'categoria')
    update.message.reply_text(msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    return PROCESS_CATEGORY

#common helper:
def ask_pieces(update, context, category):
    #next message:
    msg = f"Segnata categoria '{category}'! Mi dici il <b>numero di pezzi</b> che hai in magazzino?\n\nScrivi solo la <i>cifra</i>, es. 1, 10, ...\n\nOppure clicca su /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PIECES

#ADD 4) process category and ask p_name:
def process_category(update: Update, context: CallbackContext) -> int:
    try:
        #IF ALREADY IN DB -> get from query:
        query = update.callback_query
        category = query.data
        tlog.info(category)
        query.edit_message_reply_markup(reply_markup=None)
        query.answer()
        tlog.info(f"Letta categoria {category}.")
        context.user_data['category'] = category
        #ask next:
        return ask_pieces(update, context, category)
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
            msg = f"La categoria '{category}' è nuova: te la registro. Scrivimi l'aliquota IVA applicabile alla categoria {category} (es. 10%).\n\nOppure clicca su /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
            context.user_data["last_sent"] = message.message_id
            context.user_data["NEW_CATEGORY"] = True
            return SAVE_CATEGORY
        else:
            #ask next:
            return ask_pieces(update, context, category)

#ADD 5) process pieces:
def process_pieces(update: Update, context: CallbackContext) -> int:
    #1) check caller function:
    to_edit = context.user_data.get('to_edit')
    if (to_edit == None) or (to_edit == 'Quantita'):
        #a) if pieces:
        try:
            pieces = int(update.message.text)
        except:
            msg = "Re-inviami soltanto il numero in cifre (es. 1, 10, ...).\n\nOppure clicca su /esci per uscire."
            update.message.reply_text(msg)
            return PROCESS_PIECES
        #store in bot memory:
        context.user_data['pieces'] = pieces
        tlog.info(f"Letti {pieces} pezzi.")
        msg = f"Segnato {pieces} pezzi. "
    else:
        #b) if to_edit (no pieces):
        mapping = {'Produttore': 'supplier', 'Nome': 'p_name', 'Categoria': 'category', 'Quantita': 'pieces'}
        context.user_data[mapping[to_edit]] = update.message.text.lower()
        context.user_data['to_edit'] = None
        msg = f"Aggiornato. "
    
    #prepare product recap:
    utts = {
        'p_code': int(context.user_data['p_code']),
        'supplier': context.user_data['supplier'],
        'p_name': context.user_data['p_name'],
        'category': context.user_data['category'],
        'pieces': int(context.user_data['pieces']),
    }
    msg = f"{msg}Ti invio il recap del prodotto:\n"+\
            f"- Codice: {utts['p_code']}\n"+\
            f"- Produttore: {utts['supplier']}\n"+\
            f"- Nome: {utts['p_name']}\n"+\
            f"- Categoria: {utts['category']}\n"+\
            f"- Numero di pezzi: {utts['pieces']}\n"+\
            f"\nPosso salvare nel magazzino?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    update.message.reply_text(msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    return SAVE_EDIT

#common helper:
def edit_info(update, context):
    keyboard = [[InlineKeyboardButton('Produttore', callback_data='Produttore'),
                InlineKeyboardButton('Nome', callback_data='Nome')],
                [InlineKeyboardButton('Categoria', callback_data='Categoria'),
                InlineKeyboardButton('Quantita', callback_data='Quantita')],
                [InlineKeyboardButton('Esci', callback_data='Esci')]]
    msg = f"Cosa vuoi modificare?"
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return ASK_REWRITE

#prodotto - 6) process category and ask_quantity:
def save_to_db(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
    err = False

    #trigger STORE TO DB:
    if choice == 'Sì':
        schema = context.user_data.get('schema')
        p_code = context.user_data['p_code']
        utts = {
            'p_code': p_code,
            'supplier': context.user_data['supplier'],
            'p_name': context.user_data['p_name'],
            'category': context.user_data['category'],
            'pieces': int(context.user_data['pieces']),
        }
        try:
            conn, cursor = db_connect()
            if context.user_data.get('in_db') == True:
                ret = db_interactor.delete_prod(conn, cursor, schema, p_code)
            ret = db_interactor.add_prod(conn, cursor, schema, utts)
            db_disconnect(conn, cursor)
        except:
            err = True
        
        if err == True or ret == -1:
            msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
        else:
            msg = f"Ti ho salvato il prodotto nel magazzino!\n\nVuoi che ti faccia qualche altra domanda per categorizzare meglio il prodotto?"
            keyboard = [[InlineKeyboardButton('Sì', callback_data="Aggiungi info"),
                        InlineKeyboardButton('No', callback_data="Modifica info")]]
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["last_sent"] = message.message_id
            return NEXT_STEP
    #trigger EDIT INFO:
    else:
        return edit_info(update, context)

    
#prodotto - 7) decide next step to do:
def next_step(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()

    #"next_step" is called either by:
    # - process_pcode() -> asks options "Edit info", "Add info", "Cancel"
    # - save_to_db() -> asks options "Yes" or "No" to the question "Add info"

    #trigger ADD INFO -> start asking the price:
    if choice == "Sì" or choice == "Aggiungi info":
        #ask price:
        msg = f"Ti farò una serie di brevi domande. Puoi interrompere quando vuoi cliccando su /esci.\n\n"+\
                f"1) Qual è il <b>prezzo al pubblico</b> del prodotto?\n"+\
                f"Scrivi solo la <i>cifra</i> in Euro (es. 10 o 10,50)."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_PRICE
    
    #trigger EXIT:
    elif choice == "No" or choice == "Annulla":
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    
    #trigger EDIT INFO:
    else:
        return edit_info(update, context)

#EDIT:
def ask_rewrite(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    #if end:
    if choice == 'Esci':
        query.edit_message_reply_markup(reply_markup=None)
        query.answer()
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    #else: prepare edit:
    context.user_data['to_edit'] = choice
    query.delete_message()
    query.answer()
    if choice == 'Quantita':
        msg = f"Riscrivi qui il <b>numero</b> corretto di pezzi (nota: solo cifre)."
    else:
        msg = f"Riscrivi qui il testo corretto per il campo <b>{choice}</b>"
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PIECES


#ADD EXTRA INFO:
#extra - 1) save price and ask bool disp medico:
def process_price(update: Update, context: CallbackContext) -> int:
    #store answer from user message:
    price = update.message.text.strip('€')
    price = price.replace(',', '.')
    try:
        price = float(price)
    except:
        msg = "Re-inviami soltanto le cifre del prezzo (es. 10 o 10,50).\n\nOppure clicca su /esci per uscire."
        update.message.reply_text(msg)
        return PROCESS_PRICE

    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'prezzo'
    ret = db_interactor.add_detail(schema, p_code, colname, price)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {price:.2f}€. 2) Il prodotto è un <b>dispositivo medico</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_DISP_MEDICO

#extra - 2) save disp_medico and ask min_age:
def process_disp_medico(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'dispmedico'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. 3) Qual è l'<b>età minima</b> per l'assunzione del prodotto?\n"+\
                f"Scrivimi solo l'età <i>in cifre</i> (es. 18, 3, 0, ...)"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_MIN_AGE

#extra - 3) save min_age and ask bool bio:
def process_min_age(update: Update, context: CallbackContext) -> int:
    #store answer from user message:
    try:
        age = int(update.message.text)
    except:
        msg = "Re-inviami soltanto l'età in cifre (es. 18, 3, 0...).\n\nOppure clicca su /esci per uscire."
        update.message.reply_text(msg)
        return PROCESS_MIN_AGE

    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'etaminima'
    ret = db_interactor.add_detail(schema, p_code, colname, age)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        agestr = "anno" if age == 1 else f"anni"
        msg = f"Segnato {age} {agestr}. 4) Il prodotto è <b>biologico</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_BIO

#extra - 4) save bio and ask bool vegan:
def process_bio(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
    #save new data to DB:
    schema = context.user_data['schema']
    p_code = context.user_data['p_code']
    colname = 'bio'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(schema, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. 5) Il prodotto è <b>vegano</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_VEGAN

#extra - 5) save vegan and ask bool nogluten:
def process_vegan(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
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
        msg = f"Segnato {choice} 6) Il prodotto è <b>senza glutine</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOGLUTEN

#extra - 6) save nogluten and ask bool nolactose:
def process_nogluten(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
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
        msg = f"Segnato {choice}. 7) Il prodotto è <b>senza lattosio</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOLACTOSE

#extra - 7) save nolactose and ask bool nosugar:
def process_nolactose(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
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
        msg = f"Segnato {choice}. 8) Il prodotto è <b>senza zucchero</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOSUGAR

#extra - 8) save nosugar and end:
def process_nosugar(update: Update, context: CallbackContext) -> int:
    #get answer from open query:
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
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
        msg = f"Segnato {choice}.\nHo completato l'aggiornamento del prodotto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#"viste":
def viste(update: Update, context: CallbackContext):
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    #get Schema:
    schema = get_schema(update, context)
    if schema == None:
        return CONV_END
    # try:
    conn, cursor = db_connect()
    Prodotti = db_interactor.get_view_prodotti(conn, schema)
    db_disconnect(conn, cursor)
    if Prodotti.empty == False:
        #build plt table:
        fig, ax =plt.subplots(figsize=(12,4))
        ax.axis('tight')
        ax.axis('off')
        ax.table(cellText=Prodotti.values,colLabels=Prodotti.columns,loc='center')
        #export table to pdf:
        filename = './data_cache/prodotti.pdf'
        pp = PdfPages(filename)
        pp.savefig(fig, bbox_inches='tight')
        pp.close()
        #send pdf:
        pdfdoc = open(filename, 'rb')
        chat_id=update.effective_chat.id
        context.bot.send_document(chat_id, pdfdoc)
        os.remove(filename)
    # except:
    #     msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
    #     update.message.reply_text(msg)


#GENERIC HANDLERS:
#default reply:
def default_reply(update: Update, context: CallbackContext):
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    update.message.reply_text(f"Ciao! {welcome}", parse_mode=ParseMode.HTML)

#cancel and end:
def esci(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
    msg = "Esco. A presto!"
    update.message.reply_text(msg)
    return CONV_END

#error handler: log errors caused by updates:
def error(update: Update, context: CallbackContext) -> int:
    #reset:
    end_open_query(update, context)
    remove_open_keyboards(update, context)
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
    #dispatcher.add_handler(CommandHandler("viste", viste))

    #conversation handlers:
    #/start":
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PICK_WH: [CallbackQueryHandler(pick_wh, pattern='.*')],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #/registrami:
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('registrami', registrami)],
        states={
            SET_AUTH: [MessageHandler(Filters.regex(r'\d+'), set_auth)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #/produttore":
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('produttore', produttore)],
        states={
            ASK_DISCOUNT: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, ask_discount)],
            SAVE_SUPPLIER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, save_supplier)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #/categoria":
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('categoria', categoria)],
        states={
            ASK_ALIQUOTA: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, ask_aliquota)],
            SAVE_CATEGORY: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, save_category)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #add new product ("/nuovo"):
    conv_handler = ConversationHandler(
        entry_points=[
                CommandHandler('prodotto', prodotto),
                MessageHandler(Filters.regex("^(Prodotto|prodotto)$"), prodotto)],
        states={
            PROCESS_PCODE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.photo, process_pcode),
                MessageHandler(Filters.text, process_pcode)],
            INIT_ADD: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(init_add, pattern='.*')],
            PROCESS_SUPPLIER: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_supplier, pattern='.*'),
                MessageHandler(Filters.text, process_supplier)],
            SAVE_SUPPLIER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, save_supplier)],
            PROCESS_PNAME: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, process_pname)],
            PROCESS_CATEGORY: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_category, pattern='.*'),
                MessageHandler(Filters.text, process_category)],
            SAVE_CATEGORY: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, save_category)],
            PROCESS_PIECES: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, process_pieces)],
            SAVE_EDIT: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(save_to_db, pattern='.*')],
            NEXT_STEP: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(next_step, pattern='.*')],
            ASK_REWRITE: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(ask_rewrite, pattern='.*')],
            PROCESS_PRICE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, process_price)],
            PROCESS_DISP_MEDICO: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_disp_medico, pattern='.*')],
            PROCESS_MIN_AGE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.text, process_min_age)],
            PROCESS_BIO: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_bio, pattern='.*')],
            PROCESS_VEGAN: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_vegan, pattern='.*')],
            PROCESS_NOGLUTEN: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_nogluten, pattern='.*')],
            PROCESS_NOLACTOSE: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_nolactose, pattern='.*')],
            PROCESS_NOSUGAR: [
                CommandHandler('esci', esci),
                CallbackQueryHandler(process_nosugar, pattern='.*')],
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
