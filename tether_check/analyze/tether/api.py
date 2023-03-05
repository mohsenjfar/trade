import sys, os, django
sys.path.append('/home//Documents/cryptobot/tether_check/analyze')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analyze.settings")
django.setup()

from tether.models import Ticker
import requests
import time

url = "https://abantether.com/api/v1/otc/coin-price/"
headers = {'Authorization': 'Token d5bb0cb1b9ae9f480e000da41678def4d9cd30fd'}

bot_url = "https://api.telegram.org/bot6233446929%3AAAE9qKnXSiweUxFF_m4i57uNAO2WobOtSv0/sendMessage"

bot_headers = {
    "accept": "application/json",
    "content-type": "application/json"
}

last_price = Ticker.objects.last().price

while True:
    res = requests.get(url, headers=headers)
    sell_price = eval(res.text)['USDT']['irtPriceSell']
    if sell_price != last_price:
        Ticker.objects.create(price=sell_price)
        # payload = {
        #     "text": f"{last_price}",
        #     "disable_web_page_preview": False,
        #     "disable_notification": False,
        #     "reply_to_message_id": None,
        #     "chat_id": "@jfar_platform_bot"
        # }
        # response = requests.post(bot_url, json=payload, headers=bot_headers)
        last_price = sell_price
    time.sleep(30)