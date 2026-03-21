from flask import Flask, request, redirect, render_template_string, abort
import string
import random
import requests
from pymongo import MongoClient

import info

app = Flask(__name__)
app.secret_key = info.SECRET_KEY

# 🔗 MongoDB Connection
client = MongoClient(info.MONGO_URI)
db = client[info.DB_NAME]
collection = db[info.COLLECTION_NAME]

# ---------------- UTIL ----------------
def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def save_link(link_id, url):
    collection.insert_one({
        "id": link_id,
        "url": url
    })

def get_link(link_id):
    data = collection.find_one({"id": link_id})
    return data["url"] if data else None

# ---------------- UI ----------------
HOME_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>BoB Files Safe Link</title>
</head>

<body style="text-align:center; margin-top:80px; font-family:sans-serif; background:#f5f5f5;">

<h1>🔐 BoB Files Safe Link</h1>

<form method="POST" action="/create">
<input type="text" name="url" placeholder="Paste your URL here..." required 
style="width:350px;padding:12px;border-radius:5px;border:1px solid #ccc;">
<br><br>
<button style="padding:10px 25px;background:black;color:white;border:none;border-radius:5px;">
Generate Safe Link
</button>
</form>

{% if safe_link %}
<h3>Your Safe Link:</h3>
<input value="{{ safe_link }}" style="width:380px;padding:10px;" readonly>
{% endif %}

</body>
</html>
"""

SAFE_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>BoB Files Safe Link</title>
</head>

<body style="text-align:center; margin-top:100px; font-family:sans-serif; background:#f5f5f5;">

<h2>🔐 BoB Files Safe Link</h2>
<p>Please verify you are human to continue</p>

<form method="POST">
<div class="g-recaptcha" data-sitekey="{{ site_key }}"></div>
<br>
<button style="padding:10px 20px;background:black;color:white;border:none;border-radius:5px;">
Continue
</button>
</form>

<script src="https://www.google.com/recaptcha/api.js" async defer></script>

</body>
</html>
"""

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template_string(HOME_PAGE)


@app.route("/create", methods=["POST"])
def create():
    url = request.form.get("url")

    if not url or not url.startswith("http"):
        return "❌ Invalid URL!"

    link_id = generate_id()
    save_link(link_id, url)

    safe_link = info.BASE_URL + "s/" + link_id

    return render_template_string(HOME_PAGE, safe_link=safe_link)


@app.route("/s/<link_id>", methods=["GET", "POST"])
def safelink(link_id):
    url = get_link(link_id)

    if not url:
        return abort(404)

    if request.method == "GET":
        return render_template_string(SAFE_PAGE, site_key=info.RECAPTCHA_SITE_KEY)

    # 🔐 CAPTCHA VERIFY
    captcha_response = request.form.get("g-recaptcha-response")

    verify = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": info.RECAPTCHA_SECRET_KEY,
            "response": captcha_response
        }
    ).json()

    if not verify.get("success"):
        return "❌ CAPTCHA failed!"

    return redirect(url)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run()
