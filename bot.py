from telegram import ReplyKeyboardRemove, Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, CallbackContext
import database.db_interactor as db_interactor
from database.db_tools import db_connect
import bot_functions
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from globals import *

#HERBIE TELEGRAM BOT
#GLOBALS:
PROCESS_PCODE, INIT_ADD, PROCESS_SUPPLIER, PROCESS_PNAME, PROCESS_CATEGORY, PROCESS_PIECES, SAVE_EDIT, ASK_REWRITE = range(8)
CONV_END = -1 #value of ConversationHandler.END

#START:
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Ciao!")

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)

def error(update, context):
    """Log Errors caused by Updates."""
    tlog.warning('Update "%s" caused error "%s"', update, context.error)

#ADD NEW PRODUCT TO DB:
#1) ask p_code mode: text or photo:
def prodotto(update: Update, context: CallbackContext) -> int:
    msg = f"Ciao! Per iniziare, mi serve un <b>codice a barre</b>. Puoi:\n"+\
            f"- Inviarmi una <b>FOTO</b> del codice, oppure\n"+\
            f"- Trascrivermelo via <b>TESTO</b> (SENZA spazi)."
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
        parse_mode=ParseMode.HTML)
    return PROCESS_PCODE

#3) process p_code:
def process_pcode(update: Update, context: CallbackContext) -> int:
    p_code = None
    msg = f"Sto estraendo i dati..."
    message = context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    #1) check if message sent by usercontains a photo:
    if update.message.photo != []:
        #a) extract and store barcode from image:
        try:
            image = update.message.photo[-1].get_file()
            p_code = bot_functions.extract_barcode(image)
        except:
            msg = f"Non ho trovato codici.\n\nProva con un'altra foto, o in alternativa trascrivimi il codice a barre.\n\nOppure scrivi /esci per uscire."
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
        prod = db_interactor.get_prodinfo(conn, {'p_code': p_code})
        conn.close()
        #a) if product not found -> new product:
        if prod == []:
            context.user_data['in_db'] = False
            msg = f"{msg} Questo prodotto non è nel mio magazzino. Lo inseriamo ora?"
            keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                        InlineKeyboardButton('No', callback_data='No')]]
            message.edit_text(msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard))
            return INIT_ADD

        #b) if product found -> edit info / add info:
        else:
            prod = prod[0]
            context.user_data['in_db'] = True
            #store additional info in bot memory:
            context.user_data['supplier'] = prod['supplier']
            context.user_data['p_name'] = prod['p_name']
            context.user_data['category'] = prod['category']
            context.user_data['pieces'] = prod['pieces']
            #ask what to do:
            msg = f"{msg}Ti invio il recap del prodotto:\n"+\
                f"- Produttore: {prod['supplier']}\n"+\
                f"- Nome: {prod['p_name']}\n"+\
                f"- Categoria: {prod['category']}\n"+\
                f"- Numero di pezzi: {prod['pieces']}\n"+\
                f"\nCosa vuoi fare?"
            keyboard = [[InlineKeyboardButton('Modifica info', callback_data='Modifica info')],
                        [InlineKeyboardButton('Aggiungi info', callback_data='Aggiungi info')],
                        [InlineKeyboardButton('Annulla', callback_data='Annulla')]]
            message.edit_text(msg,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard))
            return SAVE_EDIT

    except:
        #c) DB error:
        msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
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
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        return CONV_END
    else:
        #supplier picker:
        keyboard = bot_functions.inline_picker('Produttore')
        msg = f"Iniziamo. Dimmi il nome del <b>produttore</b>.\n\nOppure scrivi /esci per uscire."
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg, 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard))
        return PROCESS_SUPPLIER

