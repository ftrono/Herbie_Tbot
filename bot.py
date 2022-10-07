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
START, SET_AUTH, PROCESS_VISTA, PROCESS_FILTER = range(0, 4)
PROCESS_PCODE, INIT_ADD, PROCESS_SUPPLIER, PROCESS_PNAME, PROCESS_CATEGORY = range(4, 9)
PROCESS_VAT, PROCESS_PRICE, PROCESS_COST, PROCESS_DISPMEDICO, PROCESS_PIECES = range(9, 14)
NEXT_STEP, EDIT_INFO, SAVE_EDIT = range(14, 17)
PROCESS_VEGAN, PROCESS_NOLACTOSE, PROCESS_NOGLUTEN, PROCESS_NOSUGAR = range(17, 21)
CONV_END = -1 #value of ConversationHandler.END

#default messages:
ask_register = f"Per poter utilizzare il bot è necessario richiedere l'OTP di accesso relativo alla tua licenza all'amministratore. Quando lo avrai ricevuto, utilizza il comando /registrami per registrarti."
welcome = f"\n🤖 <b>Lancia un comando per iniziare!</b>"+\
            f"\n- /prodotto - Registra nuovo o aggiorna dati prodotto"+\
            f"\n- /vista - Scarica vista del magazzino in formato stampa"+\
            f"\n- /registrami - Registrati per l'utilizzo di Herbie Bot"+\
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


#COMMANDS & HELPERS
def check_auth(update, context, chat_id):
    #download updated user authorizations:
    msg = f"Autenticazione in corso..."
    message = context.bot.send_message(chat_id=chat_id, text=msg)
    auth = db_interactor.get_auths(SCHEMA, chat_id)
    context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    return auth

#"/start":
#start - 1) check & get user auth:
def start(update, context):
    #reset:
    reset_priors(update, context)
    #check user authorizations:
    chat_id = update.effective_chat.id
    tlog.info(f"/start launched by user: {chat_id}")
    auth = check_auth(update, context, chat_id)
    #message:
    if auth == -1:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
    else:
        msg = f"Ciao, sono Herbie! Benvenuto nel magazzino {SCHEMA}.\n{welcome}"
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
    ret = db_interactor.register_auth(SCHEMA, chat_id, otp)
    #a) no match -> conv_end:
    if ret == -1:
        msg = f"Registrazione non riuscita.\n\n{ask_register}"
        message.edit_text(msg)
        return CONV_END
    else:
        #b) match found -> launch "/start":
        msg = f"Ciao, sono Herbie! Benvenuto nel magazzino di <b>{SCHEMA.upper()}</b>.\n{welcome}"
        message.edit_text(msg, parse_mode=ParseMode.HTML)
        return CONV_END


#"/prodotto":
#prodotto - 1) ask p_code mode: text or photo:
def prodotto(update, context):
    reset_priors(update, context)
    #check auth:
    chat_id = update.effective_chat.id
    auth = check_auth(update, context, chat_id)
    if auth == -1:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Inviami un <b>codice a barre</b>. Puoi:\n"+\
                f"- Inviarmi una <b>FOTO</b>, oppure\n"+\
                f"- <b>Trascrivermi</b> il codice (SENZA spazi).\n\n"+\
                f"Se il prodotto è già registrato, puoi anche scrivermi il <b>nome</b>.\n\nAltrimenti usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_PCODE

