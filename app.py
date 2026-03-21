from flask import Flask, request, redirect, render_template, abort, session
import string
import random
import requests
from pymongo import MongoClient
import info
import time

app = Flask(__name__)
app.secret_key = info.SECRET_KEY

# MongoDB
client = MongoClient(info.MONGO_URI)
db = client[info.DB_NAME]
collection = db[info.COLLECTION_NAME]

# ---------------- UTIL ----------------
def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

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
    url = request.form.get("url")

    if not url or not url.startswith("http"):
        return "Invalid URL!"

    link_id = generate_id()
    save_link(link_id, url)

    safe_link = info.BASE_URL + "s/" + link_id

    return render_template("index.html", safe_link=safe_link)


# 🔐 STEP 1 (Captcha)
@app.route("/s/<link_id>", methods=["GET", "POST"])
def step1(link_id):
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

    # 🔐 Generate token + store in session
    token = generate_token()
    session["token"] = token
    session["link_id"] = link_id
    session["time"] = time.time()

    return redirect("/step2")


# 🔁 STEP 2 (Intermediate)
@app.route("/step2")
def step2():
    if "token" not in session:
        return "Access Denied!"

    return render_template("step2.html")


# 🚀 FINAL STEP
@app.route("/final")
def final():
    token = session.get("token")
    link_id = session.get("link_id")
    start_time = session.get("time")

    if not token or not link_id:
        return "Access Denied!"

    if time.time() - start_time < 3:
        return "Too fast!"

    url = get_link(link_id)

    session.clear()

    # 👉 Redirect nahi — page show kar
    return render_template("redirect.html", target=url)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()
