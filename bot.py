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
START, SET_AUTH = range(2)
PICK_WH, PROCESS_MENU, PROCESS_PCODE, ASK_DISCOUNT, ASK_ALIQUOTA, INIT_ADD, PROCESS_SUPPLIER, SAVE_SUPPLIER, PROCESS_PNAME, PROCESS_CATEGORY, SAVE_CATEGORY, PROCESS_PRICE, PROCESS_PIECES, SAVE_EDIT, NEXT_STEP, EDIT_INFO, PROCESS_DISP_MEDICO, PROCESS_MIN_AGE, PROCESS_BIO, PROCESS_VEGAN, PROCESS_NOGLUTEN, PROCESS_NOLACTOSE, PROCESS_NOSUGAR = range(23)
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
        msg = f"Ciao, sono Herbie! Sei registrato nei magazzini di:\n<b>{authlist}</b>.\n{welcome}"
        tlog.info(f"Downloaded updated auths for user: {chat_id}")
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return CONV_END

#"/registrami":
#registrami - 1) ask OTP:
def registrami(update: Update, context: CallbackContext):
    #reset:
    reset_priors(update, context)
    #asks user to send the OTP:
    chat_id = update.effective_chat.id
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
    query = update.callback_query
    schema = query.data
    tlog.info(schema)
    query.delete_message()
    query.answer()
    context.user_data['schema'] = schema
    return main_menu(update, context, schema)


#MAIN MENU:
#main menu for both "/aggiorna" and "/vista":
def main_menu(update, context, schema):
    #keyboard:
    if context.user_data.get('caller') == 'aggiorna':
        #/aggiorna:
        actionstr = f"Cosa vuoi aggiornare?"
        buttons = ['Prodotto', 'Produttore', 'Categoria', 'Esci']
    else:
        #/vista:
        actionstr = f"Quale vista vuoi estrarre?"
        buttons = ['Prodotto', 'Produttore', 'Categoria', 'Storico ordini', 'Lista ordini', 'Esci']
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
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    query.edit_message_reply_markup(reply_markup=None)
    query.answer()
    caller = context.user_data.get('caller')
    #sorter:
    if caller == 'aggiorna':
        if choice == 'Prodotto':
            return prodotto(update, context)
        elif choice == 'Produttore':
            return produttore(update, context)
        elif choice == 'Categoria':
            return categoria(update, context)
        else:
            msg = f"Ok. A presto!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END
    else:
        if choice == 'Prodotto':
            return vista_prodotti(update, context)
        else:
            msg = f"Ok. A presto!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return CONV_END

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


#PRODUTTORE:
#produttore - 1) ask name of new supplier:
def produttore(update, context):
    msg = f"Registriamo un nuovo <b>produttore</b>, o aggiorniamone lo sconto medio sugli ordini.\n\n"+\
            f"Inviami il nome del produttore. Oppure usa /esci per uscire."
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
    msg = f"Ricevuto! Ora scrivimi la percentuale di sconto sugli ordini applicata in media da {supplier} (es. 30%).\n\nOppure usa /esci per uscire."
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
    ret = db_interactor.add_supplier(schema, supplier, discount)
    if ret == 0:
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


#"CATEGORIA":
#categoria - 1) ask name of new supplier:
def categoria(update, context):
    msg = f"Registriamo una nuova <b>categoria</b> prodotti, o aggiorniamone l'aliquota IVA.\n\n"+\
            f"Inviami il nome della categoria. Oppure usa /esci per uscire."
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
    msg = f"Ricevuto! Ora scrivimi l'aliquota IVA applicabile alla categoria {category} (es. 10%).\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    context.user_data["last_sent"] = message.message_id
    return SAVE_CATEGORY

#categoria - 3) save new supplier and its typical discount rate on orders:
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
    ret = db_interactor.add_category(schema, category, vat)
    if ret == 0:
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


