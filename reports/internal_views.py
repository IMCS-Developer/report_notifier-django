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

    report_type = data.get('report_type', 'coal')
    report_date = data.get('report_date')
    shift = data.get('shift')
    today_rom = data.get('today_rom')
    today_jetty = data.get('today_jetty')
    today_rom_ritase = data.get('today_rom_ritase')
    today_jetty_ritase = data.get('today_jetty_ritase')
    mtd_rom = data.get('mtd_rom')
    mtd_jetty = data.get('mtd_jetty')
    last_transaction = data.get('last_transaction')
    delivery_shift = data.get('delivery_shift')
    title_param = data.get('title')
    notif_text = data.get('notif_text')
    author_nrp = data.get('author_nrp')

    if not report_date or not shift:
        return JsonResponse({'error': 'report_date dan shift wajib diisi'}, status=400)

    if report_type == 'coal' and (today_rom is None or today_jetty is None):
        return JsonResponse({'error': 'report_date, shift, today_rom, today_jetty wajib diisi untuk coal'}, status=400)

    try:
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': "report_date harus berformat 'YYYY-MM-DD'"}, status=400)

    defaults_data = {}
    if delivery_shift:
        defaults_data['delivery_shift'] = delivery_shift
    if data.get('encoded_key'):
        defaults_data['encoded_key'] = data.get('encoded_key')

    report, created = DailyReportSummary.objects.get_or_create(
        report_date=report_date,
        shift=shift,
        report_type=report_type,
        defaults=defaults_data,
    )

    fields_to_update = []
    if not report.delivery_shift and delivery_shift:
        report.delivery_shift = delivery_shift
        fields_to_update.append('delivery_shift')

    default_title = "Daily Fuel Activity Report" if report_type == 'fuel' else "Daily Coal Activity Report"
    target_title = title_param or report.title or default_title
    if report.title != target_title:
        report.title = target_title
        fields_to_update.append('title')

    if not report.timestamp:
        report.timestamp = timezone.now()
        fields_to_update.append('timestamp')

    if notif_text and report.notif_text != notif_text:
        report.notif_text = notif_text
        fields_to_update.append('notif_text')

    if author_nrp and not report.author:
        author_obj = MasterManpower.objects.filter(nrp=author_nrp).first()
        if author_obj:
            report.author = author_obj
            fields_to_update.append('author')

    if today_rom is not None and today_jetty is not None:
        rounded_today_rom = round(float(today_rom), 2)
        rounded_today_jetty = round(float(today_jetty), 2)
        if report.today_rom != rounded_today_rom or report.today_jetty != rounded_today_jetty:
            report.today_rom = rounded_today_rom
            report.today_jetty = rounded_today_jetty
            fields_to_update.extend(['today_rom', 'today_jetty'])

    if fields_to_update:
        fields_to_update.append('updated_at')
        report.save(update_fields=list(set(fields_to_update)))

    channel_layer = get_channel_layer()
    if channel_layer:
        user_display = "System Auto"
        if report.author and report.author.nama:
            user_display = report.author.nama
        elif author_nrp:
            user_display = author_nrp

        async_to_sync(channel_layer.group_send)(
            "reports_feed",
            {
                "type": "report_update",
                "message": {
                    "type": report_type,
                    "encoded_key": report.encoded_key,
                    "report_date": report.report_date.strftime('%Y-%m-%d'),
                    "shift": report.shift,
                    "delivery_shift": report.delivery_shift,
                    "today_rom": report.today_rom,
                    "today_jetty": report.today_jetty,
                    "today_rom_ritase": today_rom_ritase,
                    "today_jetty_ritase": today_jetty_ritase,
                    "mtd_rom": mtd_rom,
                    "mtd_jetty": mtd_jetty,
                    "last_transaction": last_transaction,
                    "total_volume": data.get('total_volume'),
                    "total_transactions": data.get('total_transactions'),
                    "verified_transactions": data.get('verified_transactions'),
                    "title": report.title,
                    "user": user_display,
                    "user_photo": None,
                    "sender_nik": author_nrp,
                    "created": created,
                },
            },
        )

    return JsonResponse({'success': True, 'created': created, 'id': report.id, 'encoded_key': report.encoded_key})


@require_GET
@require_internal_token
def list_active_fcm_devices(request):
    tokens = list(
        FCMDevice.objects.filter(active=True).values_list('registration_id', flat=True)
    )
    return JsonResponse({'tokens': tokens, 'count': len(tokens)})
