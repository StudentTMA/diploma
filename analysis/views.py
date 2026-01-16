import os
import uuid
import io
import base64

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseForbidden, FileResponse, Http404, HttpResponse
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analysis.utils import (
    create_filemeta,
    get_filemeta_from_session,
    create_report,
    add_report_log,
    safe_run_analysis,
    cleanup_uploaded_file_and_session
)

MAX_ROWS = 1000
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

def _user_tmp_dir(user):
    return os.path.join('tmp', str(user.id))

def _is_path_in_user_tmp(rel_path, user):
    #  путь должен начинаться с tmp/<user.id>/
    norm = os.path.normpath(rel_path)
    return norm.startswith(os.path.normpath(os.path.join('tmp', str(user.id))))

@login_required
def column_chart(request):
    # рендерим index с selected_partial 
    columns = request.session.get('uploaded_columns', [])
    preview_rows = request.session.get('uploaded_preview_rows', [])
    return render(request, 'index.html', {
        'selected_partial': 'column_chart.html',
        'columns': columns,
        'rows': preview_rows,
        'show_preview': bool(preview_rows),
    })

@login_required
def open_file(request):
    if request.method != 'POST' or 'file' not in request.FILES:
        return redirect('column_chart')

    f = request.FILES['file']
    if f.size > MAX_BYTES:
        return HttpResponseBadRequest(f"Файл слишком большой. Максимум {MAX_BYTES // (1024*1024)} MB.")

    tmp_dir = _user_tmp_dir(request.user)
    filename = f"{uuid.uuid4().hex}_{f.name}"
    rel_path = os.path.join(tmp_dir, filename)

    saved_rel_path = default_storage.save(rel_path, f)
    full_path = default_storage.path(saved_rel_path)

    try:
        df_head = pd.read_csv(full_path, nrows=MAX_ROWS + 1)
    except Exception as e:
        default_storage.delete(saved_rel_path)
    
        return HttpResponseBadRequest("Ошибка чтения CSV: " + str(e))

    if len(df_head) > MAX_ROWS:
        default_storage.delete(saved_rel_path)
        return HttpResponseBadRequest(f"Файл слишком большой. Максимум {MAX_ROWS} строк.")

    preview_rows = df_head.head(10).values.tolist()
    columns = df_head.columns.tolist()

    # log_filemeta
    file_meta = create_filemeta(
        owner=request.user,
        original_name=f.name,
        storage_path=saved_rel_path,
        size_bytes=getattr(f, 'size', None)
    )
    request.session['uploaded_file_meta_id'] = file_meta.id
    request.session['uploaded_file_path'] = saved_rel_path
    request.session['uploaded_columns'] = columns
    request.session['uploaded_preview_rows'] = preview_rows

#  короткий лог о загрузке 



   
  
    next_partial = request.POST.get('next_partial', '').strip()

    #  валидация  только конкретные имена partial, которые есть в проекте
    allowed_partials = {
        'column_chart.html',
        'descriptive_statistics.html',
        'correlation.html',
    
    }
    if next_partial not in allowed_partials:
        
        next_partial = 'column_chart.html'

    
    return render(request, 'index.html', {
        'selected_partial': next_partial,
        'columns': columns,
        'rows': preview_rows,
        'show_preview': True,
    })