#prodotto - 2) process p_code:
def process_pcode(update, context):
    p_code = None
    from_match = False
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
            p_code, rem = bot_functions.code_to_int(p_code)
            #p_code = rem + str(p_code)
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
            p_code, rem = bot_functions.code_to_int(p_text)
            #p_code = rem + str(p_num)
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
                        tlog.info(f"Trovato codice numerico {p_code}.")
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
            Matches = db_interactor.match_product(SCHEMA, p_text=p_text)

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
            Matches = db_interactor.match_product(SCHEMA, p_code=p_code)
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
        #store all match info in bot's memory:
        context.user_data['supplier'] = Matches['produttore'].iloc[0]
        context.user_data['p_name'] = Matches['nome'].iloc[0]
        context.user_data['category'] = Matches['categoria'].iloc[0]
        context.user_data['vat'] = Matches['aliquota'].iloc[0]
        context.user_data['price'] = Matches['prezzo'].iloc[0]
        context.user_data['cost'] = Matches['costo'].iloc[0]
        context.user_data['pieces'] = Matches['quantita'].iloc[0]
        context.user_data['dispmedico'] = Matches['dispmedico'].iloc[0]
        #ask what to do:
        msg = f"{msg}Ti invio il recap del prodotto:\n"+\
            f"- Produttore: <i>{Matches['produttore'].iloc[0]}</i>\n"+\
            f"- Nome: <i>{Matches['nome'].iloc[0]}</i>\n"+\
            f"- Categoria: <i>{Matches['categoria'].iloc[0]}</i>\n"+\
            f"- IVA: <i>{Matches['aliquota'].iloc[0]}%</i>\n"+\
            f"- Prezzo: <i>{Matches['prezzo'].iloc[0]:.2f}€</i>\n"+\
            f"- Costo: <i>{Matches['costo'].iloc[0]:.2f}€</i>\n"+\
            f"- Numero di pezzi: <i>{Matches['quantita'].iloc[0]}</i>\n"+\
            f"- Disp medico: <i>{'Sì' if Matches['dispmedico'].iloc[0] == True else 'No'}</i>\n"+\
            f"\nCosa vuoi modificare?"
        keyboard = [[InlineKeyboardButton('Modifica quantità', callback_data='Modifica quantita')],
                    [InlineKeyboardButton('Info prodotto', callback_data='Modifica info'),
                    InlineKeyboardButton('Vegano/allergeni', callback_data='Modifica extra')],
                    [InlineKeyboardButton('Esci', callback_data='Esci')]]
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
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Iniziamo. "
    #supplier picker:
    keyboard = bot_functions.inline_picker(SCHEMA, 'produttore')
    msg = f"{msg}Dimmi il nome del <b>produttore</b>. Oppure usa /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_SUPPLIER

#ADD 2) process supplier and ask next:
def process_supplier(update, context):
    try:
        #IF FROM KEYBOARD -> get from query:
        supplier = answer_query(update, context)
        tlog.info(f"Letto produttore {supplier}.")
        context.user_data['supplier'] = supplier
    except:
        #IF FROM TEXT -> get from user message:
        supplier = update.message.text.lower()
        context.user_data['supplier'] = supplier
        tlog.info(f"Letto produttore {supplier}.")
        remove_open_keyboards(update, context)
    #ask next:
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        return ask_pname(update, context, supplier)

#common helper:
def ask_pname(update, context, supplier=None):
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
        msg = f"Scrivimi a quale <b>categoria</b> appartiene il prodotto"
    else:
        msg = f"Segnato nome '{p_name}'! Ora dimmi a quale <b>categoria</b> appartiene il prodotto"
    msg = f"{msg} (es. cosmesi, alimentazione, ...). Oppure usa /esci per uscire.\n\nNOTA: Se non è fra i suggerimenti, inviami direttamente il nome."
    #category picker:
    keyboard = bot_functions.inline_picker(SCHEMA, 'categoria')
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_CATEGORY

#ADD 4) process category and ask next:
def process_category(update, context):
    try:
        #IF FROM KEYBOARD -> get from query:
        category = answer_query(update, context)
        tlog.info(f"Letta categoria {category}.")
        context.user_data['category'] = category
    except:
        #IF FROM TEXT -> get from user message:
        category = update.message.text.lower()
        context.user_data['category'] = category
        tlog.info(f"Letta categoria {category}.")
        remove_open_keyboards(update, context)
    #ask next:
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        return ask_vat(update, context, category)

