from django.db import models
from django.conf import settings
from django.utils import timezone

class FileMeta(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    original_name = models.CharField(max_length=512)
    storage_path = models.CharField(max_length=1024)   # информационный путь во временном хранилище
    size_bytes = models.BigIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.original_name} ({self.owner})"


class ReportMeta(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.ForeignKey(FileMeta, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField(null=True, blank=True)       # краткий итог
    error = models.TextField(null=True, blank=True)         # текст ошибки, если была
    duration_seconds = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Report {self.id} by {self.owner}"


class ReportLog(models.Model):
    report = models.ForeignKey(ReportMeta, on_delete=models.CASCADE, related_name='logs')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    message = models.TextField()

    def __str__(self):
        return f"Log {self.id} for report {self.report_id}"