@login_required
def run_analysis(request):
    if request.method != 'POST':
        return redirect('column_chart')

    analysis_type = request.POST.get('analysis_type', 'column_chart')
    rel_path = request.session.get('uploaded_file_path')

    if not rel_path or not default_storage.exists(rel_path):
        return render(request, 'index.html', {
            'selected_partial': 'column_chart.html',
            'error': 'CSV не загружен. Пожалуйста, загрузите файл.',
            'columns': request.session.get('uploaded_columns', []),
        })

    if not _is_path_in_user_tmp(rel_path, request.user):
        return HttpResponseForbidden("Недопустимый путь к файлу.")

    full_path = default_storage.path(rel_path)

    try:
        df = pd.read_csv(full_path)
    except Exception as e:
        return render(request, 'index.html', {
            'selected_partial': 'column_chart.html',
            'error': 'Ошибка чтения CSV: ' + str(e),
            'columns': request.session.get('uploaded_columns', []),
        })

    if analysis_type in ('column_chart', 'plot'):
        selected = request.POST.getlist('columns')
        plot_type = request.POST.get('plot_type', 'hist')

        if not selected:
            return render(request, 'index.html', {
                'selected_partial': 'column_chart.html',
                'error': 'Выберите хотя бы одну колонку.',
                'columns': list(df.columns),
            })

        for c in selected:
            if c not in df.columns:
                return render(request, 'index.html', {
                    'selected_partial': 'column_chart.html',
                    'error': f'Колонка {c} не найдена в файле.',
                    'columns': list(df.columns),
                })

        #файл мета
        file_meta = get_filemeta_from_session(request)
        report = create_report(request.user, file_meta)
        add_report_log(report, request.user, "report created")

        
        def do_column_chart(df_local, selected_cols, plot_t):
            n = len(selected_cols)
            fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(6, 3*n))
            if n == 1:
                axes = [axes]
            for ax, col in zip(axes, selected_cols):
                series = pd.to_numeric(df_local[col], errors='coerce').dropna()
                if series.empty:
                    ax.text(0.5, 0.5, 'Нет числовых данных', ha='center')
                    continue
                if plot_t == 'hist':
                    ax.hist(series, bins=30, color='#2b8cbe', edgecolor='black')
                    ax.set_title(col)
                elif plot_t == 'line':
                    ax.plot(series.index, series.values, color='#2b8cbe')
                    ax.set_title(col)
                elif plot_t == 'box':
                    ax.boxplot(series.dropna())
                    ax.set_title(col)
                else:
                    ax.hist(series, bins=30)
                    ax.set_title(col)
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return f"Chart for {len(selected_cols)} columns", buf.read(), 'chart.png'

        try:
            
            summary, result_bytes, filename = safe_run_analysis(report, request.user, do_column_chart, df, selected, plot_type)

            #  байты результата отобразим их в шаблоне
            img_b64 = None
            if result_bytes:
                img_b64 = base64.b64encode(result_bytes).decode('ascii')

            return render(request, 'index.html', {
                'selected_partial': 'column_chart.html',
                'plot': img_b64,
                'columns': list(df.columns),
                'report_summary': summary,
            })
        except Exception as e:
            
            return render(request, 'index.html', {
                'selected_partial': 'column_chart.html',
                'error': 'Ошибка построения графика: ' + str(e),
                'columns': list(df.columns),
            })
        finally:
            
            cleanup_uploaded_file_and_session(request)

    return render(request, 'index.html', {
        'selected_partial': 'column_chart.html',
        'error': 'Неизвестный тип анализа',
        'columns': request.session.get('uploaded_columns', []),
    })




def delete_uploaded_file_from_disk(request):
    
    rel_path = request.session.get('uploaded_file_path')
    if not rel_path:
        return False
    if not _is_path_in_user_tmp(rel_path, request.user):
        return False
    try:
        if default_storage.exists(rel_path):
            default_storage.delete(rel_path)
    except Exception:
        
        return False
    # удалили файл с диска, но оставляем метаданные в сессии
    request.session.pop('uploaded_file_path', None)
    return True


@login_required
def clear_upload(request):
    if request.method != 'POST':
        
        return redirect('index')

    # удаляем файл и очищаем все сессионные метаданные
    rel_path = request.session.get('uploaded_file_path')
    if rel_path and _is_path_in_user_tmp(rel_path, request.user) and default_storage.exists(rel_path):
        try:
            default_storage.delete(rel_path)
        except Exception:
            pass

    # полная очистка сесси- заново
    request.session.pop('uploaded_file_path', None)
    request.session.pop('uploaded_columns', None)
    request.session.pop('uploaded_preview_rows', None)
    request.session.pop('uploaded_file_name', None)
    request.session.pop('describe_selected_cols', None)

    return redirect('index')


