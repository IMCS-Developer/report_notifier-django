import json
import logging

logger = logging.getLogger(__name__)

from django.http import JsonResponse
from django.utils import timezone
from django.db import models, transaction
from reports.decorators import csrf_exempt, require_GET, require_POST

from reports.models import MasterManpower, DailyReportSummary, ReportComment, ReportReaction
from reports.shared_helpers import _get_user_photo_url_async, _get_entity_reaction_data_sync

from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync, sync_to_async


@csrf_exempt
@require_GET
async def get_report_reaction_status(request):
    report_id = request.GET.get('report_id')
    user_nik = request.GET.get('nik')

    if not report_id or not user_nik:
        logger.warning(f"get_report_reaction_status: report_id ({report_id}) atau nik ({user_nik}) tidak lengkap")
        return JsonResponse({'status': 'error', 'message': 'report_id atau nik tidak lengkap'}, status=400)

    try:
        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_id)

        results = await _get_entity_reaction_data_sync(report_summary, user_nik=user_nik, is_report=True)

        return JsonResponse({
            'status': 'success',
            'report_id': report_id,
            'user_nik': user_nik,
            'user_reaction': results["user_reaction"],
            'likes_count': results["likes_count"],
            'dislikes_count': results["dislikes_count"],
            'loves_count': results["loves_count"],
            'comments_count': results["comments_count"],
        })

    except DailyReportSummary.DoesNotExist:
        logger.error(f"Laporan dengan encoded_key={report_id} tidak ditemukan.")
        return JsonResponse({'status': 'error', 'message': 'Laporan tidak ditemukan'}, status=404)
    except MasterManpower.DoesNotExist:  # Ini mungkin tidak akan terpukul jika user_nik opsional untuk _get_entity_reaction_data_sync
        logger.error(f"Pengguna dengan NIK={user_nik} tidak ditemukan (dalam get_report_reaction_status).")
        return JsonResponse({'status': 'error', 'message': 'Pengguna tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam get_report_reaction_status: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_GET
async def get_report_reaction_users(request):
    """
    Mengembalikan daftar pengguna yang memberikan reaksi tertentu pada laporan.
    """
    report_id = request.GET.get('report_id')
    reaction_type = request.GET.get('reaction_type')  # misalnya: 'love', 'like', 'dislike'

    if not report_id or not reaction_type:
        return JsonResponse({'status': 'error', 'message': 'report_id dan reaction_type wajib diisi'}, status=400)

    canonical_reaction_type = {
        'love': 'love', 'loved': 'love',
        'like': 'like', 'liked': 'like',
        'dislike': 'dislike', 'disliked': 'dislike',
    }.get(reaction_type.lower(), None)  # .lower() for case insensitivity

    if not canonical_reaction_type:
        return JsonResponse({'status': 'error', 'message': 'Tipe reaksi tidak valid'}, status=400)

    try:
        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_id)

        reactions_queryset = ReportReaction.objects.filter(
            report=report_summary,
            emoji=canonical_reaction_type,  # Use canonical type
            comment__isnull=True
        ).select_related('user')  # Prefetch info pengguna

        reacted_users_data = await database_sync_to_async(list)(reactions_queryset)

        users_list = []
        for reaction in reacted_users_data:
            user_obj = reaction.user
            user_name = user_obj.nama if user_obj.nama else user_obj.nrp
            user_photo_url = await _get_user_photo_url_async(user_obj, request)
            users_list.append({
                'user_nik': user_obj.nrp,
                'user_name': user_name,
                'user_photo_url': user_photo_url
            })

        return JsonResponse({'status': 'success', 'users': users_list})

    except DailyReportSummary.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Laporan tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam get_report_reaction_users: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_POST
async def post_comment(request):
    """
    Mengelola posting komentar atau balasan pada laporan.
    """
    logger.info(f"DEBUG post_comment: Raw request body: {request.body.decode('utf-8')}")
    try:
        data = json.loads(request.body)
        report_id = data.get('report_id')  # encoded_key laporan
        user_nik = data.get('user_nik')
        message = data.get('message')
        parent_comment_id = data.get('parent_comment_id')  # Untuk balasan

        logger.info(
            f"DEBUG post_comment: Parsed data - report_id: {report_id}, user_nik: {user_nik}, message: {message}, parent_comment_id: {parent_comment_id}")

        if not report_id or not user_nik or not message:
            logger.warning(
                f"post_comment: Data tidak lengkap. report_id: {report_id}, user_nik: {user_nik}, message: {message}")
            return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'}, status=400)

        # Dapatkan laporan dan pengguna dalam satu panggilan asinkron jika tidak ada parent_comment_id
        # Atau pisahkan jika diperlukan
        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_id)
        db_manpower_user = await sync_to_async(MasterManpower.objects.get)(nrp=user_nik)

        parent_comment = None
        if parent_comment_id:
            try:
                parent_comment = await sync_to_async(ReportComment.objects.get)(pk=parent_comment_id)
            except ReportComment.DoesNotExist:
                logger.error(f"post_comment: Komentar induk dengan ID={parent_comment_id} tidak ditemukan.")
                return JsonResponse({'status': 'error', 'message': 'Komentar induk tidak ditemukan'}, status=404)

        comment = await sync_to_async(ReportComment.objects.create)(
            report=report_summary,
            user=db_manpower_user,
            message=message,
            parent_comment=parent_comment,
            is_edited=False,  # NEW: Set default for new comments
            edited_at=None  # NEW: Set default for new comments
        )

        @sync_to_async
        def _get_comment_details_for_ws_sync(comment_obj, report_obj, request_obj):
            comment_user_name = comment_obj.user.nama if comment_obj.user.nama else comment_obj.user.nrp
            comment_user_photo_url = async_to_sync(_get_user_photo_url_async)(comment_obj.user,
                                                                              request_obj)  # Memanggil fungsi async di dalam sync

            total_comments_count = report_obj.comments.count()
            return total_comments_count, comment_user_name, comment_user_photo_url

        total_comments_count, comment_user_name, comment_user_photo = await _get_comment_details_for_ws_sync(comment,
                                                                                                             report_summary,
                                                                                                             request)

        channel_layer = await sync_to_async(get_channel_layer)()

        new_comment_data = {
            "id": comment.id,
            "report_id": report_id,
            "user": comment_user_name,
            "user_nik": comment.user.nrp,
            "user_photo": comment_user_photo,
            "message": comment.message,
            "timestamp": comment.timestamp.isoformat(),
            "parent_comment_id": comment.parent_comment.id if comment.parent_comment else None,
            "is_edited": False,
            "likes_count": 0,
            "dislikes_count": 0,
            "loves_count": 0,
            "user_reaction": None,
        }

        await channel_layer.group_send(
            "reports_feed",
            {
                "type": "report_comment_update",
                "message": {
                    "encoded_key": report_id,
                    "comments_count": total_comments_count,
                    "new_comment": new_comment_data
                }
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Komentar berhasil diposting',
            'comment_id': comment.id,
            'new_comment': new_comment_data,
        })

    except json.JSONDecodeError:
        logger.error(f"post_comment: JSON tidak valid: {request.body.decode('utf-8')}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'JSON tidak valid'}, status=400)
    except DailyReportSummary.DoesNotExist:
        logger.error(f"post_comment: Laporan dengan encoded_key={report_id} tidak ditemukan.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Laporan tidak ditemukan'}, status=404)
    except MasterManpower.DoesNotExist:
        logger.error(f"post_comment: Pengguna dengan NIK={user_nik} tidak ditemukan.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Pengguna tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam post_comment: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_POST
async def update_comment(request):
    """
    Memperbarui komentar yang ada.
    """
    logger.info(f"DEBUG update_comment: Raw request body: {request.body.decode('utf-8')}")
    try:
        data = json.loads(request.body)
        comment_id = data.get('comment_id')
        user_nik = data.get('nik')  # FIXED: Mengambil 'nik' dari request
        new_message = data.get('message')

        logger.info(
            f"DEBUG update_comment: Parsed data - comment_id: {comment_id}, user_nik: {user_nik}, new_message: {new_message}")

        if not comment_id or not user_nik or not new_message:
            logger.warning(
                f"update_comment: Data tidak lengkap. comment_id: {comment_id}, user_nik: {user_nik}, new_message: {new_message}")
            return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'}, status=400)

        comment_to_update = await sync_to_async(ReportComment.objects.select_related('report', 'user').get)(
            id=comment_id, user__nrp=user_nik
        )

        # Update fields
        comment_to_update.message = new_message
        comment_to_update.is_edited = True
        comment_to_update.edited_at = timezone.now()
        await sync_to_async(comment_to_update.save)()

        # Dapatkan jumlah terbaru untuk laporan induk
        report_summary = comment_to_update.report
        current_counts = await _get_entity_reaction_data_sync(report_summary,
                                                              is_report=True)  # Comments count is included here
        comment_reaction_data = await _get_entity_reaction_data_sync(comment_to_update, user_nik=user_nik,
                                                                     is_report=False)

        # Dapatkan channel_layer di dalam konteks asinkron
        channel_layer = await sync_to_async(get_channel_layer)()

        updated_comment_data = {
            "id": comment_to_update.id,
            "report_id": report_summary.encoded_key,
            "user": comment_to_update.user.nama if comment_to_update.user.nama else comment_to_update.user.nrp,
            "user_nik": comment_to_update.user.nrp,
            "user_photo": await _get_user_photo_url_async(comment_to_update.user, request),
            "message": comment_to_update.message,
            "timestamp": comment_to_update.timestamp.isoformat(),
            "parent_comment_id": comment_to_update.parent_comment.id if comment_to_update.parent_comment else None,
            "is_edited": comment_to_update.is_edited,
            "likes_count": comment_reaction_data['likes_count'],
            "dislikes_count": comment_reaction_data['dislikes_count'],
            "loves_count": comment_reaction_data['loves_count'],
            "user_reaction": comment_reaction_data['user_reaction'],
        }

        # Kirim update WebSocket untuk menandakan komentar berubah
        await channel_layer.group_send(
            "reports_feed",
            {
                "type": "report_comment_update",  # Gunakan kembali tipe ini
                "message": {
                    "encoded_key": report_summary.encoded_key,
                    "comments_count": current_counts['comments_count'],
                    "updated_comment": updated_comment_data
                }
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Komentar berhasil diperbarui',
            'comment_id': comment_to_update.id,
            'updated_comment': updated_comment_data,
        })

    except json.JSONDecodeError:
        logger.error(f"update_comment: JSON tidak valid: {request.body.decode('utf-8')}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'JSON tidak valid'}, status=400)
    except ReportComment.DoesNotExist:
        logger.error(f"update_comment: Komentar {comment_id} tidak ditemukan atau bukan milik pengguna {user_nik}.",
                     exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Tidak ditemukan atau bukan pemilik komentar'}, status=403)
    except MasterManpower.DoesNotExist:
        logger.error(f"update_comment: Pengguna dengan NIK={user_nik} tidak ditemukan.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Pengguna tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam update_comment: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_GET
async def get_comments(request):
    """
    Mengembalikan daftar komentar untuk laporan tertentu, termasuk balasan,
    dengan menyertakan data reaksi dan status edit.
    """
    report_id = request.GET.get('report_id')
    user_nik = request.GET.get('nik')  # NIK dari pengguna yang request, untuk personalisasi reaksi

    if not report_id:
        logger.warning(f"get_comments: report_id ({report_id}) tidak lengkap.")
        return JsonResponse({'status': 'error', 'message': 'report_id tidak lengkap'}, status=400)

    try:
        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_id)

        # Mengambil komentar utama (parent_comment is null) dan prefetch balasan serta pengguna
        comments_queryset = ReportComment.objects.filter(
            report=report_summary,
            parent_comment__isnull=True
        ).select_related('user').prefetch_related(
            models.Prefetch('replies', queryset=ReportComment.objects.select_related('user').order_by('timestamp')),
            # Urutkan balasan dari yang terlama ke terbaru
            # NEW: Prefetch reactions for comments and their replies
            models.Prefetch('reactions',
                            queryset=ReportReaction.objects.select_related('user').filter(report__isnull=True)),
            models.Prefetch('replies__reactions',
                            queryset=ReportReaction.objects.select_related('user').filter(report__isnull=True))
        ).order_by('-timestamp')  # Urutkan komentar utama: terbaru di atas

        comments = await database_sync_to_async(list)(comments_queryset)  # Sudah benar

        comments_data = []
        for comment in comments:
            comment_user_name = comment.user.nama if comment.user.nama else comment.user.nrp
            comment_user_photo = await _get_user_photo_url_async(comment.user, request)

            # NEW: Dapatkan data reaksi untuk komentar utama
            comment_reaction_data = await _get_entity_reaction_data_sync(comment, user_nik=user_nik, is_report=False)

            replies_data = []
            for reply in comment.replies.all():
                reply_user_name = reply.user.nama if reply.user.nama else reply.user.nrp
                reply_user_photo = await _get_user_photo_url_async(reply.user, request)

                # NEW: Dapatkan data reaksi untuk setiap balasan
                reply_reaction_data = await _get_entity_reaction_data_sync(reply, user_nik=user_nik, is_report=False)

                replies_data.append({
                    "id": reply.id,
                    "user": reply_user_name,
                    "user_nik": reply.user.nrp,
                    "user_photo": reply_user_photo,
                    "message": reply.message,
                    "timestamp": reply.timestamp.isoformat(),
                    "parent_comment_id": reply.parent_comment.id if reply.parent_comment else None,
                    "is_edited": reply.is_edited,  # BARU
                    "likes_count": reply_reaction_data['likes_count'],  # BARU
                    "dislikes_count": reply_reaction_data['dislikes_count'],  # BARU
                    "loves_count": reply_reaction_data['loves_count'],  # BARU
                    "user_reaction": reply_reaction_data['user_reaction'],  # BARU
                })

            comments_data.append({
                "id": comment.id,
                "user": comment_user_name,
                "user_nik": comment.user.nrp,
                "user_photo": comment_user_photo,
                "message": comment.message,
                "timestamp": comment.timestamp.isoformat(),
                "parent_comment_id": comment.parent_comment.id if comment.parent_comment else None,
                "is_edited": comment.is_edited,  # BARU
                "likes_count": comment_reaction_data['likes_count'],  # BARU
                "dislikes_count": comment_reaction_data['dislikes_count'],  # BARU
                "loves_count": comment_reaction_data['loves_count'],  # BARU
                "user_reaction": comment_reaction_data['user_reaction'],  # BARU
                "replies": replies_data
            })

        return JsonResponse({'status': 'success', 'comments': comments_data})

    except DailyReportSummary.DoesNotExist:
        logger.error(f"get_comments: Laporan dengan encoded_key={report_id} tidak ditemukan.")
        return JsonResponse({'status': 'error', 'message': 'Laporan tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam get_comments: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_GET
async def get_comment_reaction_users(request):
    """
    Mengembalikan daftar pengguna yang memberikan reaksi tertentu pada komentar.
    """
    comment_id = request.GET.get('comment_id')
    reaction_type = request.GET.get('reaction_type')  # misalnya, 'love', 'like', 'dislike'

    if not comment_id or not reaction_type:
        return JsonResponse({'status': 'error', 'message': 'comment_id dan reaction_type wajib diisi'}, status=400)

    # FIXED: Map incoming reaction_type to canonical emoji
    canonical_reaction_type = {
        'love': 'love', 'loved': 'love',
        'like': 'like', 'liked': 'like',
        'dislike': 'dislike', 'disliked': 'dislike',
    }.get(reaction_type.lower(), None)  # .lower() for case insensitivity

    if not canonical_reaction_type:
        return JsonResponse({'status': 'error', 'message': 'Tipe reaksi tidak valid'}, status=400)

    try:
        comment_obj = await sync_to_async(ReportComment.objects.get)(id=comment_id)

        reactions_queryset = ReportReaction.objects.filter(
            comment=comment_obj,
            emoji=canonical_reaction_type,  # Use canonical type
            report__isnull=True
        ).select_related('user')  # Prefetch info pengguna

        reacted_users_data = await database_sync_to_async(list)(reactions_queryset)

        users_list = []
        for reaction in reacted_users_data:
            user_obj = reaction.user
            user_name = user_obj.nama if user_obj.nama else user_obj.nrp
            user_photo_url = await _get_user_photo_url_async(user_obj, request)
            users_list.append({
                'user_nik': user_obj.nrp,
                'user_name': user_name,
                'user_photo_url': user_photo_url
            })

        return JsonResponse({'status': 'success', 'users': users_list})

    except ReportComment.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Komentar tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam get_comment_reaction_users: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_POST  # Pastikan ini tetap POST
async def delete_comment(request):
    if request.method != 'POST':  # Seharusnya tidak tercapai karena @require_POST
        logger.warning("delete_comment: Metode tidak diizinkan - menerima permintaan non-POST.")
        return JsonResponse({"status": "error", "message": "Metode tidak diizinkan"}, status=405)

    try:
        data = json.loads(request.body)
        comment_id = data.get('comment_id')
        user_nik = data.get('nik')  # FIXED: Mengambil 'nik' dari request

        logger.info(f"DEBUG delete_comment: Data yang diurai - comment_id='{comment_id}', user_nik='{user_nik}'")

        if not comment_id or not user_nik:
            logger.warning(f"delete_comment: Data tidak lengkap. comment_id: {comment_id}, user_nik: {user_nik}")
            return JsonResponse({"status": "error", "message": "comment_id dan nik wajib diisi"}, status=400)

        try:
            comment_to_delete = await sync_to_async(
                ReportComment.objects.select_related('report', 'user').get
            )(id=comment_id, user__nrp=user_nik)
        except ReportComment.DoesNotExist:
            logger.warning(
                f"delete_comment: Komentar {comment_id} tidak ditemukan atau bukan milik pengguna {user_nik}.")
            return JsonResponse({"status": "error", "message": "Tidak ditemukan atau bukan pemilik komentar"},
                                status=403)

        report_encoded_key = comment_to_delete.report.encoded_key

        # Hapus komentar
        deleted_count, _ = await sync_to_async(comment_to_delete.delete)()

        if deleted_count == 0:
            logger.error(f"delete_comment: Gagal menghapus komentar {comment_id} meskipun ditemukan.")
            return JsonResponse({"status": "error",
                                 "message": "Gagal menghapus komentar atau komentar tidak ditemukan setelah validasi"},
                                status=404)

        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_encoded_key)
        total_comments_count = await sync_to_async(report_summary.comments.count)()

        channel_layer = await sync_to_async(get_channel_layer)()

        # Kirim update via WebSocket
        await channel_layer.group_send(
            "reports_feed",
            {
                "type": "report_comment_update",
                "message": {
                    "encoded_key": report_encoded_key,
                    "comments_count": total_comments_count,
                    "deleted_comment_id": comment_id
                }
            }
        )

        return JsonResponse({"status": "success", "message": "Komentar dihapus"})

    except json.JSONDecodeError:
        logger.error(f"delete_comment: JSON tidak valid: {request.body.decode('utf-8')}", exc_info=True)
        return JsonResponse({"status": "error", "message": "JSON tidak valid"}, status=400)
    except DailyReportSummary.DoesNotExist:
        logger.error(
            f"delete_comment: Laporan terkait komentar {comment_id} (key: {report_encoded_key}) tidak ditemukan.",
            exc_info=True)
        return JsonResponse({"status": "error", "message": "Laporan terkait komentar tidak ditemukan"}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam delete_comment: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_POST
async def post_report_reaction(request):
    """
    Mengelola posting atau pembaruan reaksi pada laporan.
    """
    logger.info(f"DEBUG post_report_reaction: Raw request body: {request.body.decode('utf-8')}")
    try:
        data = json.loads(request.body)
        report_id = data.get('report_id')
        user_nik = data.get('nik')
        action = data.get('action')  # 'love', 'like', 'dislike', 'unlove', 'unlike', 'undislike'

        logger.info(
            f"DEBUG post_report_reaction: Data yang diurai - report_id='{report_id}', user_nik='{user_nik}', action='{action}'")

        if not report_id or not user_nik or not action:
            logger.warning(
                f"post_report_reaction: Data tidak lengkap. report_id: {report_id}, user_nik: {user_nik}, action: {action}")
            return JsonResponse({'status': 'error', 'message': 'Data tidak lengkap'}, status=400)

        # Dapatkan laporan dan pengguna
        report_summary = await sync_to_async(DailyReportSummary.objects.get)(encoded_key=report_id)
        db_manpower_user = await sync_to_async(MasterManpower.objects.get)(nrp=user_nik)

        # Tentukan target emoji dari action
        target_emoji = None
        is_un_action = False
        if action == 'love' or action == 'unlove':
            target_emoji = 'love'
            is_un_action = (action == 'unlove')
        elif action == 'like' or action == 'unlike':
            target_emoji = 'like'
            is_un_action = (action == 'unlike')
        elif action == 'dislike' or action == 'undislike':
            target_emoji = 'dislike'
            is_un_action = (action == 'undislike')
        else:
            logger.warning(f"post_report_reaction: Aksi tidak valid: {action}")
            return JsonResponse({'status': 'error', 'message': 'Aksi tidak valid'}, status=400)

        # Fungsi pembantu sinkron untuk logika reaksi dan perhitungan jumlah
        @sync_to_async
        def _process_reaction_and_get_counts_sync():
            with transaction.atomic():  # Pastikan operasi DB ini atomik
                # Pastikan filter ini juga secara eksplisit mencari reaksi laporan (comment__isnull=True)
                existing_reaction = ReportReaction.objects.filter(
                    report=report_summary,
                    user=db_manpower_user,
                    comment__isnull=True
                ).first()

                message = ""
                user_reaction_status_for_response = None

                if existing_reaction:
                    if existing_reaction.emoji == target_emoji:
                        # Jika emoji yang sama diklik lagi (toggle off)
                        existing_reaction.delete()
                        message = f"Reaksi '{target_emoji}' dihapus."
                        user_reaction_status_for_response = None
                    else:
                        # Jika emoji berbeda diklik (ubah reaksi)
                        existing_reaction.emoji = target_emoji
                        existing_reaction.save()
                        message = f"Reaksi diperbarui ke '{target_emoji}'."
                        user_reaction_status_for_response = target_emoji
                else:
                    if not is_un_action:  # Hanya buat reaksi jika bukan aksi 'un-' dan belum ada reaksi
                        ReportReaction.objects.create(
                            report=report_summary,
                            user=db_manpower_user,
                            emoji=target_emoji,
                            comment=None  # Penting: pastikan komentar adalah None untuk reaksi laporan
                        )
                        message = f"Reaksi '{target_emoji}' ditambahkan."
                        user_reaction_status_for_response = target_emoji
                    else:
                        message = "Tidak ada reaksi yang perlu dihapus."
                        user_reaction_status_for_response = None

                # Hitung ulang semua jumlah reaksi dan komentar
                reaction_data = async_to_sync(_get_entity_reaction_data_sync)(report_summary, user_nik=user_nik,
                                                                              is_report=True)

                return {
                    'message': message,
                    'likes_count': reaction_data['likes_count'],
                    'dislikes_count': reaction_data['dislikes_count'],
                    'loves_count': reaction_data['loves_count'],
                    'comments_count': reaction_data['comments_count'],  # Komentar tetap dihitung
                    'user_reaction_status_for_response': reaction_data['user_reaction'],
                }

        # Panggil fungsi pembantu sinkron
        results = await _process_reaction_and_get_counts_sync()

        # Dapatkan channel_layer di dalam konteks asinkron
        channel_layer = await sync_to_async(get_channel_layer)()
        await channel_layer.group_send(
            "reports_feed",
            {
                "type": "report_reaction_update",
                "message": {
                    "encoded_key": report_id,
                    "likes_count": results['likes_count'],
                    "dislikes_count": results['dislikes_count'],
                    "loves_count": results['loves_count'],
                    "user_nik": user_nik,
                    "user_reaction": results['user_reaction_status_for_response'],
                    "comments_count": results['comments_count']
                }
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': results['message'],
            'likes_count': results['likes_count'],
            'dislikes_count': results['dislikes_count'],
            'loves_count': results['loves_count'],
            'user_reaction': results['user_reaction_status_for_response'],
            'comments_count': results['comments_count']
        })

    except json.JSONDecodeError:
        logger.error(f"post_report_reaction: JSON tidak valid: {request.body.decode('utf-8')}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'JSON tidak valid'}, status=400)
    except DailyReportSummary.DoesNotExist:
        logger.error(f"post_report_reaction: Laporan dengan encoded_key={report_id} tidak ditemukan.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Laporan tidak ditemukan'}, status=404)
    except MasterManpower.DoesNotExist:
        logger.error(f"post_report_reaction: Pengguna dengan NIK={user_nik} tidak ditemukan.", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Pengguna tidak ditemukan'}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam post_report_reaction: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
@require_POST
async def post_comment_reaction(request):  # Diganti nama dari toggle_comment_reaction untuk konsistensi
    logger.info(f"DEBUG post_comment_reaction: Raw request body: {request.body.decode('utf-8')}")
    try:
        data = json.loads(request.body)
        comment_id = data.get('comment_id')
        user_nik = data.get('nik')
        emoji_action = data.get('action')  # 'love', 'like', 'dislike', 'unlove', 'unlike', 'undislike'

        logger.info(
            f"DEBUG post_comment_reaction: Data yang diurai - comment_id='{comment_id}', user_nik='{user_nik}', emoji_action='{emoji_action}'")

        if not comment_id or not user_nik or not emoji_action:
            logger.warning(
                f"post_comment_reaction: Field wajib diisi. comment_id: {comment_id}, user_nik: {user_nik}, emoji_action: {emoji_action}")
            return JsonResponse({"status": "error", "message": "Field wajib diisi"}, status=400)

        # Dapatkan komentar dan pengguna
        comment_obj = await sync_to_async(ReportComment.objects.get)(id=comment_id)
        db_manpower_user = await sync_to_async(MasterManpower.objects.get)(nrp=user_nik)

        # Tentukan target emoji dari action
        target_emoji = None
        is_un_action = False
        # FIXED: Tangani 'loved', 'liked', 'disliked' dari frontend
        if emoji_action == 'love' or emoji_action == 'unlove' or emoji_action == 'loved':
            target_emoji = 'love'
            is_un_action = (emoji_action == 'unlove')
        elif emoji_action == 'like' or emoji_action == 'unlike' or emoji_action == 'liked':
            target_emoji = 'like'
            is_un_action = (emoji_action == 'unlike')
        elif emoji_action == 'dislike' or emoji_action == 'undislike' or emoji_action == 'disliked':
            target_emoji = 'dislike'
            is_un_action = (emoji_action == 'undislike')
        else:
            logger.warning(f"post_comment_reaction: Aksi emoji tidak valid: {emoji_action}")
            return JsonResponse({'status': 'error', 'message': 'Aksi emoji tidak valid'}, status=400)

        # Fungsi pembantu sinkron untuk logika reaksi komentar dan perhitungan jumlah
        @sync_to_async
        def _process_comment_reaction_and_get_counts_sync():
            with transaction.atomic():  # Pastikan operasi DB ini atomik
                # Pastikan filter ini juga secara eksplisit mencari reaksi komentar (report__isnull=True)
                existing_reaction = ReportReaction.objects.filter(
                    comment=comment_obj,
                    user=db_manpower_user,
                    report__isnull=True  # Pastikan ini reaksi untuk komentar
                ).first()

                status_msg = ""
                message_msg = ""
                # user_reaction_emoji = None # Ini akan disetel oleh _get_entity_reaction_data_sync

                if existing_reaction:
                    if existing_reaction.emoji == target_emoji:
                        # Jika emoji yang sama diklik lagi (toggle off)
                        existing_reaction.delete()
                        status_msg = "removed"
                        message_msg = "Reaksi dihapus"
                    else:
                        # Jika emoji berbeda diklik (ubah reaksi)
                        existing_reaction.emoji = target_emoji
                        existing_reaction.save()
                        status_msg = "updated"
                        message_msg = "Reaksi diperbarui"
                else:
                    if not is_un_action:  # Hanya buat reaksi jika bukan aksi 'un-' dan belum ada reaksi
                        ReportReaction.objects.create(
                            comment=comment_obj,
                            user=db_manpower_user,
                            emoji=target_emoji,
                            report=None  # Penting: pastikan laporan adalah None untuk reaksi komentar
                        )
                        status_msg = "added"
                        message_msg = "Reaksi ditambahkan"
                    else:
                        status_msg = "skipped"
                        message_msg = "Tidak ada reaksi yang perlu dihapus."

                # Hitung ulang jumlah reaksi untuk komentar ini menggunakan pembantu konsolidasi
                reaction_data = async_to_sync(_get_entity_reaction_data_sync)(comment_obj, user_nik=user_nik,
                                                                              is_report=False)

                return {
                    'status_msg': status_msg,
                    'message_msg': message_msg,
                    'reactions_counts_dict': {
                        'likes_count': reaction_data['likes_count'],
                        'dislikes_count': reaction_data['dislikes_count'],
                        'loves_count': reaction_data['loves_count'],
                    },
                    'user_reaction_emoji': reaction_data['user_reaction'],
                }

        results = await _process_comment_reaction_and_get_counts_sync()

        # Dapatkan channel_layer di dalam konteks asinkron
        channel_layer = await sync_to_async(get_channel_layer)()
        await channel_layer.group_send(
            "reports_feed",
            {
                "type": "comment_reaction_update",
                "message": {
                    "id": comment_id,
                    "likes_count": results['reactions_counts_dict']['likes_count'],
                    "dislikes_count": results['reactions_counts_dict']['dislikes_count'],
                    "loves_count": results['reactions_counts_dict']['loves_count'],
                    "user_nik": user_nik,
                    "user_reaction": results['user_reaction_emoji'],
                }
            }
        )

        return JsonResponse({
            "status": results['status_msg'],
            "message": results['message_msg'],
            "reactions_counts": results['reactions_counts_dict'],
            "user_reaction_emoji": results['user_reaction_emoji'],
        })

    except json.JSONDecodeError:
        logger.error(f"post_comment_reaction: JSON tidak valid: {request.body.decode('utf-8')}", exc_info=True)
        return JsonResponse({"status": "error", "message": "JSON tidak valid"}, status=400)
    except ReportComment.DoesNotExist:
        logger.error(f"post_comment_reaction: Komentar dengan ID={comment_id} tidak ditemukan.", exc_info=True)
        return JsonResponse({"status": "error", "message": "Komentar tidak ditemukan."}, status=404)
    except MasterManpower.DoesNotExist:
        logger.error(f"post_comment_reaction: Pengguna dengan NIK={user_nik} tidak ditemukan.", exc_info=True)
        return JsonResponse({"status": "error", "message": "Pengguna tidak ditemukan."}, status=404)
    except Exception as e:
        logger.error(f"ERROR dalam post_comment_reaction: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": 'Terjadi kesalahan server internal.'}, status=500)


@csrf_exempt
def register_fcm_token(request):
    if request.method == 'POST':
        try:
            import pprint
            pp = pprint.PrettyPrinter(indent=4)

            print("✅ Payload Body:")
            raw_body = request.body
            try:
                json_data = json.loads(raw_body)
                pp.pprint(json_data)
            except Exception as e:
                print("❌ Gagal parsing JSON:")
                print(raw_body)
                raise e

            data = json_data
            token = data.get('token')
            nik = data.get('nik', '').strip()
            user = data.get("user_name", "Anonymous")

            print(f"[DEBUG] Nik diterima: '{nik}'")

            if not token or not nik:  # MODIFIED: pastikan nik juga diperiksa
                return JsonResponse({"status": "error", "message": "Token dan NIK wajib diisi"}, status=400)

            # Gunakan query case-insensitive
            from reports.models import MasterManpower
            # MODIFIED: pastikan pencarian MasterManpower adalah async jika diperlukan, di sini dalam view sync
            # jadi perlu di-await jika dipanggil. Tapi view ini sinkron, jadi tidak masalah.
            user_manpower_obj = MasterManpower.objects.filter(nrp__iexact=nik, is_active=True).first()
            if not user_manpower_obj:
                print("[DEBUG] Hasil filter kosong:")
                # Tampilkan 5 NRP teratas sebagai referensi
                sample = list(MasterManpower.objects.all().values_list("nrp", flat=True)[:5])
                print("Contoh isi DB (nrp):", sample)
                return JsonResponse({"status": "error", "message": "NIK tidak valid"}, status=404)

            print(f"[DEBUG] Pengguna ditemukan: {user_manpower_obj.nama}")

            from reports.models import FCMDevice
            FCMDevice.objects.update_or_create(
                registration_id=token,
                defaults={"active": True, "user_nik": user_manpower_obj, "user_name": user_manpower_obj.nama}
            )

            return JsonResponse({"status": "success",
                                 "message": "Token FCM berhasil disimpan",
                                 "user_name": user_manpower_obj.nama
                                 })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Metode tidak diizinkan"}, status=405)