#ADD 2.a) new supplier:
def new_supplier(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    context.user_data['supplier'] = 'NEW'
    tlog.info(choice)
    query.delete_message()
    query.answer()
    #ask new:
    msg = f"Scrivimi il nome del <b>produttore</b>.\n\nOppure scrivi /esci per uscire."
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    return PROCESS_SUPPLIER

#ADD 2.b) process supplier and ask p_name:
def process_supplier(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('supplier') == 'NEW':
        supplier = update.message.text.lower()
    else:
        #get from query:
        query = update.callback_query
        supplier = query.data
        tlog.info(supplier)
        query.edit_message_reply_markup(reply_markup=None)
        query.answer()
    #store in bot memory:
    context.user_data['supplier'] = supplier
    tlog.info(f"Letto produttore {supplier}.")
    #next message:
    msg = f"Segnato produttore {supplier}! Ora scrivimi il nome dettagliato del <b>prodotto</b>. Aggiungi tutte le info necessarie, es.:\n\n<i>Grintuss pediatric sciroppo 12 flaconcini</i>\n\nOppure scrivi /esci per uscire."
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    return PROCESS_PNAME

#ADD 3) process p_name and ask_category:
def process_pname(update: Update, context: CallbackContext) -> int:
    #get prod name sent by user:
    p_name = update.message.text.lower()
    p_name = p_name.replace("'", "")
    #store in bot memory:
    context.user_data['p_name'] = p_name
    tlog.info(f"Letto nome prodotto {p_name}.")
    #next message:
    msg = f"Segnato nome {p_name}! Ora dimmi a quale <b>categoria</b> appartiene (es. cosmesi, alimentazione, ...).\n\nOppure scrivi /esci per uscire."
    #category picker:
    keyboard = bot_functions.inline_picker('Categoria')
    update.message.reply_text(msg, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup(keyboard))
    return PROCESS_CATEGORY


#ADD 4.a) new category:
def new_category(update: Update, context: CallbackContext) -> int:
    #get open query:
    query = update.callback_query
    choice = query.data
    #store choice:
    context.user_data['category'] = 'NEW'
    tlog.info(choice)
    #answer query:
    query.delete_message()
    query.answer()
    #ask new:
    msg = f"Scrivimi il nome della <b>nuova categoria</b>.\n\nOppure scrivi /esci per uscire."
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    return PROCESS_CATEGORY

#ADD 4.b) process category and ask p_name:
def process_category(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('category') == 'NEW':
        category = update.message.text.lower()
    else:
        #get from query:
        query = update.callback_query
        category = query.data
        tlog.info(category)
        query.edit_message_reply_markup(reply_markup=None)
        query.answer()
    #store in bot memory:
    context.user_data['category'] = category
    tlog.info(f"Letta categoria {category}.")
    #next message:
    msg = f"Segnata categoria {category}! Mi dici il <b>numero di pezzi</b> che hai in magazzino?\n\nScrivi solo la <i>cifra</i>, es. 1, 10, ...\n\nOppure scrivi /esci per uscire."
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    return PROCESS_PIECES

#ADD 5) process pieces:
def process_pieces(update: Update, context: CallbackContext) -> int:
    #1) check caller function:
    to_edit = context.user_data.get('to_edit')
    if (to_edit == None) or (to_edit == 'Quantita'):
        #a) if pieces:
        try:
            pieces = int(update.message.text)
        except:
            msg = "Re-inviami soltanto il numero in cifre (es. 1, 10, ...).\n\nOppure scrivi /esci per uscire."
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


#6) process category and ask_quantity:
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
        p_code = int(context.user_data['p_code'])
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
                ret = db_interactor.delete_prod(conn, cursor, p_code)
            ret = db_interactor.add_prod(conn, cursor, utts)
            conn.close()
        except:
            err = True
        
        if err == True or ret == -1:
            msg = f"C'è stato un problema col mio DB, ti chiedo scusa!"
            context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
            return CONV_END
        else:
            msg = f"Ti ho salvato il prodotto nel magazzino!\n\nVuoi che ti faccia qualche altra domanda per categorizzare meglio il prodotto?"
            keyboard = [[InlineKeyboardButton('Sì', callback_data='Sì'),
                        InlineKeyboardButton('No', callback_data='No')]]
            context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard))
            return CONV_END

    #trigger ADD INFO:
    elif choice == "Aggiungi info":
        msg = f"Aggiungeremo info." ###
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        return CONV_END
    
    #trigger EXIT:
    elif choice == "Annulla":
        msg = f"Ok. A presto!"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        return CONV_END
    
    #trigger EDIT INFO:
    else:
        keyboard = [[InlineKeyboardButton('Produttore', callback_data='Produttore'),
                InlineKeyboardButton('Nome', callback_data='Nome')],
                [InlineKeyboardButton('Categoria', callback_data='Categoria'),
                InlineKeyboardButton('Quantita', callback_data='Quantita')],
                [InlineKeyboardButton('Esci', callback_data='Esci')]]
        msg = f"Cosa vuoi modificare?"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard))
        return ASK_REWRITE

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
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        return CONV_END
    #else: prepare edit:
    context.user_data['to_edit'] = choice
    query.delete_message()
    query.answer()
    if choice == 'Quantita':
        msg = f"Riscrivi qui il <b>numero</b> corretto di pezzi (nota: solo cifre)."
    else:
        msg = f"Riscrivi qui il testo corretto per il campo <b>{choice}</b>"
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.HTML)
    return PROCESS_PIECES

