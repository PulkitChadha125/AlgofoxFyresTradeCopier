import time
import pandas as pd
from datetime import datetime
import FyresIntegration
from apscheduler.schedulers.background import BackgroundScheduler
import pyotp
from Algofox import *
from flask import Flask, render_template
from urllib.parse import urlparse, parse_qs


app = Flask(__name__)

def get_all_detail_csv():
    symbols = []

    try:
        df = pd.read_csv('TradeSettings.csv')
        symbols = df.to_dict(orient='records')
    except pd.errors.EmptyDataError:
        print("The CSV file is empty or has no data.")
    except FileNotFoundError:
        print("The CSV file was not found.")
    except Exception as e:
        print("An error occurred while reading the CSV file:", str(e))

    return symbols
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

def delete_file_contents(file_path):
    try:
        with open(file_path, 'w') as file:
            file.truncate(0)
        print(f"Successfully deleted all contents of {file_path}.")
    except IOError:
        print(f"Error: Failed to delete contents of {file_path}.")
def get_api_credentials():
    credentials = {}
    delete_file_contents("OrderLogs.txt")
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
    global processed_order_ids

    orders = FyresIntegration.get_orderbook()

    for order in orders['orderBook']:
        order_id = order['id']

        if order_id not in processed_order_ids:
            processed_order_ids.add(order_id)  # Add the order ID to the set
            timestamp = order['orderDateTime']
            transaction_type = order['side']
            tradingsymbol = order['symbol']
            product = order['productType']
            quantity = order['qty']
            price = order['limitPrice']
            status = order['status']
            log_message = f"{timestamp} Order for {transaction_type} {tradingsymbol} {product} for {quantity} Quantity is {status}, Exchange order Id {order_id}\n"

            # Save the log message to a file named after the symbol
            filename = f"OrderLogs.txt"
            with open(filename, 'a') as file:
                file.write(log_message)

    process_orders(orders)


