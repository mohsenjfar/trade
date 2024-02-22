import time
import logging
import os
import cctx
import django
import sys
from django.utils import timezone
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from kucoin.client import Market
from kucoin.client import User
from kucoin.client import Trade
import pandas as pd
import datetime
import pyt

sys.path.append('/root/trade/trade')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trade.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from trade.models import Order

logger = logging.getLogger(__name__)
handler = logging.FileHandler('break.log', mode='a')
format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(format)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

binance = ccxt.binance()

kucoin = ccxt.kucoin()
kucoin.apiKey = os.environ.get('key')
exchange.secret = os.environ.get('secret')
exchange.password = os.environ.get('passphrase')

token = os.environ.get('token')

async def start(update, context):
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id, text=text)
    context.job_queue.run_repeating(
        scheduled_tasks, 
        5,
        chat_id=chat_id,
        name=str(chat_id),
        first=1
    )
    text = 'Bot successfully started'
    context.chat_data['notifications'] = {}
    context.chat_data['orders'] = {}
    context.chat_data['timeframe'] = '15min'

async def notification_check(context, chat_id):
    notifications = context.chat_data['notifications']
    for ticker in notifications:
        if ticker['direction'] == 'up':
            if price > ticker['price']:
                text = f"Price just crossed above {ticker['price']} for {ticker['name']}"
                await context.bot.send_message(chat_id, text=text)
        elif ticker['direction'] == 'down':
            if price < ticker['price']:
                text = f"Price just crossed below {ticker['price']} for {ticker['name']}"
                await context.bot.send_message(chat_id, text=text)

async def stoploss_check(context):
    
    # retrieve open trades from database and check their risk to reward ratio and set new stop
    return

async buy_order_check(update, context):
    # check context.chat_data['orders'] and if price is crossed above that price place buy order
    return

async def place_buy_order(update, context):
    # if price is awailabel place order with this price else market
    return

async def force_exit(update, context):

    return

async def open_trades(update, context):
    return

async def timeframe_change(update, context):
    new_timeframe = 
    return

async def scheduled_tasks(context):
    logger.info('Heartbeat')
    chat_id = context.job.chat_id
    await stoploss_check(context)
    await buy_order_check(update, context)
    await notification_check(context, chat_id)

async def stop(update, context):
    chat_id = update.message.chat_id
    remove_job_if_exists(str(chat_id), context)
    text = "Bot Successfully stopped!"
    await context.bot.send_message(chat_id, text=text)

def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def main() -> None:
    application = Application.builder().token(token).read_timeout(10).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", place_buy_order))
    application.add_handler(CommandHandler("fx", force_exit))
    application.add_handler(CommandHandler("trades", open_trades))
    application.add_handler(CommandHandler("timeframe", timeframe_change))
    application.add_handler(CommandHandler("stop", stop))
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()