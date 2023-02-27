from django.db import models
from django.utils import timezone

class Ticker(models.Model):
    price = models.FloatField(default=0)
    time = models.DateTimeField(default=timezone.now)