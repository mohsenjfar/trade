from django.db import models
from django.utils import timezone

class Order(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    ticker = models.CharField(max_length=30)
    size = models.FloatField()
    price = models.FloatField()
    risk = models.FloatField()
    date = models.DateTimeField(timezone.now())