#common helper:
def ask_vat(update, context, category=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f"Dimmi"
    else:
        msg = f"Segnata categoria '{category}'! Ora dimmi"
    msg = f"{msg} l'<b>aliquota IVA</b> applicabile.\n\nOppure usa /esci per uscire."
    #vat picker:
    keyboard = []
    buf = []
    for rate in VAT:
        buf.append(InlineKeyboardButton(f"{rate}%", callback_data=str(rate)))
    keyboard.append(buf)
    #message:
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_VAT

#ADD 5) process vat and ask next:
def process_vat(update, context):
    try:
        #IF FROM KEYBOARD -> get from query:
        vat = answer_query(update, context)
        tlog.info(f"Letta aliquota {vat}%.")
        context.user_data['vat'] = vat
    except:
        #IF FROM TEXT -> get from user message:
        vat = update.message.text.lower()
        vat = vat.strip('%')
        vat = vat.replace(',', '.')
        vat = vat.replace(' ', '')
        try:
            vat = float(vat)
        except:
            msg = "Re-inviami soltanto le cifre dell'aliquota IVA (es. se 22%, invia solo 22), senza simboli o spazi.\n\nOppure usa /esci per uscire."
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
            return PROCESS_VAT
        context.user_data['vat'] = vat
        tlog.info(f"Letta aliquota {vat}%.")
        remove_open_keyboards(update, context)
    #ask next:
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        return ask_price(update, context, vat)

#common helper:
def ask_price(update, context, vat=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnata aliquota {vat}%! "
    msg = f"{msg}Qual è il <b>prezzo al pubblico</b> del prodotto?\n"+\
            f"Scrivi solo la <i>cifra</i> in Euro (es. 10 o 10,50)."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PRICE

#ADD 6) process price and ask next:
def process_price(update, context):
    #store answer from user message:
    price = update.message.text.strip('€')
    price = price.replace(',', '.')
    price = price.replace(' ', '')
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
        return ask_cost(update, context, price)

#common helper:
def ask_cost(update, context, price=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnato prezzo {price:.2f}€! "
    msg = f"{msg}Qual è il <b>costo d'acquisto</b> del prodotto?\n"+\
            f"Scrivi solo la <i>cifra</i> in Euro (es. 8 o 8,50)."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_COST

#ADD 7) process cost and ask next:
def process_cost(update, context):
    #store answer from user message:
    cost = update.message.text.strip('€')
    cost = cost.replace(',', '.')
    cost = cost.replace(' ', '')
    try:
        cost = float(cost)
    except:
        msg = "Re-inviami soltanto le cifre del costo d'acquisto (es. 8 o 8,50), senza simboli o parole.\n\nOppure usa /esci per uscire."
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return PROCESS_COST

    #store in bot memory:
    context.user_data['cost'] = cost
    tlog.info(f"Letto costo {cost:.2f} €.")
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        #ask next:
        return ask_dispmedico(update, context, cost)

#common helper:
def ask_dispmedico(update, context, cost):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnato costo {cost:.2f}€! "
    msg = f"{msg}Il prodotto è un <b>dispositivo medico</b>?"
    keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                InlineKeyboardButton('No', callback_data='No')]]
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data["last_sent"] = message.message_id
    return PROCESS_DISPMEDICO

#ADD 8) save dispmedico and ask next:
def process_dispmedico(update, context):
    try:
        #IF FROM KEYBOARD -> get from query:
        disp = answer_query(update, context)
        tlog.info(f"Letto disp medico: {disp}%.")
        context.user_data['dispmedico'] = disp
    except:
        #IF FROM TEXT -> ask again:
        remove_open_keyboards(update, context)
        cost = context.user_data.get('cost')
        return ask_dispmedico(update, context, cost)
    #ask next:
    #if caller is edit info -> return to state Recap:
    if context.user_data.get('to_edit') != None:
        return process_pieces(update, context)
    else:
        return ask_pieces(update, context, disp)

#common helper:
def ask_pieces(update, context, disp=None):
    #if caller is edit info:
    if context.user_data.get('to_edit') != None:
        msg = f""
    else:
        msg = f"Segnato '{disp}'. "
    msg = f"{msg}Mi dici il <b>numero di pezzi</b> che hai in magazzino?\n\nScrivi solo la <i>cifra</i>, es. 1, 10, ...\n\nOppure usa /esci per uscire."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    context.user_data["last_sent"] = message.message_id
    return PROCESS_PIECES

#ADD 9) process quantity and show Recap:
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
        'vat': float(context.user_data['vat']),
        'price': float(context.user_data['price']),
        'cost': float(context.user_data['cost']),
        'dispmedico': context.user_data['dispmedico'],
        'pieces': int(context.user_data['pieces']),
    }
    msg = f"{msg}Ti invio il recap del prodotto:\n"+\
            f"- Codice: <i>{info['p_code']}</i>\n"+\
            f"- Produttore: <i>{info['supplier']}</i>\n"+\
            f"- Nome: <i>{info['p_name']}</i>\n"+\
            f"- Categoria: <i>{info['category']}</i>\n"+\
            f"- IVA: <i>{info['vat']}%</i>\n"+\
            f"- Prezzo: <i>{info['price']:.2f}€</i>\n"+\
            f"- Costo: <i>{info['cost']:.2f}€</i>\n"+\
            f"- Dispositivo medico: <i>{info['dispmedico']}</i>\n"+\
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
        p_code = context.user_data['p_code']
        info = {
            'p_code': p_code,
            'supplier': context.user_data['supplier'],
            'p_name': context.user_data['p_name'],
            'category': context.user_data['category'],
            'vat': float(context.user_data['vat']),
            'price': float(context.user_data['price']),
            'cost': float(context.user_data['cost']),
            'dispmedico': True if context.user_data['dispmedico'] == 'Sì' else False,
            'pieces': int(context.user_data['pieces']),
        }
        #save to DB:
        ret = db_interactor.register_prodinfo(SCHEMA, info)
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message.message_id)
        if ret == -1:
            msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = message.message_id
        else:
            msg = f"Ti ho salvato il prodotto nel magazzino!\n\nA presto!"
            message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            context.user_data["last_sent"] = None
        return CONV_END
    #trigger EDIT INFO:
    else:
        return edit_picker(update, context)

