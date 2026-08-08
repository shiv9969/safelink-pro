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


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- CREATE SAFELINK ----------------

@app.route("/create", methods=["POST"])
def create():
    try:
        # ---------------- GET URL ----------------

        if request.is_json:
            data = request.get_json(silent=True) or {}
            url = data.get("url")
        else:
            url = request.form.get("url")

        # ---------------- VALIDATE URL ----------------

        if not url or not url.startswith(("http://", "https://")):

            if request.is_json:
                return {
                    "error": "Invalid URL!"
                }, 400

            return "Invalid URL!", 400

        # ---------------- GENERATE ID ----------------

        link_id = generate_id()

        # ---------------- SAVE ORIGINAL URL ----------------

        save_link(
            link_id,
            url
        )

        # ---------------- GENERATE SAFELINK ----------------

        safe_link = (
            info.BASE_URL.rstrip("/")
            + "/s/"
            + link_id
        )

        # ---------------- JSON RESPONSE FOR BOT ----------------

        if request.is_json:
            return {
                "url": safe_link
            }, 200

        # ---------------- NORMAL BROWSER RESPONSE ----------------

        return render_template(
            "index.html",
            safe_link=safe_link
        )

    except Exception as e:

        app.logger.exception(
            "Error in /create"
        )

        # Return JSON error to bot
        if request.is_json:
            return {
                "error": str(e)
            }, 500

        # Browser error
        return redirect(
            "/?error=1"
        )


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

        verify = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": info.RECAPTCHA_SECRET_KEY,
                "response": captcha_response
            },
            timeout=15
        ).json()

    except Exception as e:

        app.logger.exception(
            "reCAPTCHA verification error"
        )

        return "CAPTCHA verification error!", 500

    # ---------------- CAPTCHA RESULT ----------------

    if not verify.get("success"):
        return "CAPTCHA failed!", 400

    # ---------------- REDIRECT TO ORIGINAL URL ----------------

    return redirect(url)


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run()
