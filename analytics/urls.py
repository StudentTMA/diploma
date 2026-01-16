"""
URL configuration for analytics project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from pages import views as pages_views
from analysis import views as analysis_views

from django.conf import settings
from django.conf.urls.static import static




urlpatterns = [
    
   # path('postfile/', views.open_file, name='postfile'),
    path('admin/', admin.site.urls),
    path('', pages_views.index, name='index'),
    path('auth/', include('social_django.urls', namespace='social')), # Google OAuth
    path('about/', pages_views.about, name='about'),
    path('author/', pages_views.author, name='author'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('postfile/', analysis_views.open_file, name='postfile'),
    path('column-chart/', analysis_views.column_chart, name='column_chart'),
    path('analysis/run/', analysis_views.run_analysis, name='run_analysis'),
    path('analysis/describe/', analysis_views.descriptive_statistics, name='descriptive_statistics'),
    path('analysis/describe/run/', analysis_views.describe, name='describe'),
    path('analysis/correlation/', analysis_views.correlation, name='correlation'),
    path('analysis/correlation/run/', analysis_views.run_correlation, name='run_correlation'),
    path('analysis/clear_upload/', analysis_views.clear_upload, name='clear_upload'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)