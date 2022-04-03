import os, sqlite3, logging, configparser, time, json, pytz
from datetime import datetime, date
import pandas as pd

#GLOBAL IMPORTS, PARAMETERS & INSTANTIATIONS:

#GLOBALS:
DB_FILE = "database/erboristeria.db"
THRESHOLD_TO_ORD = 5
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

#TELEGRAM BOT:
#Config:
config = configparser.ConfigParser()
print(os.getcwd())
config.read(os.getcwd()+"/t_credentials.ini")
t_conf = config['TELEGRAM']
TOKEN = str(t_conf.get('token'))

#LOGS:
#Set DB logger:
log=logging.getLogger('db_events')
hdl=logging.FileHandler('./logs/db_events.log',mode='a')
hdl.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
log.setLevel(logging.INFO)
log.addHandler(hdl)

#Set Telegram bot logger:
tlog=logging.getLogger('tbot_events')
thdl=logging.FileHandler('./logs/tbot_events.log',mode='a')
thdl.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
tlog.setLevel(logging.INFO)
tlog.addHandler(thdl)
