from telegram import InlineKeyboardButton
from pyzbar import pyzbar
from PIL import Image
import database.db_interactor as db_interactor
import database.db_export as db_export
from globals import *

#BOT_FUNCTIONS:
#common data preparers for bot:
# - code_to_int()
# - code39toCode32()
# - extract_barcode()
# - inline_picker()
# - create_view_prodotti()
# - create_view_listaordine()
# - create_view_storicoordini()


#extract int code & cut part from full scan:
def code_to_int(p_code):
    #try conversion to int (there might be some initial letters, to be cut):
    rem = ''
    try:
        try:
            p_code = int(p_code)
        except:
            rem = p_code[0]
            p_code = int(p_code[1:])
    except:
        rem = p_code[0:2]
        p_code = int(p_code[2:])
    return p_code, rem


#convert code39 to Italian Pharmacode (code32):
def code39toCode32(val):
    code32set = '0123456789BCDFGHJKLMNPQRSTUVWXYZ'
    res = 0
    for i in range(len(val)):
        res = res * 32 + code32set.index(val[i])
    code32 = str(res)
    if len(code32) < 9:
        code32 = '000000000' + code32
        code32 = code32[:-9]
    return code32


#scan image for barcodes and extract pcode:
def extract_barcode(image):
    #get photo sent by user:
    image_name = './data_cache/barcode.jpg'
    image.download(image_name)
    #read barcode in photo:
    decoded = pyzbar.decode(Image.open(image_name))
    tlog.info(f"extract_barcode(): {decoded}")
    for barcode in decoded:
        try:
            p_code = barcode.data
            p_code = p_code.decode("utf-8")
            break
        except:
            pass
    #check if needed conversion of Italian Pharmacode:
    tlog.info(f"{p_code}")
    try:
        p_code = int(p_code)
    except:
        p_code = code39toCode32(p_code)
        p_code = int(p_code)
    os.remove(image_name)
    return p_code


#inline picker keyboard:
def inline_picker(schema, column_name):
    buf = []
    keyboard = []
    cnt = 0
    items = db_interactor.get_column(schema, column_name)
    #build inline keyboard:
    if items != []:
        items.sort()
        for item in items:
            cnt = cnt + 1
            buf.append(InlineKeyboardButton(str(item), callback_data=str(item)))
            #end row of buttons every 2 buttons:
            if (cnt % 2 == 0) or (cnt == len(items)):
                keyboard.append(buf)
                buf = []
    else:
        tlog.error("inline_picker(): No items found.")
    return keyboard


#EXPORT:
#view Prodotti:
def create_view_prodotti(schema, filename, supplier=None):
    headers = {'Codice': 'codiceprod', 'Produttore': 'produttore', 'Nome': 'nome', 'Categoria': 'categoria', 'IVA %': 'aliquota', 'Prezzo Pubblico €': 'prezzo', 'Costo Acquisto €': 'costo', 'Quantita': 'quantita', 'Valore Giacenze €': 'valoretotale', 'Costo Giacenze €': 'costototale', 'Costo Giacenze +IVA €': 'costoplus', 'Disp Medico': 'dispmedico', ' Vegano ': 'vegano', 'Senza Lattosio': 'senzalattosio', 'Senza Glutine': 'senzaglutine', 'Senza Zucchero': 'senzazucchero'}
    #export table to pdf:
    try:
        Prodotti = db_export.get_view_prodotti(schema, supplier)
        if Prodotti.empty == False:
            #1) format adjustments:
            Vista = pd.DataFrame(columns=headers.keys())
            for col in Vista.columns:
                if col == 'IVA %':
                    Vista[col] = Prodotti[headers[col]]/100
                elif col == 'Costo Giacenze +IVA €':
                    #calculate purchase cost +VAT from available data:
                    temp_costplus = []
                    for ind in Prodotti.index:
                        #purchase cost +VAT:
                        costotot = Prodotti['costototale'].iloc[ind]
                        costplus = costotot + (costotot * (Prodotti['aliquota'].iloc[ind]/100))
                        temp_costplus.append(costplus)
                    Vista[col] = temp_costplus
                else:
                    Vista[col] = Prodotti[headers[col]]
            Vista.replace(to_replace=False, value='No', inplace=True)
            Vista.replace(to_replace=True, value='Sì', inplace=True)
            #add grand totals row:
            Vista = Vista.append({col:'-' for col in Vista.columns}, ignore_index=True)
            Vista['Codice'].iloc[-1] = 'TOTALE'
            Vista['Quantita'].iloc[-1] = Prodotti['quantita'].sum()
            Vista['Costo Giacenze €'].iloc[-1] = Prodotti['costototale'].sum()
            Vista['Valore Giacenze €'].iloc[-1] = Prodotti['valoretotale'].sum()
            Vista['Costo Giacenze +IVA €'].iloc[-1] = sum(temp_costplus)
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
                if column in ['Prezzo Pubblico €', 'Costo Acquisto €', 'Costo Giacenze €', 'Valore Giacenze €', 'Costo Giacenze +IVA €']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_price)
                elif column == 'IVA %':
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_pct)
                else:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width)
            writer.save()
        return 0
    except Exception:
        tlog.exception(f"create_view_prodotti(): Export error for xslx Prodotti for schema {schema}. {Exception}")
        return -1