#"/prodotto":
#prodotto - 1) ask p_code mode: text or photo:
def prodotto(update, context):
    msg = f"Per iniziare, devo <b>identificare un prodotto</b>. Puoi:\n"+\
            f"- Inviarmi una <b>FOTO</b> del codice a barre, oppure\n"+\
            f"- Inviarmi il <b>NOME</b> del prodotto, oppure\n"+\
            f"- Trascrivermi il codice a barre via <b>TESTO</b> (SENZA spazi)."
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
            msg = f"Ho letto il codice {p_code}. "
            context.user_data['p_code'] = int(p_code)
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
            #try conversion to int:
            p_code = int(p_text)

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
        keyboard = [[InlineKeyboardButton('Modifica info', callback_data='Modifica info')],
                    [InlineKeyboardButton('Aggiungi info', callback_data='Aggiungi info')],
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

#ADD 2) process supplier and ask p_name:
def process_supplier(update, context):
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
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
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
            else:
                #ask next:
                return ask_pname(update, context, supplier)

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
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f"Scrivimi"
    else:
        msg = f"Segnato nome '{p_name}'! Ora dimmi"
    msg = f"{msg} a quale <b>categoria</b> appartiene il prodotto (es. cosmesi, alimentazione, ...). Oppure usa /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    #category picker:
    schema = context.user_data.get('schema')
    keyboard = bot_functions.inline_picker(schema, 'categoria')
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_CATEGORY

#ADD 4) process category and ask price:
def process_category(update, context):
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
        #if caller is edit info -> return to state Recap:
        if context.user_data.get('to_edit') != None:
            return process_pieces(update, context)
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
            else:
                #ask next:
                return ask_price(update, context, category)

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
        return ask_disp_medico(update, context)
    
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
    query = update.callback_query
    choice = query.data
    tlog.info(choice)
    context.user_data['to_edit'] = choice
    query.delete_message()
    query.answer()
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
#extra - 1) ask bool disp medico:
def ask_disp_medico(update, context):
    msg = f"Ti farò una serie di brevi domande. Puoi interrompere quando vuoi cliccando su /esci.\n\n"+\
            f"1) Il prodotto è un <b>dispositivo medico</b>?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_DISP_MEDICO

#extra - 2) save disp_medico and ask min_age:
def process_disp_medico(update, context):
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
        msg = f"Segnato {choice}. Prossima:\n\n2) Qual è l'<b>età minima</b> per l'assunzione del prodotto?\n"+\
                f"Scrivimi solo l'età <i>in cifre</i> (es. 18, 3, 0, ...)"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_MIN_AGE

#extra - 3) save min_age and ask bool bio:
def process_min_age(update, context):
    #store answer from user message:
    try:
        age = int(update.message.text)
    except:
        msg = "Re-inviami soltanto l'età in cifre (es. 18, 3, 0...).\n\nOppure usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
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
        msg = f"Segnato {age} {agestr}. Prossima:\n\n3) Il prodotto è <b>biologico</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_BIO

#extra - 4) save bio and ask bool vegan:
def process_bio(update, context):
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
        msg = f"Segnato {choice}. Prossima:\n\n4) Il prodotto è <b>vegano</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_VEGAN

#extra - 5) save vegan and ask bool nogluten:
def process_vegan(update, context):
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
        msg = f"Segnato {choice}. Prossima:\n\n5) Il prodotto è <b>senza glutine</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOGLUTEN

#extra - 6) save nogluten and ask bool nolactose:
def process_nogluten(update, context):
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
        msg = f"Segnato {choice}. Prossima:\n\n6) Il prodotto è <b>senza lattosio</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOLACTOSE

#extra - 7) save nolactose and ask bool nosugar:
def process_nolactose(update, context):
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
        msg = f"Segnato {choice}. Prossima:\n\n7) Il prodotto è <b>senza zucchero</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_NOSUGAR

#extra - 8) save nosugar and end:
def process_nosugar(update, context):
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
        msg = f"Segnato {choice}.\n\nHo completato l'aggiornamento del prodotto. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END


#"viste":
def vista_prodotti(update: Update, context: CallbackContext):
    #get view:
    schema = context.user_data.get('schema')
    filename = './data_cache/prodotti.xlsx'
    ret = bot_functions.create_view_prodotti(schema, filename)
    if ret == 0:
        #3) send file to user:
        xlsx = open(filename, 'rb')
        chat_id=update.effective_chat.id
        context.bot.send_document(chat_id, xlsx)
        os.remove(filename)
    else:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id


#GENERIC HANDLERS:
#default reply:
def default_reply(update: Update, context: CallbackContext):
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
            PROCESS_DISP_MEDICO: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_disp_medico, pattern='.*')],
            PROCESS_MIN_AGE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_min_age)],
            PROCESS_BIO: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_bio, pattern='.*')],
            PROCESS_VEGAN: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_vegan, pattern='.*')],
            PROCESS_NOGLUTEN: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nogluten, pattern='.*')],
            PROCESS_NOLACTOSE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nolactose, pattern='.*')],
            PROCESS_NOSUGAR: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_nosugar, pattern='.*')],
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
