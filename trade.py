import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import mexc_spot_v3
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, filters

hosts = "https://api.mexc.com"
key = os.environ.get('KEY')
secret = os.environ.get('SECRET')
token = os.environ.get('TOKEN')

market = mexc_spot_v3.mexc_market(mexc_hosts=hosts)
trade = mexc_spot_v3.mexc_trade(mexc_hosts=hosts, mexc_key=key, mexc_secret=secret)
account = mexc_spot_v3.mexc_account(mexc_hosts=hosts, mexc_key=key, mexc_secret=secret)
capital = mexc_spot_v3.mexc_capital(mexc_hosts=hosts, mexc_key=key, mexc_secret=secret)

command_executor = 'http://185.215.187.158:4444'
options = webdriver.ChromeOptions()
# options.add_experimental_option("detach", True)
options.add_argument('--ignore-ssl-errors=yes')
options.add_argument('--ignore-certificate-errors')
options.add_argument("--webdriver.timeout.session=60000")
driver = webdriver.Remote(
    command_executor=command_executor,
    options=options
)
driver.maximize_window()


def mexc_login(ticker):
    url = "https://www.mexc.com/login"
    driver.get(url)
    selector = "#login > div.LoginForm_otherLogin__NA0qO > div.LoginForm_otherLoginHandle__2rQVc > div:nth-child(4) > div"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()
    time.sleep(2)
    original_window = driver.current_window_handle
    for window_handle in driver.window_handles:
        if window_handle != original_window:
            driver.switch_to.window(window_handle)
            break
    time.sleep(2)
    selector = "login-phone"
    driver.find_element(by=By.ID, value=selector).send_keys("53145075")
    time.sleep(2)
    selector = "#send-form > div.login_button_wrap > button:nth-child(2)"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()
    input("Accept session on telegram and press enter to countinue.")
    selector = "body > main > section > div.login_button_wrap > button:nth-child(2)"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()
    driver.switch_to.window(original_window)
    time.sleep(5)
    selector = "#__next > div.login_loginBox__kVwMC > div.login_wrapper__aEuqp > div > div > div > div.AuthCode_codeInput__7WYrT.react-code-input"
    elements = driver.find_element(by=By.CSS_SELECTOR, value=selector)
    elements = elements.find_elements(By.TAG_NAME, "input")
    ids = [element.get_attribute('id') for element in elements]
    passwd = input("Enter google authenticator password:")
    values = list(passwd)
    for c, i in enumerate(ids):
        driver.find_element(by=By.ID, value=i).clear()
        driver.find_element(by=By.ID, value=i).send_keys(values[c])
        time.sleep(0.2)
    time.sleep(10)
    url = f"https://www.mexc.com/exchange/{ticker.replace('USDT','_USDT')}"
    driver.get(url)
    selector = "#__next > section > div.exchange_wrapper__u_qZX.exchange_layoutMX__0zSjA > div.exchange_actionWrapper__7IkvE > div.actions_middleWrapper__cjxMT > div.actions_orderTypeMode__QDSff > div.horizon-scroll.actions_modes__l3w3h.actions_line__b_I6K > div:nth-child(2)"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()

    return True


def get_new_tickers():
    tickers = market.get_24hr_ticker()
    return [ticker['symbol'] for ticker in tickers if ticker['lastPrice'] == '0']


def check_ticker_api(ticker):
    default_tickers = market.get_defaultSymbols()['data']
    return ticker in default_tickers


def tickers_launck_time(ticker):
    url = f"https://www.mexc.com/exchange/{ticker.replace('USDT','_USDT')}"
    driver.get(url)
    element = driver.find_element(by=By.CLASS_NAME, value="countDown_deadline__Inua0").text
    return datetime.strptime(element, '%Y-%m-%d %H:%M:%S')


def ticker_api_buy(ticker):
    params = {
            "symbol": ticker,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": 10
        }
    response = trade.post_order(params)
    values = {
        'orderId':response['orderId'],
        'buy_order_status':response['status'],
        'buy_qty':response['origQty']
    }
    return values