@login_required
def describe(request):
    
    if request.method == 'GET':
        return render(request, 'index.html', {
            'selected_partial': 'descriptive_statistics.html',
            'columns': request.session.get('uploaded_columns', []),
            'rows': request.session.get('uploaded_preview_rows', []),
            'show_preview': bool(request.session.get('uploaded_preview_rows')),
            'selected_cols': request.session.get('describe_selected_cols', []),
        })

    
    if bool(request.POST.get('download_csv')) and request.session.get('last_describe_csv'):
        csv_text = request.session.pop('last_describe_csv')
        csv_bytes = ('\ufeff' + csv_text).encode('utf-8')
        resp = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="describe.csv"'
        return resp

    
    rel_path = request.session.get('uploaded_file_path')
    if not rel_path or not default_storage.exists(rel_path):
        return render(request, 'index.html', {
            'selected_partial': 'descriptive_statistics.html',
            'error': 'CSV не загружен. Пожалуйста, загрузите файл.',
            'columns': request.session.get('uploaded_columns', []),
        })

    if not _is_path_in_user_tmp(rel_path, request.user):
        return HttpResponseForbidden("Недопустимый путь к файлу.")

    full_path = default_storage.path(rel_path)
    try:
        df = pd.read_csv(full_path)
    except Exception as e:
        return render(request, 'index.html', {
            'selected_partial': 'descriptive_statistics.html',
            'error': 'Ошибка чтения CSV: ' + str(e),
            'columns': request.session.get('uploaded_columns', []),
        })

   
    selected = request.POST.getlist('columns') or list(df.columns)
    include_plots = bool(request.POST.get('include_plots'))
    download_csv = bool(request.POST.get('download_csv'))

    
    request.session['describe_selected_cols'] = selected

    # Валидация 
    for c in selected:
        if c not in df.columns:
            return render(request, 'index.html', {
                'selected_partial': 'descriptive_statistics.html',
                'error': f'Колонка {c} не найдена в файле.',
                'columns': list(df.columns),
            })

    # ReportMeta и лог о создании
    file_meta = get_filemeta_from_session(request)
    report = create_report(request.user, file_meta)
    add_report_log(report, request.user, "report created for describe")

    #  внешние переменные для результата HTML и графиков
    result_html = None
    plots = {}

    
    def do_describe(df_local, selected_cols, include_plots_flag):
        nonlocal result_html, plots
        metrics = []
        plots = {}

        for col in selected_cols:
            series = df_local[col]
            n = len(series)
            missing = int(series.isna().sum())
            unique = int(series.nunique(dropna=True))
            dtype = str(series.dtype)
            row = {
                'column': col,
                'dtype': dtype,
                'n': n,
                'missing': missing,
                'missing_pct': round(missing / n, 4) if n else None,
                'unique': unique,
            }

            s_num = pd.to_numeric(series, errors='coerce')
            if s_num.dropna().size > 0:
                s = s_num.dropna()
                mean = s.mean() if not s.empty else None
                std = s.std() if not s.empty else None
                row.update({
                    'mean': float(mean) if mean is not None else None,
                    'median': float(s.median()) if not s.empty else None,
                    'std': float(std) if not s.empty else None,
                    'var': float(s.var()) if not s.empty else None,
                    'min': float(s.min()) if not s.empty else None,
                    '25%': float(s.quantile(0.25)) if not s.empty else None,
                    '50%': float(s.quantile(0.5)) if not s.empty else None,
                    '75%': float(s.quantile(0.75)) if not s.empty else None,
                    'max': float(s.max()) if not s.empty else None,
                    'iqr': float(s.quantile(0.75) - s.quantile(0.25)) if not s.empty else None,
                    'skew': float(s.skew()) if not s.empty else None,
                    'kurtosis': float(s.kurtosis()) if not s.empty else None,
                    'zeros': int((s == 0).sum()),
                    'negatives': int((s < 0).sum()),
                })
                if include_plots_flag:
                    try:
                        fig, ax = plt.subplots(figsize=(6,3))
                        ax.hist(s, bins=30, color='#2b8cbe', edgecolor='black')
                        ax.set_title(f'{col} — histogram')
                        plt.tight_layout()
                        buf = io.BytesIO()
                        plt.savefig(buf, format='png', bbox_inches='tight')
                        plt.close(fig)
                        buf.seek(0)
                        plots[col] = base64.b64encode(buf.read()).decode('ascii')
                    except Exception:
                        # не ломаем из‑за одного графика
                        pass

            metrics.append(row)

        
        df_metrics = pd.DataFrame(metrics).set_index('column')

       
        rename_map = {
            'dtype': 'Тип', 'n': 'N', 'missing': 'Пропуски', 'missing_pct': 'Доля пропусков',
            'unique': 'Уникальных', 'mean': 'Среднее', 'median': 'Медиана', 'std': 'Стд',
            'var': 'Дисперсия', 'min': 'Мин', '25%': '25%', '50%': '50%', '75%': '75%',
            'max': 'Макс', 'iqr': 'IQR', 'skew': 'Асимметрия', 'kurtosis': 'Куртозис',
            'zeros': 'Нулей', 'negatives': 'Отрицательных'
        }
        df_metrics = df_metrics.rename(columns=rename_map)

       
        def safe_div(a, b):
            try:
                if a is None or b is None:
                    return None
                if b == 0:
                    return None
                return a / b
            except Exception:
                return None

        if 'Среднее' in df_metrics.columns and 'Стд' in df_metrics.columns:
            def compute_cv_row(r):
                std = r.get('Стд')
                mean = r.get('Среднее')
                if pd.isna(std) or pd.isna(mean) or mean == 0:
                    return None
                val = safe_div(std, mean)
                return round(val, 3) if val is not None else None
            df_metrics['CV'] = df_metrics.apply(compute_cv_row, axis=1)
        else:
            if 'mean' in df_metrics.columns and 'std' in df_metrics.columns:
                def compute_cv_row_alt(r):
                    std = r.get('std')
                    mean = r.get('mean')
                    if pd.isna(std) or pd.isna(mean) or mean == 0:
                        return None
                    val = safe_div(std, mean)
                    return round(val, 3) if val is not None else None
                df_metrics['CV'] = df_metrics.apply(compute_cv_row_alt, axis=1)

        # Интерпретация
        def interpret(row):
            notes = []
            mp = row.get('Доля пропусков') or row.get('missing_pct')
            if mp is not None and mp > 0.2:
                notes.append('Много пропусков')
            cv = row.get('CV')
            if cv is not None:
                if abs(cv) > 1:
                    notes.append('Высокая дисперсия (CV>1)')
                elif abs(cv) > 0.5:
                    notes.append('Умеренная дисперсия (CV>0.5)')
            skew = row.get('Асимметрия') or row.get('skew')
            if skew is not None and abs(skew) > 1:
                notes.append('Сильная асимметрия')
            uniq = row.get('Уникальных') or row.get('unique')
            if uniq is not None and isinstance(uniq, (int, float)) and uniq > 0 and row.get('N') and uniq / row.get('N') > 0.5:
                notes.append('Много уникальных значений')
            return '; '.join(notes)

        df_metrics['Интерпретация'] = df_metrics.apply(interpret, axis=1)

    
        for c in df_metrics.columns:
            if pd.api.types.is_float_dtype(df_metrics[c]) or pd.api.types.is_integer_dtype(df_metrics[c]):
                df_metrics[c] = df_metrics[c].apply(lambda v: round(v, 3) if pd.notna(v) else v)

        # Транспонируем таблицу
        df_out = df_metrics.T
        df_out.index.name = None

        # HTML результат
        table_html = df_out.to_html(classes='table table-sm table-bordered', na_rep='', escape=False)
        result_html = f'<div class="table-responsive" style="max-height:420px; overflow:auto;">{table_html}</div>'

        # CSV для скачивания
        csv_text = df_out.to_csv()
        csv_bytes = ('\ufeff' + csv_text).encode('utf-8')

        summary_text = f"Describe: {len(selected_cols)} columns"
        return summary_text, csv_bytes, 'describe.csv'

    
    try:
        summary, result_bytes, filename = safe_run_analysis(report, request.user, do_describe, df, selected, include_plots)

        
        if download_csv and result_bytes:
            resp = HttpResponse(result_bytes, content_type='text/csv; charset=utf-8')
            resp['Content-Disposition'] = 'attachment; filename="describe.csv"'
            return resp

        
        if result_bytes:
            try:
                csv_text = result_bytes.decode('utf-8')
                request.session['last_describe_csv'] = csv_text
            except Exception:
                request.session.pop('last_describe_csv', None)

        # Рендерим страницу с HTML таблицей и графиками
        return render(request, 'index.html', {
            'selected_partial': 'descriptive_statistics.html',
            'result': result_html,
            'plots': plots,
            'columns': list(df.columns),
            'rows': request.session.get('uploaded_preview_rows', []),
            'show_preview': bool(request.session.get('uploaded_preview_rows')),
            'selected_cols': selected,
            'report_summary': summary,
        })

    except Exception as e:
        # safe_run_analysis уже записал report.error и лог
        return render(request, 'index.html', {
            'selected_partial': 'descriptive_statistics.html',
            'error': 'Ошибка анализа: ' + str(e),
            'columns': list(df.columns),
        })

    finally:
        cleanup_uploaded_file_and_session(request)



