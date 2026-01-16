import io
import time
import traceback
from typing import Optional, Tuple

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from .models import FileMeta, ReportMeta, ReportLog


def create_filemeta(owner, original_name: str, storage_path: str, size_bytes: Optional[int] = None) -> FileMeta:
   
    return FileMeta.objects.create(
        owner=owner,
        original_name=original_name,
        storage_path=storage_path,
        size_bytes=size_bytes
    )


def get_filemeta_from_session(request) -> Optional[FileMeta]:
    
    fm_id = request.session.get('uploaded_file_meta_id')
    if not fm_id:
        return None
    return FileMeta.objects.filter(id=fm_id).first()


def create_report(owner, file_meta: Optional[FileMeta] = None) -> ReportMeta:
    
    return ReportMeta.objects.create(owner=owner, file=file_meta)


def add_report_log(report: ReportMeta, owner, message: str) -> ReportLog:

    # короткая строка лога в БД.
    return ReportLog.objects.create(report=report, owner=owner, message=message)


def safe_run_analysis(report: ReportMeta, owner, func, *args, **kwargs) -> Tuple[Optional[str], Optional[bytes], Optional[str]]:
    
    start = time.time()
    add_report_log(report, owner, "analysis started")
    try:
        summary, result_bytes, result_filename = func(*args, **kwargs)
        duration = time.time() - start
        report.summary = summary
        report.duration_seconds = duration
        report.save(update_fields=['summary', 'duration_seconds'])
        add_report_log(report, owner, "analysis finished")
        return summary, result_bytes, result_filename
    except Exception as exc:
        tb = traceback.format_exc()
        report.error = tb
        report.save(update_fields=['error'])
        add_report_log(report, owner, f"analysis failed: {str(exc)}")
        raise


def cleanup_uploaded_file_and_session(request):
    rel_path = request.session.get('uploaded_file_path')
    if rel_path:
        try:
            default_storage.delete(rel_path)
        except Exception:
            pass
    for k in ('uploaded_file_path','uploaded_file_meta_id','uploaded_columns','uploaded_preview_rows','describe_selected_cols'):
        request.session.pop(k, None)
