from flask import Flask, request, redirect, render_template, abort
import string
import random
import requests
from pymongo import MongoClient
import info

app = Flask(__name__)
app.secret_key = info.SECRET_KEY

# MongoDB
client = MongoClient(info.MONGO_URI)
db = client[info.DB_NAME]
collection = db[info.COLLECTION_NAME]

# ---------------- UTIL ----------------
def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def save_link(link_id, url):
    collection.insert_one({"id": link_id, "url": url})

def get_link(link_id):
    data = collection.find_one({"id": link_id})
    return data["url"] if data else None

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create", methods=["POST"])
def create():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        url = data.get("url")
    else:
        url = request.form.get("url")

    if not url or not url.startswith("http"):
        if request.is_json:
            return {"error": "Invalid URL!"}, 400
        return "Invalid URL!", 400

    link_id = generate_id()
    save_link(link_id, url)

    safe_link = info.BASE_URL + "s/" + link_id

    if request.is_json:
        return {"url": safe_link}

    return render_template("index.html", safe_link=safe_link)


@app.route("/s/<link_id>", methods=["GET", "POST"])
def safelink(link_id):
    url = get_link(link_id)

    if not url:
        return abort(404)

    if request.method == "GET":
        return render_template("safe.html", site_key=info.RECAPTCHA_SITE_KEY)

    # CAPTCHA VERIFY
    captcha_response = request.form.get("g-recaptcha-response")

    verify = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": info.RECAPTCHA_SECRET_KEY,
            "response": captcha_response
        }
    ).json()

    if not verify.get("success"):
        return "CAPTCHA failed!"

    return redirect(url)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()
