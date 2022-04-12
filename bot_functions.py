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
    headers = {'Codice': 'codiceprod', 'Produttore': 'produttore', 'Nome': 'nome', 'Categoria': 'categoria', 'Quantita': 'quantita', 'Prezzo Pubblico €': 'prezzo', 'Sconto Medio %': 'scontomedio', 'IVA %': 'aliquota', 'Costo Acquisto €': 'costoacquisto', 'Costo Giacenze €': 'costototale', 'Valore Giacenze €': 'valoretotale', 'Disp Medico': 'dispmedico', 'Eta Minima': 'etaminima', ' Bio ': 'bio', ' Vegano ': 'vegano', 'Senza Glutine': 'senzaglutine', 'Senza Lattosio': 'senzalattosio', 'Senza Zucchero': 'senzazucchero'}
    #export table to pdf:
    try:
        Prodotti = db_interactor.get_view_prodotti(schema)
        if Prodotti.empty == False:
            #1) format adjustments:
            Vista = pd.DataFrame(columns=headers.keys())
            for col in Vista.columns:
                if col == 'Codice':
                    Vista[col] = [str(p_code) for p_code in Prodotti[headers[col]]]
                elif col in ['Sconto Medio %', 'IVA %']:
                    Vista[col] = Prodotti[headers[col]]/100
                elif col == 'Costo Acquisto €':
                    #calculate purchase cost & inventory value from available data:
                    temp_cost = []
                    temp_inv = []
                    for ind in Prodotti.index:
                        #purchase cost:
                        discount = Prodotti['prezzo'].iloc[ind] * (Prodotti['scontomedio'].iloc[ind]/100)
                        cost = Prodotti['prezzo'].iloc[ind] - discount
                        cost = cost + (cost * (Prodotti['aliquota'].iloc[ind]/100))
                        temp_cost.append(cost)
                        #inventory value:
                        inventory = cost * Prodotti['quantita'].iloc[ind]
                        temp_inv.append(inventory)
                    Vista[col] = temp_cost
                elif col == 'Costo Giacenze €':
                    #populate column with the inventory value (at cost) already calculated:
                    Vista[col] = temp_inv
                else:
                    Vista[col] = Prodotti[headers[col]]
            
            Vista.replace(to_replace=False, value='No', inplace=True)
            Vista.replace(to_replace=True, value='Sì', inplace=True)
            #add grand totals row:
            Vista = Vista.append({col:'-' for col in Vista.columns}, ignore_index=True)
            Vista['Codice'].iloc[-1] = 'TOTALE'
            Vista['Quantita'].iloc[-1] = Prodotti['quantita'].sum()
            Vista['Costo Giacenze €'].iloc[-1] = sum(temp_inv)
            Vista['Valore Giacenze €'].iloc[-1] = Prodotti['valoretotale'].sum()
            Vista.reset_index(drop=True, inplace=True)

            #2) export:
            #load Pandas Excel exporter:
            writer = pd.ExcelWriter(filename)
            Vista.to_excel(writer, sheet_name=schema, index=False, na_rep='')
            workbook  = writer.book
            fmt_price = workbook.add_format({'num_format': '#,##0.00'})
            fmt_pct = workbook.add_format({'num_format': '0%'})
            #auto-adjust columns' width:
            for column in Vista:
                column_width = max(Vista[column].astype(str).map(len).max(), len(column))
                col_idx = Vista.columns.get_loc(column)
                if column in ['Prezzo Pubblico €', 'Costo Acquisto €', 'Costo Giacenze €', 'Valore Giacenze €']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_price)
                elif column in ['Sconto Medio %', 'IVA %']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_pct)
                else:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width)
            writer.save()
        return 0
    except Exception:
        tlog.exception(f"Export error for xsls Prodotti. {Exception}")
        return -1

#views by produttore & categoria:
def create_view_recap(schema, filename):
    headers = {'Produttore': 'produttore', 'Categoria': 'categoria', 'Sconto Medio %': 'scontomedio', 'IVA %': 'aliquota', 'Quantita': 'quantita', 'Costo Giacenze €': 'costototale', 'Valore Giacenze €': 'valoretotale'}
    #export table to pdf:
    try:
        Recap = db_interactor.get_view_recap(schema)
        if Recap.empty == False:
            #1) format adjustments:
            Vista = pd.DataFrame(columns=headers.keys())
            for col in Vista.columns:
                if col in ['Sconto Medio %', 'IVA %']:
                    Vista[col] = Recap[headers[col]]/100
                elif col == 'Costo Giacenze €':
                    temp_inv = []
                    for ind in Recap.index:
                        discount = Recap['valoretotale'].iloc[ind] * (Recap['scontomedio'].iloc[ind]/100)
                        cost = Recap['valoretotale'].iloc[ind] - discount
                        cost = cost + (cost * (Recap['aliquota'].iloc[ind]/100))
                        temp_inv.append(cost)
                    Vista[col] = temp_inv
                else:
                    Vista[col] = Recap[headers[col]]
            #add grand totals row:
            Vista = Vista.append({col:'-' for col in Vista.columns}, ignore_index=True)
            Vista['Produttore'].iloc[-1] = 'TOTALE'
            Vista['Quantita'].iloc[-1] = Recap['quantita'].sum()
            Vista['Costo Giacenze €'].iloc[-1] = sum(temp_inv)
            Vista['Valore Giacenze €'].iloc[-1] = Recap['valoretotale'].sum()
            Vista.reset_index(drop=True, inplace=True)

            #2) export:
            #load Pandas Excel exporter:
            writer = pd.ExcelWriter(filename)
            Vista.to_excel(writer, sheet_name=schema, index=False, na_rep='')
            workbook  = writer.book
            fmt_price = workbook.add_format({'num_format': '#,##0.00'})
            fmt_pct = workbook.add_format({'num_format': '0%'})
            #auto-adjust columns' width:
            for column in Vista:
                column_width = max(Vista[column].astype(str).map(len).max(), len(column))
                col_idx = Vista.columns.get_loc(column)
                if column in ['Costo Giacenze €', 'Valore Giacenze €']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_price)
                elif column in ['Sconto Medio %', 'IVA %']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_pct)
                else:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width)
            writer.save()
        return 0
    except Exception:
        tlog.exception(f"Export error for Recap xsls of schema {schema}. {Exception}")
        return -1
