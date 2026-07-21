import os  # for path manipulation

import firebase_admin
from django.conf import settings
from firebase_admin import credentials


def initialize_firebase():
    """
    Menginisialisasi Firebase Admin SDK.
    Mencari jalur kunci akun layanan di pengaturan Django.
    Menggunakan kunci akun layanan untuk mengakses Firebase Realtime Database.
    """
    if not firebase_admin._apps:
        try:
            service_account_path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH', None)

            if not service_account_path:
                print("ERROR: FIREBASE_SERVICE_ACCOUNT_KEY_PATH is not set in settings.py")
                return False

            # Pastikan jalurnya absolut jika belum
            if not os.path.isabs(service_account_path):
                full_path = os.path.join(settings.BASE_DIR, service_account_path)
            else:
                full_path = service_account_path

            if not os.path.isfile(full_path):
                raise FileNotFoundError(f"Firebase service account key file not found at: {full_path}")

            cred = credentials.Certificate(full_path)
            firebase_admin.initialize_app(cred)
            print("INFO: Firebase Admin SDK initialized successfully.")
            return True
        except Exception as e:
            print(f"ERROR: Failed to initialize Firebase Admin SDK: {e}")
            return False
    else:
        print("INFO: Firebase Admin SDK already initialized.")
        return True
