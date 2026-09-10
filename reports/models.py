import hashlib
import json
import logging
import os
from datetime import datetime

import pytz
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


class MasterManpower(models.Model):
    id = models.AutoField(primary_key=True)
    no = models.CharField(db_column='no', max_length=255, blank=True, null=True)
    nrp = models.CharField(db_column='nrp', max_length=255, blank=True, null=True, unique=True)
    nama = models.CharField(db_column='nama', max_length=255, blank=True, null=True)
    departement = models.CharField(db_column='departement', max_length=255, blank=True, null=True)
    jabatan = models.CharField(db_column='jabatan', max_length=255, blank=True, null=True)
    jabatan_2 = models.CharField(db_column='jabatan_2', max_length=255, blank=True, null=True)
    jenis_kelamin = models.CharField(db_column='jenis_kelamin', max_length=255, blank=True, null=True)
    poh = models.CharField(db_column='poh', max_length=255, blank=True, null=True)
    kompetensi = models.CharField(db_column='kompetensi', max_length=255, blank=True, null=True)
    tgl_lahir = models.DateTimeField(db_column='tgl_lahir', blank=True, null=True)
    umur = models.FloatField(db_column='umur', blank=True, null=True)
    pendidikan = models.CharField(db_column='pendidikan', max_length=255, blank=True, null=True)
    mulai_bekerja = models.DateTimeField(db_column='mulai_bekerja', blank=True, null=True)
    doh_as_opt = models.DateTimeField(db_column='doh_as_opt', blank=True, null=True)
    status_karyawan = models.CharField(db_column='status_karyawan', max_length=255, blank=True, null=True)
    ket = models.CharField(db_column='ket', max_length=255, blank=True, null=True)
    keterangan = models.CharField(db_column='keterangan', max_length=255, blank=True, null=True)
    tgl_turnover = models.DateTimeField(db_column='tgl_turnover', blank=True, null=True)
    levels = models.CharField(db_column='levels', max_length=255, blank=True, null=True)
    opt_cn = models.CharField(db_column='opt_cn', max_length=255, blank=True, null=True)
    opt_group = models.CharField(db_column='opt_group', max_length=255, blank=True, null=True)
    email = models.CharField(db_column='email', max_length=255, blank=True, null=True)
    pas_foto = models.ImageField(upload_to='pas_foto/', blank=True, null=True)
    is_active = models.BooleanField(default=True, null=True)
    kontrak_terakhir = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user_account = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='manpower_profile')

    class Meta:
        verbose_name = "Master Manpower"
        verbose_name_plural = "Master Manpower"


class FCMDevice(models.Model):
    registration_id = models.CharField(max_length=255, unique=True, db_index=True)
    active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)

    user_nik = models.ForeignKey(
        MasterManpower,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field='nrp',
        related_name='fcm_devices'
    )

    user_name = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        verbose_name = "FCM Device"
        verbose_name_plural = "FCM Devices"

    def __str__(self):
        # Mengembalikan representasi perangkat yang dapat dibaca
        return f"Device {self.registration_id[:20]}... (Active: {self.active})"


