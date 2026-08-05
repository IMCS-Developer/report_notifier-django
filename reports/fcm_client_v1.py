import json
import time
import traceback

import requests
from django.conf import settings  # NEW: Import Django settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SERVICE_ACCOUNT_FILE = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH
FCM_PROJECT_ID = settings.FCM_PROJECT_ID

SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


def get_access_token():
    """
    Retrieves the access token for Firebase Cloud Messaging API using the service account.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    credentials.refresh(Request())
    return credentials.token


class FCMResponse:
    """
    Represents the response for a single FCM token send attempt.
    """

    def __init__(self, success, token, exception=None):
        self.success = success
        self.token = token
        self.exception = exception


class FCMResponseWrapper:
    """
    A wrapper to hold multiple FCMResponse objects for batch sending.
    """

    def __init__(self, responses):
        self.responses = responses


def send_fcm_notification_v1(tokens, title, data=None, android_channel_id=None, max_retries=3):
    """
    Sends FCM data-only messages to a list of device tokens.

    Args:
        tokens (list): A list of FCM registration tokens.
        title (str): The title for the notification (will be sent in the data payload).
        data (dict, optional): Custom data payload to send with the notification.
                               All values will be converted to strings.
        android_channel_id (str, optional): The Android notification channel ID.
                                             Defaults to "daily_report_channel".
        max_retries (int): Maximum number of retries for sending a message to a single token.

    Returns:
        FCMResponseWrapper: An object containing results for each token.
    """
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8",
    }

    responses = []  # List to store FCMResponse objects for each token

    for token in tokens:
        # Initialize safe_data with default structure.
        # All values in FCM data payload MUST be strings.
        safe_data = {
            "click_action": "FLUTTER_NOTIFICATION_CLICK",
            "title": str(title),  # Ensure title is a string
            "report_date": "",
            "shift": "",
            "today_rom": "0",
            "today_jetty": "0",
            "mtd_rom": "0",
            "mtd_jetty": "0",
            "image": "",
            "web": "",
            "apk": "",
            # Add other default fields that are expected by the client
            "likes_count": "0",
            "dislikes_count": "0",
            "loves_count": "0",
            "comments_count": "0",
            "user_reaction": "",
            "user": "System",
            "user_photo": "",
            "sender_nik": "",
            "notif_text": "",
            "timestamp": "",
        }

        if data:
            for k, v in data.items():
                # NEW LOGIC: Ensure all values are converted to strings
                try:
                    safe_data[k] = str(v)
                except Exception as e:
                    print(f"WARNING: Data payload key '{k}' could not be converted to string. Skipping. Error: {e}")

        message_payload = {
            "message": {
                "token": token,
                # The 'notification' block is intentionally omitted here for data-only messages,
                # as the Flutter app handles notification display from the 'data' payload.
                "data": safe_data,  # Only send the data payload
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": android_channel_id or "daily_report_channel",
                        "click_action": "FLUTTER_NOTIFICATION_CLICK"
                    }
                }
            }
        }

        attempt = 0
        while attempt < max_retries:
            try:
                response = requests.post(
                    f"https://fcm.googleapis.com/v1/projects/{FCM_PROJECT_ID}/messages:send",
                    headers=headers,
                    data=json.dumps(message_payload)
                )

                if response.status_code == 200:
                    print(f"✅ Successfully sent to {token}")
                    responses.append(FCMResponse(success=True, token=token))
                    break  # Success, break from retry loop
                else:
                    # Log error response from FCM
                    print(
                        f"❌ Failed to send to {token} (Attempt {attempt + 1}/{max_retries}): Status {response.status_code}, Response: {response.text}")
                    attempt += 1
                    if attempt >= max_retries:
                        responses.append(FCMResponse(success=False, token=token,
                                                     exception=response.text))  # Store error response text
            except requests.exceptions.RequestException as req_e:
                print(f"❌ Network/Request error sending to {token} (Attempt {attempt + 1}/{max_retries}): {req_e}")
                traceback.print_exc()
                attempt += 1
                if attempt >= max_retries:
                    responses.append(FCMResponse(success=False, token=token, exception=req_e))
            except Exception as e:
                print(f"❌ Unexpected exception sending to {token} (Attempt {attempt + 1}/{max_retries}): {e}")
                traceback.print_exc()
                attempt += 1
                if attempt >= max_retries:
                    responses.append(FCMResponse(success=False, token=token, exception=e))

            if attempt < max_retries:  # Only sleep if retries are remaining
                time.sleep(1)  # Wait before retrying

    return FCMResponseWrapper(responses=responses)