@login_required
def descriptive_statistics(request):
   
    columns = request.session.get('uploaded_columns', [])
    preview_rows = request.session.get('uploaded_preview_rows', [])
    return render(request, 'index.html', {
        'selected_partial': 'descriptive_statistics.html',
        'columns': columns,
        'rows': preview_rows,
        'show_preview': bool(preview_rows),
        'uploaded_file_name': request.session.get('uploaded_file_name'),
        'selected_cols': request.session.get('describe_selected_cols', []),
    })


@login_required
def correlation(request):
    
    columns = request.session.get('uploaded_columns', [])
    preview_rows = request.session.get('uploaded_preview_rows', [])
    return render(request, 'index.html', {
        'selected_partial': 'correlation.html',
        'columns': columns,
        'rows': preview_rows,
        'show_preview': bool(preview_rows),
        'uploaded_file_name': request.session.get('uploaded_file_name'),
        'selected_cols': request.session.get('correlation_selected_cols', []),
    })

@login_required
def run_correlation(request):
    if request.method == 'GET':
        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'columns': request.session.get('uploaded_columns', []),
            'rows': request.session.get('uploaded_preview_rows', []),
            'show_preview': bool(request.session.get('uploaded_preview_rows')),
            'selected_cols': request.session.get('correlation_selected_cols', []),
            'button_label': 'Анализировать',
        })

    # наличие файла
    rel_path = request.session.get('uploaded_file_path')
    if not rel_path or not default_storage.exists(rel_path):
        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'error': 'CSV не загружен.',
            'columns': request.session.get('uploaded_columns', []),
        })

    if not _is_path_in_user_tmp(rel_path, request.user):
        return HttpResponseForbidden("Недопустимый путь к файлу.")

    try:
        df = pd.read_csv(default_storage.path(rel_path))
    except Exception as e:
        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'error': 'Ошибка чтения CSV: ' + str(e),
            'columns': request.session.get('uploaded_columns', []),
        })

    selected = request.POST.getlist('columns') or []
    request.session['correlation_selected_cols'] = selected

    if len(selected) != 2:
        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'error': 'Выберите ровно две колонки.',
            'columns': list(df.columns),
        })

    file_meta = get_filemeta_from_session(request)
    report = create_report(request.user, file_meta)
    add_report_log(report, request.user, "report created for correlation")

    plot_img = None

    def do_correlation(df_local, selected_cols):
        nonlocal plot_img
        xcol, ycol = selected_cols
        x = pd.to_numeric(df_local[xcol], errors='coerce')
        y = pd.to_numeric(df_local[ycol], errors='coerce')
        df_clean = pd.DataFrame({xcol: x, ycol: y}).dropna()
        if df_clean.shape[0] < 2:
            raise ValueError("Недостаточно данных для корреляции.")

        corr = df_clean[xcol].corr(df_clean[ycol], method='pearson')

        fig, ax = plt.subplots(figsize=(6,4))
        ax.scatter(df_clean[xcol], df_clean[ycol], alpha=0.7, color='#2b8cbe')
        ax.set_xlabel(xcol)
        ax.set_ylabel(ycol)
        ax.set_title(f'Диаграмма рассеяния ({xcol} vs {ycol}), r={corr:.3f}')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        plot_img = base64.b64encode(buf.read()).decode('ascii')

        summary_text = f"Correlation (Pearson) between {xcol} and {ycol}: r={corr:.3f}, n={df_clean.shape[0]}"
        return summary_text, None, None  # нет CSV

    try:
        summary, _, _ = safe_run_analysis(report, request.user, do_correlation, df, selected)

        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'plot_img': plot_img,
            'columns': list(df.columns),
            'rows': request.session.get('uploaded_preview_rows', []),
            'show_preview': bool(request.session.get('uploaded_preview_rows')),
            'selected_cols': selected,
            'report_summary': summary,
            'button_label': 'Анализировать',
        })

    except Exception as exc:
        return render(request, 'index.html', {
            'selected_partial': 'correlation.html',
            'error': 'Ошибка анализа: ' + str(exc),
            'columns': list(df.columns),
        })

    finally:
        cleanup_uploaded_file_and_session(request)
