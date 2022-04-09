from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from pyzbar import pyzbar
from PIL import Image
from database.db_tools import db_connect, db_disconnect
import database.db_interactor as db_interactor
from globals import *

#scan image for barcodes and extract pcode:
def extract_barcode(image):
    #get photo sent by user:
    image_name = './data_cache/barcode.jpg'
    image.download(image_name)
    #read barcode in photo:
    decoded = pyzbar.decode(Image.open(image_name))
    p_code = decoded[0].data
    p_code = p_code.decode("utf-8")
    os.remove(image_name)
    p_code = int(p_code)
    return p_code

#inline picker keyboard:
def inline_picker(schema, column_name):
    buf = []
    keyboard = []
    cnt = 0
    items = db_interactor.get_column(schema, column_name)
    #build inline keyboard:
    if items != []:
        for item in items:
            cnt = cnt + 1
            buf.append(InlineKeyboardButton(str(item), callback_data=str(item)))
            #end row of buttons every 2 buttons:
            if (cnt % 2 == 0) or (cnt == len(items)):
                keyboard.append(buf)
                buf = []
    else:
        tlog.error("No items found.")
    return keyboard