def ticker_api_sell(ticker, quantity):
    params = {
        "symbol": ticker,
        "side": "SELL",
        "type": "MARKET",
        "quantity": quantity
    }
    response = trade.post_order(params)
    return response
        

def ticker_driver_buy(ticker):
    selector = "#__next > section > div.exchange_wrapper__u_qZX.exchange_layoutMX__0zSjA > div.exchange_actionWrapper__7IkvE > div.actions_middleWrapper__cjxMT > div.actions_buySellWrapper__HD1OD > div.actions_buyWrapper__y_ZSB.actions_doWrapper__POGvp > div:nth-child(3) > div:nth-child(2) > span > input"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).send_keys("10")
    selector = "#__next > section > div.exchange_wrapper__u_qZX.exchange_layoutMX__0zSjA > div.exchange_actionWrapper__7IkvE > div.actions_middleWrapper__cjxMT > div.actions_buySellWrapper__HD1OD > div.actions_buyWrapper__y_ZSB.actions_doWrapper__POGvp > div.do-submit_buyBtnWrapper__Cu6Xe > button"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()
    tickers = account.get_account_info()['balances']
    for t in tickers:
        if ticker == t:
            quantity = float(t['free'])
    return quantity


def ticker_driver_sell(quantity):
    selector = "#__next > section > div.exchange_wrapper__u_qZX.exchange_layoutMX__0zSjA > div.exchange_actionWrapper__7IkvE > div.actions_middleWrapper__cjxMT > div.actions_buySellWrapper__HD1OD > div.actions_sellWrapper__J5fJU.actions_doWrapper__POGvp > div:nth-child(3) > div:nth-child(1) > span > input"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).send_keys(quantity)
    selector = "#__next > section > div.exchange_wrapper__u_qZX.exchange_layoutMX__0zSjA > div.exchange_actionWrapper__7IkvE > div.actions_middleWrapper__cjxMT > div.actions_buySellWrapper__HD1OD > div.actions_sellWrapper__J5fJU.actions_doWrapper__POGvp > div.do-submit_sellBtnWrapper__1oHbv > button"
    driver.find_element(by=By.CSS_SELECTOR, value=selector).click()


def get_capital_price(ticker):
    ord_price = 0.6272
    params = {
        'symbol':ticker
    }
    current_price = float(market.get_price(params=params)['price'])
    current_profit = (current_price - ord_price)/ord_price*100
    tickers = account.get_account_info()['balances']
    for t in tickers:
        if ticker == t:
            volume = float(t['free'])
    total_worth = round(volume*current_price,2)
    values = {
        'current_price':current_price,
        'order_price':ord_price,
        'current_profit':current_profit,
        'total_worth':total_worth
    }
    return values


def driver_exit():
    driver.close()
    driver.quit()


def telegram_response(update, context):

    return


def main():
    updater = Updater(token=token, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_response))
    updater.start_polling()
    updater.idle()
    tickers = {}
    while True:
        new_tickers = get_new_tickers()
        for new_ticker in new_tickers:
            if not tickers.get(new_ticker):
                tickers[new_ticker] = {}
                tickers[new_ticker]['launch_time'] = tickers_launck_time(new_ticker)
                print(f"{new_ticker} will be awailable at {tickers[new_ticker]['launch_time']} UTC")
        for ticker in tickers:
            if datetime.now() < ticker['launch_time'] + timedelta(minutes=15):
                print(f"{ticker} is about to launch, getting ready...")
                if mexc_login(ticker):
                    print("driver is ready.")
                while True:
                    if datetime.now() < ticker['launch_time'] + timedelta(seconds=2):
                        if check_ticker_api(ticker):
                            tr = ticker_api_buy(ticker)
                            time.sleep(10)
                            ticker_api_sell(ticker, tr['buy_qty'])
                        else:
                            quantity = ticker_driver_buy(ticker)
                            time.sleep(10)
                            ticker_driver_sell(quantity)
                        tickers[ticker].pop()
                        break
        time.sleep(60)


# if __name__ == "__main__":
#     try:
#         main()
#     except Exception as e:
#         print(e)
#         driver_exit()