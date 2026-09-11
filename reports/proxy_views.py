import requests
from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from reports.models import DailyReportSummary, ReportReaction, ReportComment

HOP_BY_HOP_HEADERS = {
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailers',
    'transfer-encoding',
    'upgrade',
    'host',
    'content-length',
}


def _enrich_reports_with_social_data(reports, nik):
    encoded_keys = [r.get('encoded_key') for r in reports if r.get('encoded_key')]
    if not encoded_keys:
        return reports

    summaries = {s.encoded_key: s.id for s in DailyReportSummary.objects.filter(encoded_key__in=encoded_keys)}
    report_ids = list(summaries.values())

    counts_map = {}
    user_reaction_map = {}
    for r in ReportReaction.objects.filter(report_id__in=report_ids, comment__isnull=True).select_related('user'):
        bucket = counts_map.setdefault(r.report_id, {'like': 0, 'dislike': 0, 'love': 0})
        bucket[r.emoji] = bucket.get(r.emoji, 0) + 1
        if nik and r.user.nrp == nik:
            user_reaction_map[r.report_id] = r.emoji

    comments_count_map = dict(
        ReportComment.objects.filter(report_id__in=report_ids)
        .values('report_id').annotate(count=Count('id')).values_list('report_id', 'count')
    )

    for rep in reports:
        report_id = summaries.get(rep.get('encoded_key'))
        if report_id is None:
            continue
        c = counts_map.get(report_id, {})
        rep['likes_count'] = c.get('like', 0)
        rep['dislikes_count'] = c.get('dislike', 0)
        rep['loves_count'] = c.get('love', 0)
        rep['comments_count'] = comments_count_map.get(report_id, 0)
        rep['user_reaction'] = user_reaction_map.get(report_id)

    return reports


@require_GET
def proxy_get_reports(request):
    nik = request.GET.get('nik', '')
    try:
        response = requests.get(
            f"{settings.WEIGHING_BASE_URL}/api/get-reports/",
            params={'nik': nik},
            timeout=10,
        )
    except requests.exceptions.RequestException:
        return HttpResponse(
            '{"status": "error", "message": "Gagal menghubungi server weighing"}',
            content_type='application/json', status=502,
        )

    try:
        data = response.json()
    except ValueError:
        return HttpResponse(
            response.content,
            content_type=response.headers.get('Content-Type', 'application/json'),
            status=response.status_code,
        )

    reports = data.get('reports', [])
    for report in reports:
        if report.get('pdf'):
            report['pdf'] = f"/api/generate_pdf_report/?encoded_key={report['encoded_key']}"

    _enrich_reports_with_social_data(reports, nik)

    return JsonResponse(data, status=response.status_code)


@require_GET
def proxy_generate_pdf_report(request):
    encoded_key = request.GET.get('encoded_key', '').strip()
    report_type = request.GET.get('type', '').strip().lower()

    is_fms = (
        report_type == 'fms'
        or encoded_key.startswith(('fms_', 'fuel_'))
        or 'fuel' in encoded_key.lower()
    )

    if is_fms:
        fms_base = getattr(settings, 'FMS_BASE_URL', 'http://localhost:8000').rstrip('/')
        target_url = f"{fms_base}/api/fuel-report/generate_pdf_report/"
        backend_name = "FMS backend"
    else:
        weighing_base = getattr(settings, 'WEIGHING_BASE_URL', 'http://localhost:8000').rstrip('/')
        target_url = f"{weighing_base}/api/generate_pdf_report/"
        backend_name = "weighing"

    try:
        response = requests.get(
            target_url,
            params=request.GET,
            stream=True,
            timeout=30,
        )
    except requests.exceptions.RequestException:
        if not is_fms and hasattr(settings, 'FMS_BASE_URL'):
            try:
                fms_base = settings.FMS_BASE_URL.rstrip('/')
                fallback_url = f"{fms_base}/api/fuel-report/generate_pdf_report/"
                response = requests.get(fallback_url, params=request.GET, stream=True, timeout=20)
            except requests.exceptions.RequestException:
                return HttpResponse(f'Gagal menghubungi server {backend_name}', status=502)
        else:
            return HttpResponse(f'Gagal menghubungi server {backend_name}', status=502)

    if response.status_code >= 400:
        return HttpResponse(
            response.content,
            content_type=response.headers.get('Content-Type', 'text/plain'),
            status=response.status_code,
        )

    proxied = StreamingHttpResponse(
        response.iter_content(chunk_size=8192),
        content_type=response.headers.get('Content-Type', 'application/pdf'),
        status=response.status_code,
    )
    if 'Content-Disposition' in response.headers:
        proxied['Content-Disposition'] = response.headers['Content-Disposition']
    if 'Content-Length' in response.headers:
        proxied['Content-Length'] = response.headers['Content-Length']

    return proxied


