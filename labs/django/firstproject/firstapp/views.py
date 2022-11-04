from django.shortcuts import render
from django.http import HttpResponse
import datetime

def index(request):
    # Create a simple html page as a string
    today = datetime.date.today()
    template = "<html>" \
    "Today is: {}" \
    "</html>".format(today)
    # Return the template as content argument in HTTP response
    return HttpResponse(content=template)
