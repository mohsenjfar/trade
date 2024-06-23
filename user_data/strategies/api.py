import requests
from datetime import datetime

base_url = "http://localhost:8000"

def create_parent(title, initial_stake):
    url = f"{base_url}/parent"
    data = {
        'title': title
    }
    parent = requests.post(url=f"{url}/filter/", data=data)
    if parent.status_code == 400:
        parent = requests.post(url=f"{url}/", data=data).json()
        data = {
            "parent": parent.get('url'),
            "summary": f"{parent.get('title')}",
            "start": datetime.now(),
            "due": datetime.now()
        }
        task = requests.post(f"{base_url}/tasks/", data=data).json()
        url = f'{base_url}/tasks/{task.get('id')}/log_update/'
        data = {
            "due": datetime.now(),
            "profit": initial_stake
        }
        requests.post(url, data=data)
        return f"{parent.get('title')} was created with total stake amount of {initial_stake}"
    return f"{title} already exists"

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

