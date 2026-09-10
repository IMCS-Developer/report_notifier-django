import hmac
import json
import logging
from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from reports.models import DailyReportSummary, FCMDevice, MasterManpower

logger = logging.getLogger(__name__)


def require_internal_token(view_func):
    def wrapper(request, *args, **kwargs):
        token = request.headers.get('X-Internal-Token', '')
        expected = getattr(settings, 'INTERNAL_API_TOKEN', None)
        if not expected or not hmac.compare_digest(token, expected):
            return JsonResponse({'error': 'unauthorized'}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapper


@csrf_exempt
@require_POST
@require_internal_token
def upsert_daily_report_summary(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON tidak valid'}, status=400)

    report_date = data.get('report_date')
    shift = data.get('shift')
    today_rom = data.get('today_rom')
    today_jetty = data.get('today_jetty')
    delivery_shift = data.get('delivery_shift')
    author_nrp = data.get('author_nrp')

    if not report_date or not shift or today_rom is None or today_jetty is None:
        return JsonResponse({'error': 'report_date, shift, today_rom, today_jetty wajib diisi'}, status=400)

    try:
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': "report_date harus berformat 'YYYY-MM-DD'"}, status=400)

    author_to_set = None
    if author_nrp:
        author_to_set = MasterManpower.objects.filter(nrp=author_nrp).first()
        if not author_to_set:
            logger.warning(f"upsert_daily_report_summary: MasterManpower dengan nrp={author_nrp} tidak ditemukan.")

    defaults_data = {}
    if author_to_set:
        defaults_data['author'] = author_to_set
    if delivery_shift:
        defaults_data['delivery_shift'] = delivery_shift

    report, created = DailyReportSummary.objects.get_or_create(
        report_date=report_date,
        shift=shift,
        defaults=defaults_data,
    )

    fields_to_update = []
    if not report.author and author_to_set:
        report.author = author_to_set
        fields_to_update.append('author')
    if not report.delivery_shift and delivery_shift:
        report.delivery_shift = delivery_shift
        fields_to_update.append('delivery_shift')
    if not report.title:
        report.title = "Daily Coal Activity Report"
        fields_to_update.append('title')
    if not report.timestamp:
        report.timestamp = timezone.now()
        fields_to_update.append('timestamp')

    if fields_to_update:
        fields_to_update.append('updated_at')
        report.save(update_fields=fields_to_update)

    rounded_today_rom = round(float(today_rom), 2)
    rounded_today_jetty = round(float(today_jetty), 2)
    if report.today_rom != rounded_today_rom or report.today_jetty != rounded_today_jetty:
        report.today_rom = rounded_today_rom
        report.today_jetty = rounded_today_jetty
        report.save(update_fields=['today_rom', 'today_jetty', 'updated_at'])

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "reports_feed",
        {
            "type": "report_update",
            "message": {
                "encoded_key": report.encoded_key,
                "report_date": report.report_date.strftime('%Y-%m-%d'),
                "shift": report.shift,
                "delivery_shift": report.delivery_shift,
                "today_rom": report.today_rom,
                "today_jetty": report.today_jetty,
                "title": report.title,
                "created": created,
            },
        },
    )

    return JsonResponse({'success': True, 'created': created, 'id': report.id})


@require_GET
@require_internal_token
def list_active_fcm_devices(request):
    tokens = list(
        FCMDevice.objects.filter(active=True).values_list('registration_id', flat=True)
    )
    return JsonResponse({'tokens': tokens, 'count': len(tokens)})