#view ListaOrdine by codiceord:
def create_view_listaordine(schema, codiceord):
    headers = {'Codice Prodotto': 'codiceprod', 'Produttore': 'produttore', 'Nome': 'nome', 'Categoria': 'categoria', 'IVA %': 'aliquota', 'Prezzo Pubblico €': 'prezzo', 'Costo Acquisto €': 'costo', 'Quantita Ordine': 'quantita', 'Valore Totale €': 'valoretotale', 'Costo Totale €': 'costototale', 'Costo Totale +IVA €': 'costoplus'}
    temp_totcost = []
    temp_totprice = []
    #export table to pdf:
    try:
        ListaOrdine = db_export.get_view_listaordine(schema, codiceord)
        if ListaOrdine.empty == False:
            #1) format adjustments:
            Vista = pd.DataFrame(columns=headers.keys())
            for col in Vista.columns:
                if col == 'IVA %':
                    Vista[col] = ListaOrdine[headers[col]]/100
                elif col == 'Costo Totale €':
                    #total cost of ordered:
                    for ind in ListaOrdine.index:
                        totcost = ListaOrdine['costo'].iloc[ind] * ListaOrdine['quantita'].iloc[ind]
                        temp_totcost.append(totcost)
                    Vista[col] = temp_totcost
                elif col == 'Valore Totale €':
                    #total price of ordered:
                    for ind in ListaOrdine.index:
                        totprice = ListaOrdine['prezzo'].iloc[ind] * ListaOrdine['quantita'].iloc[ind]
                        temp_totprice.append(totprice)
                    Vista[col] = temp_totprice
                elif col == 'Costo Totale +IVA €':
                    #calculate purchase cost +VAT from available data:
                    temp_costplus = []
                    for ind in ListaOrdine.index:
                        #purchase cost +VAT:
                        costotot = ListaOrdine['costototale'].iloc[ind]
                        costplus = costotot + (costotot * (ListaOrdine['aliquota'].iloc[ind]/100))
                        temp_costplus.append(costplus)
                    Vista[col] = temp_costplus
                else:
                    Vista[col] = ListaOrdine[headers[col]]
            
            #add grand totals row:
            Vista = Vista.append({col:'-' for col in Vista.columns}, ignore_index=True)
            Vista['Codice Prodotto'].iloc[-1] = 'TOTALE'
            Vista['Quantita Ordine'].iloc[-1] = ListaOrdine['quantita'].sum()
            Vista['Costo Totale €'].iloc[-1] = sum(temp_totcost)
            Vista['Valore Totale €'].iloc[-1] = sum(temp_totprice)
            Vista['Costo Totale +IVA €'].iloc[-1] = sum(temp_costplus)
            Vista.reset_index(drop=True, inplace=True)
            supplier = Vista['Produttore'].iloc[0]
            codedate = str(codiceord) if len(str(codiceord)) < 8 else str(codiceord)[:8]

            #2) export:
            #load Pandas Excel exporter:
            filename = f'./data_cache/{schema}.lista_{supplier}_{codedate}.xlsx'
            writer = pd.ExcelWriter(filename)
            Vista.to_excel(writer, sheet_name=schema, index=False, na_rep='')
            workbook  = writer.book
            fmt_price = workbook.add_format({'num_format': '#,##0.00'})
            fmt_pct = workbook.add_format({'num_format': '0%'})
            #auto-adjust columns' width:
            for column in Vista:
                column_width = max(Vista[column].astype(str).map(len).max(), len(column))
                col_idx = Vista.columns.get_loc(column)
                if column in ['Prezzo Pubblico €', 'Costo Acquisto €', 'Costo Totale €', 'Valore Totale €', 'Costo Totale +IVA €']:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_price)
                elif column == 'IVA %':
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width, cell_format=fmt_pct)
                else:
                    writer.sheets[schema].set_column(first_col=col_idx, last_col=col_idx, width=column_width)
            writer.save()
        return 0, filename
    except Exception:
        tlog.exception(f"create_view_listaordine(): Export error for xslx ListaOrdine {codiceord} for schema {schema}. {Exception}")
        return -1, ""
