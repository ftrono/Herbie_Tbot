import os, psycopg2, logging, configparser, time, json, pytz
from datetime import datetime, date
import pandas as pd

#GLOBAL IMPORTS, PARAMETERS & INSTANTIATIONS:
#Connect to:
SCHEMA = 'Test'

#CONFIG:
PORT = int(os.environ.get('PORT', '8443'))
try:
    #On local -> use config file:
    ENV = 'local'
    config = configparser.ConfigParser()
    print(os.getcwd())
    config.read(os.getcwd()+"/t_credentials.ini")
    t_conf = config['TELEGRAM']
    DATABASE_URL = t_conf.get('database_url')
    HOOK_URL = t_conf.get('hook_url')
    TOKEN = t_conf.get('token')
except:
    #On Heroku -> use global config vars:
    ENV = 'heroku'
    DATABASE_URL = os.environ['DATABASE_URL']
    HOOK_URL = os.environ['HOOK_URL']
    TOKEN = os.environ['TOKEN']


#LOGS:
#Set DB logger:
dlog=logging.getLogger('db_events')
hdl=logging.FileHandler('./logs/db_events.log',mode='a')
hdl.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
dlog.setLevel(logging.INFO)
dlog.addHandler(hdl)

#Set Telegram bot logger:
tlog=logging.getLogger('tbot_events')
thdl=logging.FileHandler('./logs/tbot_events.log',mode='a')
thdl.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
tlog.setLevel(logging.INFO)
tlog.addHandler(thdl)
