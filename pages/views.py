from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.template.response import TemplateResponse
import pandas as pd
from django.core.files.storage import default_storage
from analysis.utils import cleanup_uploaded_file_and_session

# Create your views here.



def index(request):
    # Всегда очищаем временные файлы и связанные ключи при заходе на главную
    try:
        cleanup_uploaded_file_and_session(request)
    except Exception as e:
        # можно залогировать ошибку, чтобы не потерять информацию
        print(f"Ошибка очистки: {e}")

    # Пустой контекст — стартовая страница
    return render(request, 'index.html', {})



def about(request):
    return render(request, 'index.html', {
        'selected_partial': 'project.html',
    })


def author(request):
    return render(request, 'index.html', {
        'selected_partial': 'contact.html',
    })


