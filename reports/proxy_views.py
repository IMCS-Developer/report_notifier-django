import requests
from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from reports.models import DailyReportSummary, ReportReaction, ReportComment


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
    encoded_key = request.GET.get('encoded_key', '')
    try:
        response = requests.get(
            f"{settings.WEIGHING_BASE_URL}/api/generate_pdf_report/",
            params={'encoded_key': encoded_key},
            timeout=20,
        )
    except requests.exceptions.RequestException:
        return HttpResponse('Gagal menghubungi server weighing', status=502)

    proxied = HttpResponse(
        response.content,
        content_type=response.headers.get('Content-Type', 'application/pdf'),
        status=response.status_code,
    )
    if 'Content-Disposition' in response.headers:
        proxied['Content-Disposition'] = response.headers['Content-Disposition']
    return proxied
