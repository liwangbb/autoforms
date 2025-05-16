import os

from dotenv import load_dotenv

load_dotenv()

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
DOCUMENT_AI_ENDPOINT = os.getenv("DOCUMENT_AI_ENDPOINT")
DOCUMENT_AI_SCOPES = os.getenv("DOCUMENT_AI_SCOPES", "").split(",")

# Optional: Safety checks
required_vars = {
    "GOOGLE_APPLICATION_CREDENTIALS": GOOGLE_APPLICATION_CREDENTIALS,
    "DOCUMENT_AI_ENDPOINT": DOCUMENT_AI_ENDPOINT,
}

for var, val in required_vars.items():
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {var}")
