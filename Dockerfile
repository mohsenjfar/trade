FROM python:3
COPY mexc_spot_v3.py mexc_spot_v3.py
COPY requirements.txt requirements.txt
COPY trade.py trade.py
RUN pip3 install -r requirements.txt
CMD python trade.py