import base64
import json

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from services.config.google_config import (
    DOCUMENT_AI_ENDPOINT,
    DOCUMENT_AI_SCOPES,
    GOOGLE_APPLICATION_CREDENTIALS,
)


def get_docai_access_token():
    """
    Get an access token using the service account credentials.
    """
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_APPLICATION_CREDENTIALS, scopes=DOCUMENT_AI_SCOPES
    )
    credentials.refresh(Request())
    return credentials.token


def send_docai_request(pdf_path, endpoint=DOCUMENT_AI_ENDPOINT):
    """
    Send a PDF file to Document AI and return the raw JSON response.
    """
    token = get_docai_access_token()

    with open(pdf_path, "rb") as f:
        pdf_content = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "rawDocument": {"content": pdf_content, "mimeType": "application/pdf"}
    }

    try:
        response = requests.post(
            endpoint, headers=headers, data=json.dumps(payload), timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        handle_docai_exception(e, response)
        return None


def handle_docai_exception(e, response=None):
    """
    Gracefully handle exceptions from Document AI.
    """
    print("❌ Error calling Document AI:")
    print(f"🔹 {str(e)}")
    if response is not None:
        print(f"🔻 Status code: {response.status_code}")
        print(f"🔻 Response body: {response.text}")
