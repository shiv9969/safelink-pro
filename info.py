import os

# Keep secrets in deployment environment variables, never in source control.
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret")
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")

BASE_URL = os.environ.get("BASE_URL", "https://bob-files-safelink.vercel.app/")

MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "safelink")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "shiv")