class DailyReportSummary(models.Model):
    SHIFT_CHOICES = [
        ('Day Shift', 'Day Shift'),
        ('Night Shift', 'Night Shift'),
        ('All_Shift', 'All Shift'),
    ]

    report_date = models.DateField(db_index=True)
    shift = models.CharField(max_length=15, choices=SHIFT_CHOICES, db_index=True)
    delivery_shift = models.CharField(max_length=15, choices=SHIFT_CHOICES, null=True, blank=True,
                                      help_text="Shift saat laporan ini 'dikirim' atau saat transaksi yang memicu pembuatan laporan dicatat.")
    title = models.CharField(max_length=255, blank=True, null=True)
    notif_text = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now, null=True, blank=True)

    author = models.ForeignKey(
        'MasterManpower',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field='nrp',
        related_name='daily_reports_authored'
    )

    today_rom = models.FloatField(default=0.0)
    today_jetty = models.FloatField(default=0.0)

    pdf_file = models.FileField(upload_to='report_pdf/', blank=True, null=True)
    encoded_key = models.CharField(max_length=100, unique=True, editable=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('report_date', 'shift')
        verbose_name = "Daily Report Summary"
        verbose_name_plural = "Daily Report Summaries"
        ordering = ['-report_date', 'shift']

    def save(self, *args, **kwargs):
        # Generate encoded_key saat menyimpan atau jika belum ada
        if not self.encoded_key:
            date_part = self.report_date.strftime('%Y%m%d')
            shift_part = self.shift.replace(' ', '_')
            self.encoded_key = f"{date_part}_{shift_part}"

        if not self.delivery_shift:
            jakarta_tz = pytz.timezone(settings.TIME_ZONE)
            current_local_time = datetime.now(jakarta_tz)

            hour = current_local_time.hour
            if 7 <= hour < 19:
                self.delivery_shift = 'Day Shift'
            else:
                self.delivery_shift = 'Night Shift'

        super().save(*args, **kwargs)

    def get_pdf_filename(self):
        """Mengembalikan nama file PDF yang diharapkan."""
        return f"Daily_Coal_Activity_Report_{self.encoded_key}.pdf"

    def get_pdf_filepath(self):
        """Mengembalikan path lengkap ke file PDF di disk."""
        if self.pdf_file and self.pdf_file.name:
            return self.pdf_file.path
        return os.path.join(settings.MEDIA_ROOT, 'report_pdf', self.get_pdf_filename())

    def get_pdf_url(self):
        """Mengembalikan URL untuk mengunduh PDF."""
        if self.pdf_file and self.pdf_file.name:
            return self.pdf_file.url
        return f"{settings.MEDIA_URL}report_pdf/{self.get_pdf_filename()}"

    def __str__(self):
        return f"Daily Report: {self.report_date} - {self.shift} (Delivered: {self.delivery_shift or 'N/A'})"


class ReportComment(models.Model):
    report = models.ForeignKey(DailyReportSummary, on_delete=models.CASCADE, related_name='comments', null=True,
                               blank=True)
    user = models.ForeignKey('MasterManpower', on_delete=models.CASCADE, to_field='nrp', related_name='comments_made')
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Report Comment"
        verbose_name_plural = "Report Comments"

    def tagged_users(self):
        import re
        return re.findall(r"@([a-zA-Z0-9_]+)", self.message)

    def __str__(self):
        return f"Comment on {self.report.encoded_key if self.report else 'N/A'} by {self.user.nama if self.user and hasattr(self.user, 'nama') else self.user.nrp if self.user else 'Anon'}"


class ReportReaction(models.Model):
    report = models.ForeignKey(DailyReportSummary, on_delete=models.CASCADE, related_name='reactions', null=True,
                               blank=True)
    comment = models.ForeignKey(ReportComment, on_delete=models.CASCADE, related_name='reactions', null=True,
                                blank=True)

    user = models.ForeignKey(
        MasterManpower,
        on_delete=models.CASCADE,
        to_field='nrp',
        related_name='reactions_given'
    )
    emoji = models.CharField(max_length=10)  # 'like', 'love', 'dislike', 'haha', etc.
    reacted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(report__isnull=False, comment__isnull=True) | models.Q(report__isnull=True,
                                                                                      comment__isnull=False),
                name='either_report_or_comment_not_null',
            ),
            models.UniqueConstraint(
                fields=['report', 'user'],
                condition=models.Q(comment__isnull=True),
                name='unique_report_reaction'
            ),
            models.UniqueConstraint(
                fields=['comment', 'user'],
                condition=models.Q(report__isnull=True),
                name='unique_comment_reaction'
            )
        ]

        verbose_name = "Reaction"
        verbose_name_plural = "Reactions"

    def __str__(self):
        target = ""
        if self.report and not self.comment:
            target = f"on report {self.report.encoded_key}"
        elif self.comment:
            target = f"on comment {self.comment.id}"
        return f"Reaction '{self.emoji}' {target} by {self.user.nama if self.user and hasattr(self.user, 'nama') else self.user.nrp if self.user else 'Anon'}"


class AppRelease(models.Model):
    metadata_file = models.FileField(
        upload_to='apk/metadata/',
        help_text="Gradle output-metadata.json; version and build_number are read from it",
    )
    apk_file = models.FileField(upload_to='apk/')
    version = models.CharField(max_length=20, blank=True, default='', help_text="Auto-filled from output-metadata.json versionName")
    build_number = models.PositiveIntegerField(null=True, blank=True, help_text="Auto-filled from output-metadata.json versionCode")
    changelog = models.TextField(blank=True, default='')
    mandatory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Newest active release is the one served to clients")
    sha256 = models.CharField(max_length=64, blank=True, default='', help_text="Hex SHA-256 of apk_file, computed on save")
    size = models.PositiveBigIntegerField(default=0, help_text="apk_file size in bytes, computed on save")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "App Release"
        verbose_name_plural = "App Releases"
        ordering = ['-build_number']

    def __str__(self):
        return f"v{self.version or '?'}+{self.build_number or '?'}"

    def save(self, *args, **kwargs):
        if self.metadata_file:
            self._apply_output_metadata()
        if self.apk_file:
            self._apply_apk_checksum()
        super().save(*args, **kwargs)

    def _apply_output_metadata(self):
        self.metadata_file.open('rb')
        try:
            raw = self.metadata_file.read()
        finally:
            self.metadata_file.seek(0)

        try:
            document = json.loads(raw)
            element = document['elements'][0]
            version_name = str(element['versionName'])
            version_code = int(element['versionCode'])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ValidationError(f"Invalid output-metadata.json: {exc}")

        self.version = version_name
        self.build_number = version_code

        expected_output = element.get('outputFile')
        if expected_output and self.apk_file:
            uploaded_name = os.path.basename(self.apk_file.name)
            if uploaded_name != expected_output:
                logger.warning(
                    "AppRelease APK name '%s' does not match output-metadata.json outputFile '%s'",
                    uploaded_name,
                    expected_output,
                )

    def _apply_apk_checksum(self):
        digest = hashlib.sha256()
        total = 0
        self.apk_file.open('rb')
        try:
            for chunk in self.apk_file.chunks():
                digest.update(chunk)
                total += len(chunk)
        finally:
            self.apk_file.seek(0)
        self.sha256 = digest.hexdigest()
        self.size = total


@receiver(post_save, sender=AppRelease)
def notify_devices_on_new_release(sender, instance, created, **kwargs):
    if not created or not instance.is_active:
        return

    from reports.fcm_client_v1 import send_fcm_notification_v1

    tokens = list(
        FCMDevice.objects.filter(active=True).values_list('registration_id', flat=True)
    )
    if not tokens:
        return

    send_fcm_notification_v1(
        tokens,
        title='App update available',
        data={'type': 'app_update', 'version': instance.version},
    )
