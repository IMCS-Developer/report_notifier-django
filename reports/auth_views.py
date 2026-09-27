"""
Authentication API views for NRP/PIN-based login.

Provides endpoints to log in with an NRP and PIN (returning a DRF auth
token) and to set a PIN for the first time, linking a MasterManpower
record to a Django User as needed.
"""

import json

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token

from reports.models import MasterManpower

PIN_LENGTH = 6


def _get_active_manpower(nrp):
    return MasterManpower.objects.filter(nrp__iexact=nrp, is_active=True).first()


def _linked_user(manpower):
    user = User(username=manpower.nrp)
    user.set_unusable_password()
    user.save()
    manpower.user_account = user
    manpower.save(update_fields=['user_account'])
    return user


def _has_pin(user):
    return bool(user and user.password and user.has_usable_password())


def _auth_payload(user, manpower):
    token, _ = Token.objects.get_or_create(user=user)
    return {'token': token.key, 'user_name': manpower.nama or manpower.nrp}


@csrf_exempt
@require_POST
def login_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON tidak valid'}, status=400)

    nrp = (data.get('nrp') or '').strip()
    pin = data.get('pin') or data.get('password') or ''

    if not nrp or not pin:
        return JsonResponse({'error': 'NRP dan PIN wajib diisi'}, status=400)

    manpower = _get_active_manpower(nrp)
    if manpower is None:
        return JsonResponse({'error': 'NRP tidak terdaftar'}, status=404)

    if not _has_pin(manpower.user_account):
        return JsonResponse({'error': 'pin_not_set'}, status=409)

    authenticated = authenticate(request, username=manpower.nrp, password=pin)
    if authenticated is None:
        return JsonResponse({'error': 'PIN salah'}, status=401)

    return JsonResponse(_auth_payload(authenticated, manpower))


@csrf_exempt
@require_POST
def set_pin(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON tidak valid'}, status=400)

    nrp = (data.get('nrp') or '').strip()
    pin = data.get('pin') or ''

    if not nrp or not pin:
        return JsonResponse({'error': 'NRP dan PIN wajib diisi'}, status=400)

    if len(pin) != PIN_LENGTH or not pin.isdigit():
        return JsonResponse({'error': f'PIN harus {PIN_LENGTH} digit angka'},
                            status=400)

    manpower = _get_active_manpower(nrp)
    if manpower is None:
        return JsonResponse({'error': 'NRP tidak terdaftar'}, status=404)

    user = _linked_user(manpower)
    if _has_pin(user):
        return JsonResponse({'error': 'PIN sudah dibuat'}, status=403)

    user.set_password(pin)
    user.is_active = True
    user.save(update_fields=['password', 'is_active'])

    return JsonResponse(_auth_payload(user, manpower))
