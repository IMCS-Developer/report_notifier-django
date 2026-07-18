import traceback

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

from reports.models import MasterManpower


class NRPAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Mengautentikasi pengguna berdasarkan NRP dari MasterManpower.
        Secara otomatis membuat/mengaitkan user Django jika ditemukan di MasterManpower.
        Username yang diharapkan adalah NRP.
        """
        try:
            # Cari MasterManpower berdasarkan NRP (username yang dimasukkan)
            manpower = MasterManpower.objects.get(nrp=username)

            # Jika MasterManpower ditemukan, cek apakah sudah ada user Django yang terkait
            # MODIFIED: Menggunakan `related_name` `user_account` yang diharapkan ada di model MasterManpower
            if hasattr(manpower, 'user_account'):  # Periksa apakah objek terkait ada
                user = manpower.user_account
            else:
                # Jika belum ada user Django yang terkait, buat yang baru
                # Set password sebagai 'UNUSABLE_PASSWORD' secara default
                # User harus mengubah password mereka setelah login pertama
                # Atau, Anda bisa memiliki alur "registrasi" terpisah
                # NEW: Pastikan username unik untuk Django User
                user, created = User.objects.get_or_create(username=manpower.nrp, defaults={'password': ''})
                if created:
                    user.set_unusable_password()  # Set tidak dapat digunakan untuk pengguna yang baru dibuat tanpa password
                    user.save()
                manpower.user_account = user  # Tetapkan User yang dibuat atau diambil ke MasterManpower
                manpower.save()
                print(f"INFO: User Django baru dibuat/dikaitkan dengan MasterManpower NRP: {manpower.nrp}")

            # Verifikasi password yang diberikan dengan password user Django
            if user.check_password(password) and user.is_active:
                print(f"INFO: Pengguna {username} berhasil diautentikasi.")
                return user
            else:
                print(f"WARNING: Password salah atau pengguna tidak aktif untuk NRP: {username}")
                return None  # Password salah atau user tidak aktif

        except MasterManpower.DoesNotExist:
            print(f"WARNING: MasterManpower dengan NRP {username} tidak ditemukan.")
            return None  # MasterManpower tidak ditemukan
        except Exception as e:
            print(f"ERROR: Kesalahan pada proses autentikasi: {e}")
            traceback.print_exc()
            return None

    def get_user(self, user_id):
        """
        Mengambil objek User dari ID.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
