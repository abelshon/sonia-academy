import os
import uuid
from datetime import timedelta, datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR=os.path.abspath(os.path.join(BASE_DIR,"..","frontend"))

app=Flask(__name__)
app.secret_key=os.environ["SECRET_KEY"]
app.permanent_session_lifetime=timedelta(hours=8)
origins=[x.strip() for x in os.environ.get("FRONTEND_ORIGIN","").split(",") if x.strip()]
CORS(app, origins=origins or "*", supports_credentials=True)

supabase=create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not session.get("admin_id"):
            return jsonify({"error":"Authentication required"}),401
        return fn(*args,**kwargs)
    return wrapped

def get_value(key):
    r=supabase.table("app_data").select("value").eq("key",key).limit(1).execute()
    return r.data[0]["value"] if r.data else None

def set_value(key,value):
    supabase.table("app_data").upsert({"key":key,"value":value},on_conflict="key").execute()

@app.get("/api/health")
def health():
    supabase.table("app_data").select("key").limit(1).execute()
    return jsonify({"ok":True,"database":"supabase"})

@app.post("/api/auth/login")
def login():
    b=request.get_json(silent=True) or {}
    r=supabase.table("admins").select("id,username,password_hash").eq("username",str(b.get("username","")).strip()).limit(1).execute()
    if not r.data or not check_password_hash(r.data[0]["password_hash"],str(b.get("password",""))):
        return jsonify({"error":"Invalid username or password"}),401
    session.permanent=True
    session["admin_id"]=str(r.data[0]["id"]); session["username"]=r.data[0]["username"]
    return jsonify({"authenticated":True,"username":r.data[0]["username"]})

@app.get("/api/auth/me")
def me():
    return jsonify({"authenticated":bool(session.get("admin_id")),"username":session.get("username")})

@app.post("/api/auth/logout")
def logout():
    session.clear(); return jsonify({"authenticated":False})

@app.get("/api/data/<key>")
def get_data(key):
    return jsonify({"value":get_value(key)})

@app.put("/api/data/<key>")
@admin_required
def put_data(key):
    if key in {"admin_auth","admin_session"}: return jsonify({"error":"Protected key"}),403
    b=request.get_json(silent=True) or {}
    if "value" not in b: return jsonify({"error":"Missing value"}),400
    set_value(key,b["value"]); return jsonify({"ok":True})
@app.post("/api/uploads")
@admin_required
def upload_file():
    file = request.files.get("file")

    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif"
    }

    if file.mimetype not in allowed_types:
        return jsonify({
            "error": "Only JPG, PNG, WEBP and GIF images are allowed"
        }), 400

    # Limit upload size to 5 MB
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > 5 * 1024 * 1024:
        return jsonify({
            "error": "Image must be smaller than 5 MB"
        }), 400

    original_name = secure_filename(file.filename)
    extension = os.path.splitext(original_name)[1].lower()

    storage_path = f"uploads/{uuid.uuid4().hex}{extension}"

    try:
        file_bytes = file.read()

        supabase.storage.from_("academy-images").upload(
            storage_path,
            file_bytes,
            {
                "content-type": file.mimetype,
                "upsert": "false"
            }
        )

        public_url = supabase.storage.from_(
            "academy-images"
        ).get_public_url(storage_path)

        return jsonify({
            "ok": True,
            "url": public_url,
            "path": storage_path
        })

    except Exception as e:
        app.logger.exception("Image upload failed")

        return jsonify({
            "error": "Image upload failed",
            "details": str(e)
        }), 500
@app.post("/api/enquiries")
def enquiry():
    b=request.get_json(silent=True) or {}
    if any(not str(b.get(k,"")).strip() for k in ("name","phone","course")):
        return jsonify({"error":"Name, phone and course are required"}),400
    now=datetime.now(timezone.utc)
    e={"id":"enq_"+now.strftime("%Y%m%d%H%M%S%f"),"name":str(b["name"]).strip(),"phone":str(b["phone"]).strip(),"course":str(b["course"]).strip(),"message":str(b.get("message","")).strip(),"date":now.date().isoformat(),"status":"new","convertedStudentId":None}
    values=get_value("enquiries") or []; values.append(e); set_value("enquiries",values)
    return jsonify(e),201

@app.get("/api/dashboard/stats")
@admin_required
def stats():
    def a(k): return get_value(k) or []
    payments=a("payments")
    return jsonify({"students":len(a("students")),"enquiries":len(a("enquiries")),"courses":len(a("courses")),"payments":len(payments),"revenue":sum(float(x.get("amount",0) or 0) for x in payments)})

@app.route("/",defaults={"path":""})
@app.route("/<path:path>")
def frontend(path):
    p=os.path.join(FRONTEND_DIR,path)
    if path and os.path.isfile(p): return send_from_directory(FRONTEND_DIR,path)
    return send_from_directory(FRONTEND_DIR,"index.html")

def ensure_admin():
    u=os.environ.get("ADMIN_USERNAME","admin"); p=os.environ.get("ADMIN_PASSWORD")
    if not p: raise RuntimeError("Set ADMIN_PASSWORD in .env")
    r=supabase.table("admins").select("id").eq("username",u).limit(1).execute()
    if not r.data: supabase.table("admins").insert({"username":u,"password_hash":generate_password_hash(p)}).execute()

if __name__=="__main__":
    ensure_admin()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
