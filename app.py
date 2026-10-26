from flask import Flask, request, redirect, render_template, abort, session, jsonify
import string
import random
import requests
from pymongo import MongoClient
from urllib.parse import urlparse
from functools import wraps
import hmac
import hashlib
import os
import info
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", info.SECRET_KEY)

# MongoDB
client = MongoClient(os.environ.get("MONGO_URI", info.MONGO_URI), serverSelectionTimeoutMS=5000)
db = client[os.environ.get("DB_NAME", info.DB_NAME)]
collection = db[os.environ.get("COLLECTION_NAME", info.COLLECTION_NAME)]

# API key used by the bot to create opaque, one-off wrapper links.
# Set WRAP_API_KEY in Vercel Environment Variables; do not use the site key here.
WRAP_API_KEY = os.environ.get("WRAP_API_KEY", "")

# ---------------- UTIL ----------------
def generate_id(length=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

def is_safe_http_url(raw_url):
    try:
        parsed = urlparse(raw_url)
        return parsed.scheme in ("https", "http") and bool(parsed.netloc) and not parsed.username and not parsed.password
    except Exception:
        return False

def save_link(link_id, url):
    collection.insert_one({"id": link_id, "url": url, "created_at": time.time()})

def get_link(link_id):
    data = collection.find_one({"id": link_id})
    if not data:
        return None
    # Expire wrapper records after 24 hours.
    if time.time() - data.get("created_at", time.time()) > 86400:
        collection.delete_one({"id": link_id})
        return None
    return data.get("url")

def require_wrap_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        supplied = request.headers.get("X-Wrap-Key", "")
        if not WRAP_API_KEY or not hmac.compare_digest(supplied, WRAP_API_KEY):
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    safe_link = request.args.get("link")
    error = None
    if request.args.get("error"):
        error = "Invalid URL! Please enter a valid link."
    return render_template("index.html", safe_link=safe_link, error=error)

@app.route("/api/wrap", methods=["POST"])
@require_wrap_key
def api_wrap():
    """Create an opaque wrapper link for the trusted bot backend."""
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not is_safe_http_url(url):
        return jsonify({"error": "A valid HTTP/HTTPS URL is required"}), 400

    link_id = generate_id()
    # Avoid accidental collisions in the random identifier.
    while collection.find_one({"id": link_id}, {"_id": 1}):
        link_id = generate_id()
    save_link(link_id, url)
    return jsonify({"url": info.BASE_URL.rstrip("/") + "/s/" + link_id}), 201

@app.route("/create", methods=["POST"])
def create():
    url = (request.form.get("url") or "").strip()
    if not is_safe_http_url(url):
        return redirect("/?error=1")
    link_id = generate_id()
    save_link(link_id, url)
    safe_link = info.BASE_URL.rstrip("/") + "/s/" + link_id
    return redirect("/?link=" + safe_link)

# Step 1: CAPTCHA
@app.route("/s/<link_id>", methods=["GET", "POST"])
def step1(link_id):
    url = get_link(link_id)
    if not url:
        return abort(404)

    if request.method == "GET":
        return render_template("safe.html", site_key=info.RECAPTCHA_SITE_KEY)

    captcha_response = request.form.get("g-recaptcha-response")
    if not captcha_response:
        return "CAPTCHA required!", 400

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": info.RECAPTCHA_SECRET_KEY,
                "response": captcha_response
            },
            timeout=8
        )
        verify = response.json()
    except (requests.RequestException, ValueError):
        return "CAPTCHA service temporarily unavailable. Please retry.", 503

    if not verify.get("success"):
        return "CAPTCHA failed!", 400

    session["token"] = generate_token()
    session["link_id"] = link_id
    session["time"] = time.time()
    return redirect("/step2")

@app.route("/step2")
def step2():
    if "token" not in session or "link_id" not in session:
        return "Access Denied!", 403
    if time.time() - session.get("time", 0) > 600:
        session.clear()
        return "Session expired. Open the verification link again.", 410
    return render_template("step2.html")

@app.route("/final")
def final():
    token = session.get("token")
    link_id = session.get("link_id")
    started = session.get("time", 0)
    if not token or not link_id or time.time() - started > 600:
        session.clear()
        return "Access Denied or session expired!", 403

    url = get_link(link_id)
    session.clear()
    if not url or not is_safe_http_url(url):
        return abort(404)
    return render_template("redirect.html", target=url)

if __name__ == "__main__":
    app.run()
