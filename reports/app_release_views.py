"""
API view exposing the latest active mobile app release.

Provides a single GET endpoint used by the Flutter client to check for
available app updates (version, APK download URL, changelog, checksum).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from reports.models import AppRelease


@require_GET
def app_version(request):
    release = AppRelease.objects.filter(is_active=True).order_by('-build_number').first()
    if not release or not release.apk_file:
        return JsonResponse({}, status=204)

    return JsonResponse({
        'latest_version': release.version,
        'latest_build': release.build_number,
        'apk_url': request.build_absolute_uri(release.apk_file.url),
        'changelog': release.changelog,
        'mandatory': release.mandatory,
        'sha256': release.sha256,
        'size': release.size,
    })
