from django.shortcuts import render
from tether.models import Ticker
import pandas as pd
from plotly.offline import plot
import plotly.express as px

def index(request):
    qs = Ticker.objects.all()
    projects_data = [
        {
            'price': x.price,
            'time': x.time,
        } for x in qs
    ]
    df = pd.DataFrame(projects_data)
    fig = px.line(
        df, x="time", y="price"
    )
    gantt_plot = plot(fig, output_type="div")
    context = {'plot_div': gantt_plot}
    return render(request, 'index.html', context)