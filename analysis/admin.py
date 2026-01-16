from django.contrib import admin
from .models import FileMeta, ReportMeta, ReportLog


@admin.register(FileMeta)
class FileMetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'original_name', 'size_bytes', 'uploaded_at')
    search_fields = ('original_name', 'owner__username', 'owner__email')
    list_filter = ('uploaded_at',)


@admin.register(ReportMeta)
class ReportMetaAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner', 'file', 'created_at', 'duration_seconds', 'error')
    search_fields = ('owner__username', 'owner__email', 'summary')
    list_filter = ('created_at',)


@admin.register(ReportLog)
class ReportLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'report', 'owner', 'created_at', 'message')
    search_fields = ('message', 'owner__username', 'owner__email')
    list_filter = ('created_at',)