@csrf_exempt
def proxy_fuel_report(request, subpath=''):
    base_url = getattr(settings, 'FMS_BASE_URL', 'http://localhost:8000').rstrip('/')
    clean_subpath = subpath.strip('/')
    if clean_subpath:
        target_url = f"{base_url}/api/fuel-report/{clean_subpath}/"
    else:
        target_url = f"{base_url}/api/fuel-report/"

    headers = {}
    for key, value in request.headers.items():
        if key.lower() not in HOP_BY_HOP_HEADERS:
            headers[key] = value

    method = request.method.upper()
    kwargs = {
        'params': request.GET,
        'headers': headers,
        'timeout': 30,
    }

    if method in ('POST', 'PUT', 'PATCH'):
        content_type = request.content_type or ''
        if 'multipart/form-data' in content_type:
            files = []
            for field_name, file_list in request.FILES.lists():
                for f in file_list:
                    files.append((field_name, (f.name, f.read(), f.content_type)))
            kwargs['files'] = files
            kwargs['data'] = request.POST
            headers.pop('Content-Type', None)
            headers.pop('content-type', None)
        elif request.body:
            kwargs['data'] = request.body

    try:
        response = requests.request(method, target_url, **kwargs)
    except requests.exceptions.RequestException:
        return JsonResponse(
            {'status': 'error', 'message': 'Gagal menghubungi server FMS backend'},
            status=502,
        )

    if method == 'GET' and clean_subpath in ('feed', 'reports') and response.status_code == 200:
        try:
            data = response.json()
            reports = data.get('reports', [])
            nik = request.GET.get('nik', '')
            for rep in reports:
                enc_key = rep.get('encoded_key')
                if enc_key:
                    rep['pdf'] = f"/api/generate_pdf_report/?encoded_key={enc_key}&type=fms"
                    rep['pdf_url'] = f"/api/generate_pdf_report/?encoded_key={enc_key}&type=fms"
                    # Pastikan DailyReportSummary tersinkronisasi di DB untuk laporan bahan bakar ini
                    from datetime import datetime
                    rep_date_str = rep.get('report_date')
                    rep_date = None
                    if rep_date_str:
                        try:
                            rep_date = datetime.strptime(rep_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            pass
                    if not rep_date:
                        import re
                        m = re.search(r'(\d{4})(\d{2})(\d{2})', enc_key)
                        if m:
                            try:
                                rep_date = datetime.strptime(m.group(0), '%Y%m%d').date()
                            except ValueError:
                                pass
                    if rep_date:
                        DailyReportSummary.objects.get_or_create(
                            encoded_key=enc_key,
                            defaults={
                                'report_date': rep_date,
                                'shift': rep.get('shift', 'All Shift'),
                                'report_type': 'fuel',
                                'title': 'Daily Fuel Activity Report',
                            }
                        )
            _enrich_reports_with_social_data(reports, nik)
            return JsonResponse(data, status=response.status_code)
        except Exception:
            pass

    proxied = HttpResponse(
        response.content,
        content_type=response.headers.get('Content-Type', 'application/json'),
        status=response.status_code,
    )
    if 'Content-Disposition' in response.headers:
        proxied['Content-Disposition'] = response.headers['Content-Disposition']
    return proxied
