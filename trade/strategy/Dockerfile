FROM python:3
COPY tasks/models.py /root/logos/tasks/models.py
COPY bot/requirements.txt /root/logos/bot/requirements.txt
COPY logos/settings.py /root/logos/logos/settings.py
COPY bot/bot.py /root/logos/bot/bot.py
COPY tasks/apps.py /root/logos/tasks/apps.py
RUN pip3 install -r /root/logos/bot/requirements.txt
CMD python /root/logos/bot/bot.py