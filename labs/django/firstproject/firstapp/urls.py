from django.urls import path
from . import views

urlpatterns = [
# Create a path object defining the URL pattern to the index view
path(route='', view=views.index, name='index'),
]