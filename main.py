import time
import pandas as pd
from datetime import datetime
import FyresIntegration
from apscheduler.schedulers.background import BackgroundScheduler
import pyotp
from Algofox import *
from flask import Flask, render_template
from urllib.parse import urlparse, parse_qs
# Create the Flask application
app = Flask(__name__)


def read_symbols_from_csv():
    symbols = []

    try:
        df = pd.read_csv('TradeSettings.csv', usecols=['Symbol'])
        symbols = df['Symbol'].tolist()
    except pd.errors.EmptyDataError:
        print("The CSV file is empty or has no data.")
    except FileNotFoundError:
        print("The CSV file was not found.")
    except Exception as e:
        print("An error occurred while reading the CSV file:", str(e))

    return symbols


def get_api_credentials():
    credentials = {}

    try:
        df = pd.read_csv('Credentials.csv')
        for index, row in df.iterrows():
            title = row['Title']
            value = row['Value']
            credentials[title] = value
    except pd.errors.EmptyDataError:
        print("The CSV file is empty or has no data.")
    except FileNotFoundError:
        print("The CSV file was not found.")
    except Exception as e:
        print("An error occurred while reading the CSV file:", str(e))

    return credentials


credentials_dict = get_api_credentials()
redirect_uri=credentials_dict.get('redirect_uri')
client_id=credentials_dict.get('client_id')
secret_key=credentials_dict.get('secret_key')
grant_type=credentials_dict.get('grant_type')
response_type=credentials_dict.get('response_type')
state=credentials_dict.get('state')
TOTP_KEY=credentials_dict.get('totpkey')
FY_ID=credentials_dict.get('FY_ID')
PIN=credentials_dict.get('PIN')
url = credentials_dict.get('algofoxurl')
username= credentials_dict.get('algofoxusername')
password=credentials_dict.get('algofoxpassword')
role= credentials_dict.get('ROLE')
createurl(url)
processed_order_ids = set()
loginresult=login_algpfox(username=username, password=password, role=role)

if loginresult!=200:
    print("Algofoz credential wrong, shutdown down Trde Copier, please provide correct details and run again otherwise program will not work correctly ...")
    time.sleep(10000)


# FyresIntegration.apiactivation(client_id=client_id,redirect_uri=redirect_uri,response_type=response_type,state=state
#                        ,secret_key=secret_key,grant_type=grant_type)

def check_orders():
    global  processed_order_ids
    orders = FyresIntegration.get_orderbook()
    print("orders: ",orders)
    # with open('OrderLogs.txt', 'a') as file:
    #     for order in orders:
    #         order_id = order['order_id']
    #         if order_id not in processed_order_ids:
    #             processed_order_ids.add(order_id)  # Add the order ID to the set
    #             timestamp = order['order_timestamp']
    #             transaction_type = order['transaction_type']
    #             tradingsymbol = order['tradingsymbol']
    #             product = order['product']
    #             quantity = order['quantity']
    #             status = order['status']
    #             log_message = f"{timestamp} Order for {transaction_type} {tradingsymbol} {product} for {quantity} Quantity is {status}, Exchange order Id {order_id}\n"
    #             file.write(log_message)

    process_orders(orders)

def process_orders(orders):
    symbols = read_symbols_from_csv()  # Read symbols from TradeSettings.csv
    order_executed = False
    # for order in orders:
    #     order_id = order['order_id']
    #     tradingsymbol = order['tradingsymbol']
    #     timestamp = order['order_timestamp']
    #     current_time = datetime.now()
    #     status = order['status']


# print("OrderBook: ",FyresIntegration.get_orderbook())
# print("TradeBook: ",FyresIntegration.get_tradebook())
# print("PositionBook: ",FyresIntegration.get_position())

@app.route('/')
def index():
    with open('OrderLogs.txt', 'r') as file:
        order_logs = file.read()
    return render_template('index.html', order_logs=order_logs)


if __name__ == '__main__':
    FyresIntegration.automated_login(client_id=client_id, redirect_uri=redirect_uri, secret_key=secret_key, FY_ID=FY_ID,
                                     PIN=PIN, TOTP_KEY=TOTP_KEY)

    # Create a scheduler and add the job
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_orders, 'interval', seconds=1)
    scheduler.start()

    # Start the Flask app
    app.run()