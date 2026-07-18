import logging

logger = logging.getLogger(__name__)

from asgiref.sync import sync_to_async

from reports.models import ReportReaction


# --- FUNGSI PEMBANTU: Untuk mendapatkan URL foto profil pengguna ---
@sync_to_async  # Menggunakan sync_to_async karena ini operasi DB
def _get_user_photo_url_async(user_obj, request):  # Menerima user_obj dan request
    """
    Fungsi pembantu asinkron untuk mendapatkan URL foto profil pengguna.
    Menerima objek MasterManpower dan objek request.
    """
    if user_obj and hasattr(user_obj, 'pas_foto') and user_obj.pas_foto:
        try:
            # Menggunakan request.build_absolute_uri untuk URL lengkap dan aman
            return request.build_absolute_uri(user_obj.pas_foto.url)
        except ValueError:  # Tangani kasus di mana file tidak disetel atau URL tidak valid
            # logger.warning(f"Warning: Photo file for user {user_obj.nrp} does not have a valid URL.")
            return None
        except Exception as e:
            # logger.error(f"ERROR: Could not get photo URL for user {user_obj.nrp}: {e}")
            print(f"ERROR: Tidak dapat mengambil URL foto untuk pengguna {user_obj.nrp}: {e}")  # Gunakan print jika logger belum diatur
            return None
    return None


# NEW HELPER: Untuk mendapatkan jumlah reaksi dan reaksi pengguna untuk entitas apa pun (laporan atau komentar)
@sync_to_async
def _get_entity_reaction_data_sync(entity_obj, user_nik=None, is_report=True):
    """
    Mengambil jumlah reaksi (like, dislike, love) dan reaksi pengguna saat ini
    untuk objek laporan atau komentar tertentu.

    Args:
        entity_obj: Instance DailyReportSummary atau ReportComment.
        user_nik (str, optional): NIK pengguna yang sedang login untuk memeriksa reaksinya.
        is_report (bool): True jika entity_obj adalah DailyReportSummary, False jika ReportComment.
    """
    reaction_filter_kwargs = {}
    if is_report:
        reaction_filter_kwargs['report'] = entity_obj
        reaction_filter_kwargs['comment__isnull'] = True  # Pastikan hanya reaksi laporan
    else:
        reaction_filter_kwargs['comment'] = entity_obj
        reaction_filter_kwargs['report__isnull'] = True  # Pastikan hanya reaksi komentar

    likes_count = ReportReaction.objects.filter(emoji='like', **reaction_filter_kwargs).count()
    dislikes_count = ReportReaction.objects.filter(emoji='dislike', **reaction_filter_kwargs).count()
    loves_count = ReportReaction.objects.filter(emoji='love', **reaction_filter_kwargs).count()

    current_user_reaction_emoji = None
    if user_nik:
        try:
            # Pastikan user__nrp digunakan untuk filter NIK
            user_reaction_obj = ReportReaction.objects.filter(user__nrp=user_nik, **reaction_filter_kwargs).first()
            if user_reaction_obj:
                current_user_reaction_emoji = user_reaction_obj.emoji
        except Exception as e:
            logger.warning(f"Gagal mendapatkan reaksi pengguna untuk NIK {user_nik} pada entitas {entity_obj.id}: {e}")

    # Khusus untuk laporan, tambahkan comments_count
    comments_count = 0
    if is_report:
        comments_count = entity_obj.comments.count()

    return {
        "likes_count": likes_count,
        "dislikes_count": dislikes_count,
        "loves_count": loves_count,
        "comments_count": comments_count,  # Akan 0 jika is_report=False
        "user_reaction": current_user_reaction_emoji
    }
