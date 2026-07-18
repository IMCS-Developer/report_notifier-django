from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    FCMDevice,
    MasterManpower,
    DailyReportSummary,
    ReportComment,
    ReportReaction
)


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ('registration_id_short', 'user_nik_display', 'user_name', 'active', 'date_created')
    list_filter = ('active', 'date_created')
    search_fields = ('registration_id', 'user_nik__nrp', 'user_name',)  # Gunakan 'user_nik__nrp' untuk pencarian via relasi
    readonly_fields = ('date_created',)

    def registration_id_short(self, obj):
        return f"{obj.registration_id[:30]}..."

    registration_id_short.short_description = "Registration ID"

    def user_nik_display(self, obj):  # Metode kustom untuk user_nik (ForeignKey)
        return obj.user_nik.nrp if obj.user_nik else 'N/A'

    user_nik_display.short_description = "User NRP"


@admin.register(MasterManpower)
class MasterManpowerAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nrp', 'departement', 'jabatan', 'pas_foto_display', 'is_active')
    search_fields = ('nama', 'nrp', 'jabatan',)
    ordering = ('nama',)

    # Metode kustom untuk menampilkan foto profil di list_display
    def pas_foto_display(self, obj):
        if obj.pas_foto:
            return format_html('<img src="{}" style="max-width: 50px; max-height: 50px; border-radius: 50%;" />', obj.pas_foto.url)
        return "No Photo"

    pas_foto_display.short_description = "Pas Foto"


@admin.register(DailyReportSummary)
class DailyReportSummaryAdmin(admin.ModelAdmin):
    list_display = ('report_date', 'shift', 'delivery_shift', 'today_rom', 'today_jetty', 'author_nrp', 'created_at', 'updated_at', 'encoded_key',
                    'pdf_file_link')
    list_filter = ('shift', 'report_date', 'author')
    search_fields = ('encoded_key', 'author__nrp', 'author__nama')
    ordering = ('-report_date', 'shift')
    readonly_fields = ('encoded_key', 'created_at', 'updated_at', 'today_rom', 'today_jetty', 'pdf_file_display')
    raw_id_fields = ('author',)

    def author_nrp(self, obj):
        return obj.author.nrp if obj.author else 'N/A'

    author_nrp.short_description = "Author (NRP)"

    def pdf_file_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">View PDF</a>', obj.pdf_file.url)
        return "No PDF"

    pdf_file_link.short_description = "PDF"

    def pdf_file_display(self, obj):  # Untuk menampilkan link PDF di readonly_fields
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.pdf_file.url, obj.pdf_file.name.split('/')[-1])
        return "No PDF File"

    pdf_file_display.short_description = "PDF File"


@admin.register(ReportComment)
class ReportCommentAdmin(admin.ModelAdmin):
    list_display = ('report_link', 'user_nik_display', 'message_short', 'timestamp', 'parent_comment_link')
    search_fields = ('report__encoded_key', 'user__nrp', 'user__nama', 'message')
    ordering = ('-timestamp',)
    list_filter = ('timestamp', 'report__shift', 'user')
    raw_id_fields = ('report', 'user', 'parent_comment')

    def user_nik_display(self, obj):
        return obj.user.nrp if obj.user else 'N/A'

    user_nik_display.short_description = "User NRP"

    def user_name_display(self, obj):
        return obj.user.nama if obj.user and hasattr(obj.user, 'nama') else 'N/A'

    user_name_display.short_description = "User Name"

    def report_link(self, obj):
        if obj.report:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:%s_%s_change' % (obj.report._meta.app_label, obj.report._meta.model_name), args=[obj.report.pk]),
                               obj.report.encoded_key)
        return "N/A"

    report_link.short_description = "Report"

    def parent_comment_link(self, obj):
        if obj.parent_comment:
            return format_html('<a href="{}">#{}</a>',
                               reverse('admin:%s_%s_change' % (obj.parent_comment._meta.app_label, obj.parent_comment._meta.model_name),
                                       args=[obj.parent_comment.pk]),
                               obj.parent_comment.id)
        return "N/A"

    parent_comment_link.short_description = "Reply To"

    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message

    message_short.short_description = "Message"


@admin.register(ReportReaction)
class ReportReactionAdmin(admin.ModelAdmin):
    list_display = ('report_link', 'user_nik_display', 'emoji', 'reacted_at')
    search_fields = ('report__encoded_key', 'user__nrp', 'user__nama', 'emoji')
    ordering = ('-reacted_at',)
    list_filter = ('emoji', 'reacted_at', 'report__shift', 'user')
    raw_id_fields = ('report', 'user')

    def user_nik_display(self, obj):
        return obj.user.nrp if obj.user else 'N/A'

    user_nik_display.short_description = "User NRP"

    def user_name_display(self, obj):
        return obj.user.nama if obj.user and hasattr(obj.user, 'nama') else 'N/A'

    user_name_display.short_description = "User Name"

    def report_link(self, obj):
        if obj.report:
            return format_html('<a href="{}">{}</a>',
                               reverse('admin:%s_%s_change' % (obj.report._meta.app_label, obj.report._meta.model_name), args=[obj.report.pk]),
                               obj.report.encoded_key)
        return "N/A"

    report_link.short_description = "Report"