#"next_step" is called by process_pcode() -> asks options "Edit quantity", "Edit info", "Cancel":
def next_step(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)

    #trigger EDIT QUANTITY -> direct to ask_pieces:
    if choice == "Modifica quantita":
        context.user_data['to_edit'] = 'Quantita'
        return ask_pieces(update, context)

    elif choice == "Modifica extra":
        return ask_vegan(update, context)
    
    #trigger EXIT:
    elif choice == "Esci":
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
                InlineKeyboardButton('IVA', callback_data='IVA')],
                [InlineKeyboardButton('Prezzo', callback_data='Prezzo'),
                InlineKeyboardButton('Costo', callback_data='Costo')],
                [InlineKeyboardButton('Disp medico', callback_data='Disp medico'),
                InlineKeyboardButton('Quantita', callback_data='Quantita')],
                [InlineKeyboardButton('ESCI', callback_data='Esci')]]
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
    elif choice == 'IVA':
        return ask_vat(update, context)
    elif choice == 'Prezzo':
        return ask_price(update, context)
    elif choice == 'Costo':
        return ask_cost(update, context)
    elif choice == 'Disp medico':
        return ask_dispmedico(update, context)
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
    msg = f"Ti farò una serie di brevi domande. Puoi interrompere quando vuoi cliccando su /esci.\nPrima domanda:\n"+\
            f"- Il prodotto è <b>vegano</b>?"
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
    p_code = context.user_data['p_code']
    colname = 'vegano'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(SCHEMA, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        #if a product is vegan, it does not have lactose -> skip state "nolactose" (the DB will auto update 'senzalattosio'):
        if choice == 'Sì':
            choicestr = "Vegano e Senza Lattosio"
            feat = f"senza glutine"
            next_state = PROCESS_NOGLUTEN
        else:
            choicestr = 'No'
            feat = f"senza lattosio"
            next_state = PROCESS_NOLACTOSE
        msg = f"Segnato {choicestr}. Prossima:\n- Il prodotto è <b>{feat}</b>?"
        keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                    InlineKeyboardButton('No', callback_data='No')]]
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return next_state

