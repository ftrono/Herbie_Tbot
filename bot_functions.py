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


def create_view_prodotti(schema, filename):
    headers = {'Codice': 'codiceprod', 'Produttore': 'produttore', 'Nome': 'nome', 'Categoria': 'categoria', 'Quantita': 'quantita', 'Prezzo Pubblico €': 'prezzo',	'Sconto Medio %': 'scontomedio', 'IVA %': 'aliquota', 'Costo Acquisto €': 'costoacquisto', 'Disp Medico': 'dispmedico', 'Eta Minima': 'etaminima', ' Bio ': 'bio', ' Vegano ': 'vegano', 'Senza Glutine': 'senzaglutine', 'Senza Lattosio': 'senzalattosio', 'Senza Zucchero': 'senzazucchero'}
    #export table to pdf:
    try:
        Prodotti = db_interactor.get_view_prodotti(schema)
        if Prodotti.empty == False:
            #1) format adjustments:
            Vista = pd.DataFrame(columns=headers.keys())
            for col in Vista.columns:
                if col == 'Codice':
                    Vista[col] = [str(p_code) for p_code in Prodotti[headers[col]]]
                elif col == 'Prezzo Pubblico €':
                    Vista[col] = [f"{price:.2f} €" for price in Prodotti[headers[col]]]
                elif col == 'Sconto Medio %':
                    Vista[col] = [f"{disc} %" for disc in Prodotti[headers[col]]]
                elif col == 'IVA %':
                    Vista[col] = [f"{vat} %" for vat in Prodotti[headers[col]]]
                elif col == 'Costo Acquisto €':
                    temp = []
                    for ind in Prodotti.index:
                        discount = Prodotti['prezzo'].iloc[ind] * (Prodotti['scontomedio'].iloc[ind]/100)
                        cost = Prodotti['prezzo'].iloc[ind] - discount
                        cost = cost + (cost * (Prodotti['aliquota'].iloc[ind]/100))
                        temp.append(cost)
                    Vista[col] = [f"{cst:.2f} €" for cst in temp]
                else:
                    Vista[col] = Prodotti[headers[col]]
            
            Vista.replace(to_replace=False, value='No', inplace=True)
            Vista.replace(to_replace=True, value='Sì', inplace=True)
            Vista = Vista.sort_values(by="Produttore")
            Vista.reset_index(drop=True, inplace=True)

            #2) export:
            #load Pandas Excel exporter:
            writer = pd.ExcelWriter(filename)
            sheet = 'prodotti'
            Vista.to_excel(writer, sheet_name=sheet, index=False, na_rep='')
            #auto-adjust columns' width:
            for column in Vista:
                column_width = max(Vista[column].astype(str).map(len).max(), len(column))
                col_idx = Vista.columns.get_loc(column)
                writer.sheets[sheet].set_column(col_idx, col_idx, column_width)
            writer.save()
        return 0
    except Exception:
        tlog.exception(f"Export error for xsls Prodotti. {Exception}")
        return -1
