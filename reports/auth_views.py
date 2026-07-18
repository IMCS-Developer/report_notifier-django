import json

from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token


@csrf_exempt
@require_POST
def login_api(request):
    """
    Login untuk app Flutter, berbasis NRP + password.
    NRP diresolve lewat NRPAuthBackend (reports.auth_backends) ke MasterManpower.
    Mengembalikan DRF auth token, bukan session cookie.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON tidak valid'}, status=400)

    nrp = data.get('nrp')
    password = data.get('password')

    if not nrp or not password:
        return JsonResponse({'error': 'NRP dan password wajib diisi'}, status=400)

    user = authenticate(request, username=nrp, password=password)
    if user is None:
        return JsonResponse({'error': 'NRP atau password salah'}, status=401)

    token, _ = Token.objects.get_or_create(user=user)
    return JsonResponse({'token': token.key})
