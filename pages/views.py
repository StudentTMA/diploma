from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.response import TemplateResponse
import pandas as pd

# Create your views here.
def index(request):
    return TemplateResponse(request, 'index.html')

def open_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        df = pd.read_csv(file)  # читаем CSV в pandas

        # Сохраняем в сессию как JSON
        #request.session['df'] = df.to_json()

        # Получаем список колонок и первые строки
        columns = df.columns.tolist()
        rows= df.values.tolist()
        #preview = df.head().to_html(classes="table table-bordered")

        return render(request, 'index.html', {
            'columns': columns,
            'rows': rows,
            'show_preview': True
        })
    return redirect('index')