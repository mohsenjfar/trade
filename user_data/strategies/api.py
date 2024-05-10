import requests
from datetime import datetime

base_url = "http://localhost:8000"

def create_parent(title):
    url = f"{base_url}/parent"
    data = {
        'title': title
    }
    res = requests.post(url=f"{url}/filter/", data=data)
    if res.status_code == 400:
        return requests.post(url=f"{url}/", data=data).json()
    return res.json()[0]

def complete(trade):
    url = f'{base_url}/tasks/{trade.get_custom_data(key="task_id")}/complete/'
    data = {
        "due": trade.close_date,
        "profit": trade.close_profit_abs
    }
    return requests.post(url, data=data).json()

def create_task(trade, parent):
    url = f"{base_url}/parent/filter/"
    data = {
        'title': parent
    }
    parent = requests.post(url=url,data=data).json()[0]
    data = {
        "parent": parent.get('url'),
        "summary": f"{parent.get('title')} (#{trade.id})",
        "start": trade.open_date,
        "due": datetime.now()
    }
    url = f"{base_url}/tasks/"
    return requests.post(url, data=data).json()

def update_task(trade, current_time):
    url = f'{base_url}/tasks/{trade.get_custom_data(key="task_id")}/log_update/'
    data = {
        "due": current_time,
        "profit": trade.total_profit
    }
    requests.post(url, data=data)

