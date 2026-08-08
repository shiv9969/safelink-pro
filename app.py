from flask import Flask, request, redirect, render_template, abort
import string
import random
import requests
from pymongo import MongoClient
import info

app = Flask(__name__)
app.secret_key = info.SECRET_KEY


# ---------------- MONGODB ----------------

client = MongoClient(info.MONGO_URI)

db = client[info.DB_NAME]

collection = db[info.COLLECTION_NAME]


# ---------------- UTIL ----------------

def generate_id(length=8):
    return ''.join(
        random.choices(
            string.ascii_letters + string.digits,
            k=length
        )
    )


def save_link(link_id, url):
    collection.insert_one({
        "id": link_id,
        "url": url
    })


def get_link(link_id):
    data = collection.find_one({
        "id": link_id
    })

    return data["url"] if data else None


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- CREATE SAFELINK ----------------

@app.route("/create", methods=["POST"])
def create():
    try:
        # Bot/API request
        data = request.get_json(silent=True)

        if data is not None:
            url = data.get("url")
            is_api_request = True

        # Normal website form request
        else:
            url = request.form.get("url")
            is_api_request = False

        # Validate URL
        if not url or not url.startswith(("http://", "https://")):

            if is_api_request:
                return {
                    "error": "Invalid URL!"
                }, 400

            return render_template(
                "index.html",
                error="Invalid URL! Please enter a valid link."
            ), 400

        # Generate ID
        link_id = generate_id()

        # Save original shortener URL
        save_link(link_id, url)

        # Generate SafeLink
        safe_link = (
            info.BASE_URL.rstrip("/")
            + "/s/"
            + link_id
        )

        # IMPORTANT: bot gets JSON
        if is_api_request:
            return {
                "url": safe_link
            }, 200

        # Browser gets normal page
        return render_template(
            "index.html",
            safe_link=safe_link
        )

    except Exception as e:
        app.logger.exception("Error in /create")
        return {"error": str(e)}, 500


# ---------------- SAFELINK ----------------

@app.route("/s/<link_id>", methods=["GET", "POST"])
def safelink(link_id):

    # Get original URL
    url = get_link(link_id)

    if not url:
        return abort(404)

    # ---------------- GET SAFELINK PAGE ----------------

    if request.method == "GET":

        return render_template(
            "safe.html",
            site_key=info.RECAPTCHA_SITE_KEY
        )

    # ---------------- CAPTCHA VERIFY ----------------

    captcha_response = request.form.get(
        "g-recaptcha-response"
    )

    if not captcha_response:
        return "CAPTCHA failed!", 400

    try:

        verify_response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": info.RECAPTCHA_SECRET_KEY,
                "response": captcha_response
            },
            timeout=15
        )

        verify = verify_response.json()

    except Exception:

        app.logger.exception(
            "reCAPTCHA verification error"
        )

        return "CAPTCHA verification error!", 500

    # ---------------- CAPTCHA RESULT ----------------

    if not verify.get("success"):
        return "CAPTCHA failed!", 400

    # ---------------- REDIRECT ----------------

    return redirect(url)


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run()