#extra - 3) save nolactose and ask bool nogluten:
def process_nolactose(update, context):
    #get answer from open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #save new data to DB:
    p_code = context.user_data['p_code']
    colname = 'senzalattosio'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(SCHEMA, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. Prossima:\n- Il prodotto è <b>senza glutine</b>?"
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
    p_code = context.user_data['p_code']
    colname = 'senzaglutine'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(SCHEMA, p_code, colname, value)
    if ret == -1:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        msg = f"Segnato {choice}. Prossima:\n- Il prodotto è <b>senza zucchero</b>?"
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
    p_code = context.user_data['p_code']
    colname = 'senzazucchero'
    value = True if choice == 'Sì' else False
    ret = db_interactor.add_detail(SCHEMA, p_code, colname, value)
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


#"/vista":
def vista(update, context):
    reset_priors(update, context)
    #check auth:
    chat_id = update.effective_chat.id
    auth = check_auth(update, context, chat_id)
    if auth == -1:
        msg = f"Benvenuto! Non conosco il tuo chat ID.\n\n{ask_register}"
        tlog.info(f"New tentative user: {chat_id}")
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        #keyboard for /vista:
        actionstr = f"Quale vista vuoi estrarre?"
        buttons = ['Magazzino', 'Filtra', 'Lista ordine', 'Esci']
        msg = f"Ciao! Sei nel magazzino di <b>{SCHEMA.upper()}</b>.\n\n🤖📦✏ <b>{actionstr}</b>"
        keyboard = []
        for button in buttons:
            keyboard.append([InlineKeyboardButton(button, callback_data=button)])
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_VISTA

#process choice after main menu:
def process_vista(update, context):
    #get open query:
    choice = answer_query(update, context)
    tlog.info(choice)
    #sorter:
    if choice == 'Esci':
        msg = f"Ok. A presto!"
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        context.user_data["last_sent"] = message.message_id
        return CONV_END
    else:
        choice = choice.lower()
        if choice == 'lista ordine':
            choice = 'lista'
        context.user_data['vista'] = choice
        return ask_filter(update, context)

#viste - 1) filter:
def ask_filter(update, context):
    choice = context.user_data.get('vista')
    if choice == 'filtra':
        msg = f"Seleziona il <b>produttore</b> di cui vuoi estrarre le giacenze.\n\nOppure usa /esci per uscire."
        #supplier picker:
        keyboard = [[InlineKeyboardButton('Magazzino intero', callback_data='all')]]
        temp = bot_functions.inline_picker(SCHEMA, 'produttore')
        keyboard = keyboard + temp
        message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["last_sent"] = message.message_id
        return PROCESS_FILTER
    elif choice == 'lista':
        msg = f"Seleziona una lista ordini da estrarre\n(formato: <i>'produttore - data ultima modifica - DEF (se definitiva)'</i>).\n\nOppure usa /esci per uscire."
        #ordlist picker:
        History = db_interactor.get_storicoordini(SCHEMA)
        keyboard = []
        for ind in History.index:
            definitive = f" - DEF" if History['definitiva'].iloc[ind] == True else ""
            keystr = f"{History['produttore'].iloc[ind]} - {History['datamodifica'].iloc[ind]}{definitive}"
            keyboard.append([InlineKeyboardButton(str(keystr), callback_data=str(History['codiceord'].iloc[ind]))])
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
        filter = answer_query(update, context, delete=True)
        tlog.info(f"Filter: {filter}")
    except:
        filter = update.message.text.lower()
    context.user_data['filter'] = filter
    return get_vista(update, context)

#viste - 3) extract vista:
def get_vista(update, context):
    choice = context.user_data.get('vista')
    msg = f"Estrazione vista in corso..."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    #get vista:
    filter = context.user_data.get('filter')
    filter = filter if filter != 'all' else None
    filterstr = f"_{filter}" if filter else ""
    filename = f'./data_cache/{SCHEMA}.{choice}{filterstr}.xlsx'
    #forker:
    if choice == 'magazzino':
        ret = bot_functions.create_view_prodotti(SCHEMA, filename)
    elif choice == 'filtra':
        ret = bot_functions.create_view_prodotti(SCHEMA, filename, filter)
    elif choice == 'lista':
        ordcode = int(filter)
        ret, filename = bot_functions.create_view_listaordine(SCHEMA, ordcode)
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

    #/vista:
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('vista', vista),
            MessageHandler(Filters.regex("^(Vista|vista)$"), vista)],
        states={
            PROCESS_VISTA: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_vista, pattern='.*')],
            PROCESS_FILTER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_filter, pattern='.*'),
                MessageHandler(Filters.text, process_filter)],
        },
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #states for product conversation:
    states1 = {
            PROCESS_PCODE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.photo, process_pcode),
                MessageHandler(Filters.text, process_pcode)],
                }
    states2 = {
            INIT_ADD: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(init_add, pattern='.*')],
            PROCESS_SUPPLIER: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_supplier, pattern='.*'),
                MessageHandler(Filters.text, process_supplier)],
            PROCESS_PNAME: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_pname)],
            PROCESS_CATEGORY: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_category, pattern='.*'),
                MessageHandler(Filters.text, process_category)],
            PROCESS_VAT: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_vat, pattern='.*'),
                MessageHandler(Filters.text, process_vat)],
            PROCESS_PRICE: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_price)],
            PROCESS_COST: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                MessageHandler(Filters.text, process_cost)],
            PROCESS_DISPMEDICO: [
                CommandHandler('esci', esci),
                MessageHandler(Filters.regex("^(Esci|esci|Annulla|annulla|Stop|stop)$"), esci),
                CallbackQueryHandler(process_dispmedico, pattern='.*'),
                MessageHandler(Filters.text, process_dispmedico)],
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
        }
    merged_states = {**states1, **states2}

    #"/prodotto": command call:
    conv_handler = ConversationHandler(
        entry_points=[
                CommandHandler('prodotto', prodotto),
                MessageHandler(Filters.regex("^(Prodotto|prodotto|Cerca|cerca|Nuovo|nuovo)$"), prodotto)],
        states=merged_states,
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #"/prodotto": direct send photo:
    conv_handler = ConversationHandler(
        entry_points=[
                MessageHandler(Filters.photo, process_pcode)],
        states=states2,
        fallbacks=[CommandHandler('error', error)],
        allow_reentry=True)
    dispatcher.add_handler(conv_handler)

    #message handlers:
    dispatcher.add_handler(MessageHandler(Filters.text, default_reply))

    #log all errors:
    dispatcher.add_error_handler(error)

    #webhook:
    if ENV == 'cloud':
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