#CANCEL AND END:
def esci(update: Update, context: CallbackContext) -> int:
    msg = "Uscito. A presto!"
    update.message.reply_text(msg)
    return CONV_END


#GET DB VIEW IN PDF:
def prodotti(update: Update, context: CallbackContext) -> int:
    # try:
    conn, cursor = db_connect()
    Prodotti = db_interactor.get_view_prodotti(conn)
    conn.close()
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


#MAIN:
def main() -> None:
    #create the Updater and pass it the bot's token:
    updater = Updater(TOKEN, use_context=True)
    #get the dispatcher to register handlers:
    dispatcher = updater.dispatcher

    #command handlers:
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    #dispatcher.add_handler(CommandHandler("prodotti", prodotti))

    #conversation handlers:
    #add new product ("/nuovo"):
    conv_handler = ConversationHandler(
        entry_points=[
                CommandHandler('prodotto', prodotto),
                MessageHandler(Filters.regex("^(Prodotto|prodotto)$"), prodotto)],
        states={
            PROCESS_PCODE: [MessageHandler(Filters.photo, process_pcode),
                MessageHandler(Filters.text, process_pcode)],
            INIT_ADD: [CallbackQueryHandler(init_add, pattern='.*')],
            PROCESS_SUPPLIER: [
                CallbackQueryHandler(new_supplier, pattern='^NUOVO$'),
                CallbackQueryHandler(process_supplier, pattern='.*'),
                MessageHandler(Filters.text, process_supplier)],
            PROCESS_PNAME: [
                MessageHandler(Filters.text, process_pname)],
            PROCESS_CATEGORY: [
                CallbackQueryHandler(new_category, pattern='^NUOVO$'),
                CallbackQueryHandler(process_category, pattern='.*'),
                MessageHandler(Filters.text, process_category)],
            PROCESS_PIECES: [MessageHandler(Filters.text, process_pieces)],
            SAVE_EDIT: [CallbackQueryHandler(save_to_db, pattern='.*')],
            ASK_REWRITE: [CallbackQueryHandler(ask_rewrite, pattern='.*')],
        },
        fallbacks=[CommandHandler('error', error)])
    dispatcher.add_handler(conv_handler)

    #message handlers:
    dispatcher.add_handler(MessageHandler(Filters.text, echo))

    #log all errors:
    dispatcher.add_error_handler(error)

    #start polling:
    # updater.start_polling()

    #webhook:
    updater.start_webhook(
        listen="0.0.0.0",
        port=int(PORT),
        url_path=TOKEN,
        webhook_url = HOOK_URL + TOKEN
    )

    #idle:
    updater.idle()


if __name__ == '__main__':
    main()