order_ids = set()
def process_orders(orders):
    global transaction,username,password,role
    old_net_pos = None
    symbols = read_symbols_from_csv()  # Read symbols from TradeSettings.csv
    order_executed = False
    for order in orders['orderBook']:
        order_id = order['id']
        tradingsymbol = order['symbol']
        timestamp = datetime.strptime(order['orderDateTime'], '%d-%b-%Y %H:%M:%S')
        transaction_type = order['side']
        current_time = datetime.now()
        status = order['status']
        price = order['limitPrice']
        quantity = order['qty']


        if transaction_type==1:
            transaction="BUY"
        if transaction_type==-1:
            transaction = "SELL"

        # print("beforestatus: ", status)
        if status==2:
            status="COMPLETE"
        else:
            # fix this before deleivery set status to unknown
            status="NOTKNOWN"

        if (
                status == 'COMPLETE'and
                timestamp.hour == current_time.hour and
                timestamp.minute == current_time.minute
                and tradingsymbol in symbols
        ):
            if order_id not in order_ids:
                order_ids.add(order_id)  # Add the order ID to the set
                print(f"{timestamp} Order executed @ {tradingsymbol}, Ordertype= {transaction}, Quantity= {quantity}, @ price {price} , order id : {order_id}")
                ssymbols = get_all_detail_csv()
                netpositionresponce = FyresIntegration.get_position()
                # print("netpositionresponce: ",netpositionresponce)
                for symbol in ssymbols:

                    if symbol['Symbol'] == tradingsymbol:
                        ExchangeSymbol = symbol['ExchangeSymbol']
                        StrategyTag = symbol['StrategyTag']
                        Segment = symbol['Segment']
                        product = symbol['ProductType']
                        strike = symbol['STRIKE']
                        contract = symbol['CONTRAC TYPE']
                        expiery = symbol['EXPIERY']

                        for item in netpositionresponce['netPositions']:
                            if item['symbol'] == tradingsymbol:
                                symbol_net_pos = item['netQty']
                                if transaction == "BUY":
                                    old_net_pos = int(symbol_net_pos) - int(quantity)
                                elif transaction == "SELL":
                                    old_net_pos = int(symbol_net_pos) + int(quantity)

                        if old_net_pos is not None:

                            if not order_executed and transaction == "BUY" and int(old_net_pos) >= 0:
                                print(f"Sending Buy Order @ {tradingsymbol}")
                                order_executed = True
                                if Segment == "EQ":
                                    Buy_order_algofox(symbol=ExchangeSymbol, quantity=quantity, instrumentType=Segment,
                                                      direction="BUY", price=price, product=product,
                                                      order_typ="MARKET", strategy=StrategyTag,username=username,password=password,role=role)
                                    break

                                if Segment == "OPTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Buy_order_algofox(symbol=sname, quantity=quantity, instrumentType=Segment,
                                                      direction="BUY", price=price, product=product,
                                                      order_typ="MARKET", strategy=StrategyTag,username=username,password=password,role=role)
                                    break

                                if Segment == "FUTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Buy_order_algofox(symbol=sname, quantity=quantity, instrumentType=Segment,
                                                      direction="BUY", price=price, product=product,
                                                      order_typ="MARKET", strategy=StrategyTag,username=username,password=password,role=role)
                                    break
                                if Segment == "FUTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Buy_order_algofox(symbol=sname, quantity=quantity, instrumentType=Segment,
                                                      direction="BUY", price=price, product=product,
                                                      order_typ="MARKET", strategy=StrategyTag,username=username,password=password,role=role)
                                    break

                                if Segment == "OPTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Buy_order_algofox(symbol=sname, quantity=quantity, instrumentType=Segment,
                                                      direction="BUY", price=price, product=product,
                                                      order_typ="MARKET", strategy=StrategyTag,username=username,password=password,role=role)
                                    break

                            if not order_executed and transaction == "SELL" and int(old_net_pos) <= 0:
                                print(f"Sending Short Order @ {tradingsymbol}")
                                order_executed = True
                                if Segment == "EQ":
                                    Short_order_algofox(symbol=ExchangeSymbol, quantity=quantity,
                                                            instrumentType=Segment, direction="SHORT", price=price,
                                                            product=product,
                                                            order_typ="MARKET", strategy=StrategyTag, username=username,
                                                            password=password, role=role)
                                    break
                                if Segment == "OPTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Short_order_algofox(symbol=sname, quantity=quantity,
                                                            instrumentType=Segment, direction="SHORT", price=price,
                                                            product=product,
                                                            order_typ="MARKET", strategy=StrategyTag, username=username,
                                                            password=password, role=role)
                                    break

                                if Segment == "FUTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Short_order_algofox(symbol=sname, quantity=quantity,
                                                            instrumentType=Segment, direction="SHORT", price=price,
                                                            product=product,
                                                            order_typ="MARKET", strategy=StrategyTag, username=username,
                                                            password=password, role=role)
                                    break

                                if Segment == "FUTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Short_order_algofox(symbol=sname, quantity=quantity,
                                                            instrumentType=Segment, direction="SHORT", price=price,
                                                            product=product,
                                                            order_typ="MARKET", strategy=StrategyTag, username=username,
                                                            password=password, role=role)
                                    break

                                if Segment == "OPTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Short_order_algofox(symbol=sname, quantity=quantity,
                                                            instrumentType=Segment, direction="SHORT", price=price,
                                                            product=product,
                                                            order_typ="MARKET", strategy=StrategyTag, username=username,
                                                            password=password, role=role)
                                    break

                            if not order_executed and transaction == "BUY" and int(old_net_pos) < 0:
                                print(f"Sending Cover Order @ {tradingsymbol}")
                                order_executed = True
                                if Segment == "EQ":
                                    Cover_order_algofox(symbol=ExchangeSymbol, quantity=quantity,
                                                                instrumentType=Segment, direction="COVER", price=price,
                                                                product=product,
                                                                order_typ="MARKET", strategy=StrategyTag, username=username,
                                                                password=password, role=role)
                                    break

                                if Segment == "OPTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Cover_order_algofox(symbol=sname, quantity=quantity,
                                                                instrumentType=Segment, direction="COVER", price=price,
                                                                product=product,
                                                                order_typ="MARKET", strategy=StrategyTag, username=username,
                                                                password=password, role=role)
                                    break

                                if Segment == "FUTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Cover_order_algofox(symbol=sname, quantity=quantity,
                                                                instrumentType=Segment, direction="COVER", price=price,
                                                                product=product,
                                                                order_typ="MARKET", strategy=StrategyTag, username=username,
                                                                password=password, role=role)
                                    break

                                if Segment == "FUTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Cover_order_algofox(symbol=sname, quantity=quantity,
                                                                instrumentType=Segment, direction="COVER", price=price,
                                                                product=product,
                                                                order_typ="MARKET", strategy=StrategyTag, username=username,
                                                                password=password, role=role)
                                    break

                                if Segment == "OPTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Cover_order_algofox(symbol=sname, quantity=quantity,
                                                                instrumentType=Segment, direction="COVER", price=price,
                                                                product=product,
                                                                order_typ="MARKET", strategy=StrategyTag, username=username,
                                                                password=password, role=role)
                                    break
                            if not order_executed and transaction == "SELL" and int(old_net_pos) > 0:
                                print(f"Sending Sell Order @ {tradingsymbol}")
                                order_executed = True
                                if Segment == "EQ":
                                    Sell_order_algofox(symbol=ExchangeSymbol, quantity=quantity,
                                                               instrumentType=Segment, direction="SELL", price=price,
                                                               product=product,
                                                               order_typ="MARKET", strategy=StrategyTag, username=username,
                                                               password=password, role=role)
                                    break

                                if Segment == "OPTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Sell_order_algofox(symbol=sname, quantity=quantity,
                                                               instrumentType=Segment, direction="SELL", price=price,
                                                               product=product,
                                                               order_typ="MARKET", strategy=StrategyTag, username=username,
                                                               password=password, role=role)
                                    break

                                if Segment == "FUTIDX":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Sell_order_algofox(symbol=sname, quantity=quantity,
                                                               instrumentType=Segment, direction="SELL", price=price,
                                                               product=product,
                                                               order_typ="MARKET", strategy=StrategyTag, username=username,
                                                               password=password, role=role)
                                    break

                                if Segment == "FUTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}"
                                    Sell_order_algofox(symbol=sname, quantity=quantity,
                                                               instrumentType=Segment, direction="SELL", price=price,
                                                               product=product,
                                                               order_typ="MARKET", strategy=StrategyTag, username=username,
                                                               password=password, role=role)
                                    break

                                if Segment == "OPTSTK":
                                    sname = f"{ExchangeSymbol}|{str(expiery)}|{str(int(strike))}|{contract}"
                                    Sell_order_algofox(symbol=sname, quantity=quantity,
                                                               instrumentType=Segment, direction="SELL", price=price,
                                                               product=product,
                                                               order_typ="MARKET", strategy=StrategyTag, username=username,
                                                               password=password, role=role)
                                    break




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