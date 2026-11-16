"""学習塾 成績管理アプリ（セキュア版）

セキュリティ方針（SECURITY.md）:
- パスワードはハッシュ保存（werkzeug）
- SECRET_KEY は環境変数から読む
- SQL はプレースホルダのみ
- 認可はサーバ側で毎回確認（IDを変えても他人に届かない）
- ログイン試行に回数制限
- ログイン・閲覧を監査ログに記録
"""
import os
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import (Flask, abort, g, redirect, render_template, request,
                   session, url_for)

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "seiseki.db"))

SUBJECTS = [("kokugo", "国語"), ("sugaku", "数学"), ("eigo", "英語"),
            ("rika", "理科"), ("shakai", "社会")]
EXAMS = ["2026-04", "2026-07", "2026-10"]

# 志望校の基準偏差値（運営のみが合格確率計算に使う。生徒には見せない）
SCHOOL_HENSACHI = {
    "今治西高校": 65, "今治北高校": 54, "今治南高校": 43,
    "今治工業高校": 39, "今治精華高校": 42, "今治明徳高校": 38,
}

# ログイン試行の回数制限（メモリ内。本番はRedis等）
_LOGIN_FAILS = {}          # username -> [失敗時刻,...]
MAX_FAILS = 5
WINDOW_SEC = 300


def create_app():
    app = Flask(__name__)
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "SECRET_KEY が設定されていません。.env.example を .env にコピーして設定してください。")
    app.config["SECRET_KEY"] = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    register_routes(app)
    return app


# ---------- DB ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def audit(action, detail=""):
    actor = session.get("username")
    get_db().execute(
        "INSERT INTO audit_log (at, actor, action, detail) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), actor, action, detail),
    )
    get_db().commit()


# ---------- 認証・認可 ----------
def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return get_db().execute(
        "SELECT id, username, role, name FROM users WHERE id = ?", (uid,)
    ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def role_required(*roles):
    def deco(view):
        @wraps(view)
        def wrapped(*a, **kw):
            user = current_user()
            if user is None:
                return redirect(url_for("login"))
            if user["role"] not in roles:
                abort(403)
            return view(*a, **kw)
        return wrapped
    return deco


def children_ids(parent_id):
    rows = get_db().execute(
        "SELECT student_id FROM parent_child WHERE parent_id = ?", (parent_id,)
    ).fetchall()
    return {r["student_id"] for r in rows}


def can_view_student(user, student_id):
    """認可の中心。役割ごとに、見てよい生徒かをサーバ側で判定。"""
    role = user["role"]
    if role == "student":
        return user["id"] == student_id
    if role == "parent":
        return student_id in children_ids(user["id"])
    if role in ("teacher", "admin"):
        return True
    return False


# ---------- データ取得 ----------
def get_student(student_id):
    return get_db().execute(
        """SELECT u.id, u.name, s.school
           FROM users u JOIN students s ON s.user_id = u.id
           WHERE u.id = ? AND u.role = 'student'""",
        (student_id,),
    ).fetchone()


def get_scores(student_id):
    rows = get_db().execute(
        "SELECT exam, subject, score FROM scores WHERE student_id = ?",
        (student_id,),
    ).fetchall()
    table = {ex: {} for ex in EXAMS}
    for r in rows:
        table.setdefault(r["exam"], {})[r["subject"]] = r["score"]
    return table


def exam_average(score_table, exam):
    vals = [score_table[exam][s] for s, _ in SUBJECTS if s in score_table.get(exam, {})]
    return round(sum(vals) / len(vals), 1) if vals else None


def latest_average(student_id):
    table = get_scores(student_id)
    for exam in reversed(EXAMS):
        avg = exam_average(table, exam)
        if avg is not None:
            return avg
    return None


def all_students():
    return get_db().execute(
        """SELECT u.id, u.name, s.school
           FROM users u JOIN students s ON s.user_id = u.id
           WHERE u.role = 'student' ORDER BY u.id""").fetchall()


def deviation_values():
    """全生徒の最新平均から偏差値を計算（生徒本人の偏差値表示に使用）。"""
    avgs = {st["id"]: latest_average(st["id"]) for st in all_students()}
    valid = [a for a in avgs.values() if a is not None]
    if len(valid) < 2:
        return {sid: 50.0 for sid in avgs}
    mean = statistics.mean(valid)
    std = statistics.pstdev(valid) or 1.0
    return {sid: round(50 + 10 * (a - mean) / std, 1) if a is not None else None
            for sid, a in avgs.items()}


def build_chart(averages):
    """推移グラフ用の座標を計算（SVG 320x140, 平均0-100を縦軸に）。"""
    w, h, pad = 320, 140, 30
    pts = []
    n = len(EXAMS)
    for i, exam in enumerate(EXAMS):
        val = averages.get(exam)
        x = pad + (w - 2 * pad) * (i / max(1, n - 1))
        y = (h - pad) - (h - 2 * pad) * ((val or 0) / 100)
        pts.append({"x": round(x, 1), "y": round(y, 1),
                    "label": exam, "val": val})
    return {"w": w, "h": h, "pad": pad, "pts": pts}


def pass_probability(student_hensachi, school):
    """運営のみ。生徒偏差値と志望校基準から合格確率(%)。"""
    base = SCHOOL_HENSACHI.get(school)
    if student_hensachi is None or base is None:
        return None
    p = 50 + (student_hensachi - base) * 5
    return max(1, min(99, round(p)))


# ---------- ルート ----------
def register_routes(app):
    app.teardown_appcontext(close_db)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            now = time.time()
            fails = [t for t in _LOGIN_FAILS.get(username, []) if now - t < WINDOW_SEC]
            if len(fails) >= MAX_FAILS:
                audit("login_blocked", username)
                error = "試行回数が多すぎます。しばらく待ってからお試しください。"
                return render_template("login.html", error=error), 429

            from werkzeug.security import check_password_hash
            row = get_db().execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if row and check_password_hash(row["password_hash"], password):
                session.clear()
                session["user_id"] = row["id"]
                session["username"] = row["username"]
                _LOGIN_FAILS.pop(username, None)
                audit("login_success", username)
                return redirect(url_for("index"))
            fails.append(now)
            _LOGIN_FAILS[username] = fails
            audit("login_fail", username)
            error = "IDまたはパスワードが違います。"
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        audit("logout")
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        user = current_user()
        if user["role"] == "student":
            return redirect(url_for("student_page", student_id=user["id"]))
        if user["role"] == "parent":
            return redirect(url_for("children"))
        if user["role"] == "teacher":
            return redirect(url_for("teacher_page"))
        return redirect(url_for("admin_page"))

    @app.route("/children")
    @role_required("parent")
    def children():
        user = current_user()
        ids = children_ids(user["id"])
        kids = [get_student(sid) for sid in ids]
        return render_template("children.html", user=user, kids=kids)

    @app.route("/student/<int:student_id>")
    @login_required
    def student_page(student_id):
        user = current_user()
        if not can_view_student(user, student_id):      # ← 認可の肝
            audit("forbidden_student_view", str(student_id))
            abort(403)
        student = get_student(student_id)
        if student is None:
            abort(404)
        table = get_scores(student_id)
        averages = {ex: exam_average(table, ex) for ex in EXAMS}
        hensachi = deviation_values().get(student_id)
        return render_template(
            "student.html", user=user, student=student, subjects=SUBJECTS,
            exams=EXAMS, table=table, averages=averages, hensachi=hensachi,
            chart=build_chart(averages))

    @app.route("/teacher")
    @role_required("teacher", "admin")
    def teacher_page():
        user = current_user()
        rows = []
        for st in all_students():
            table = get_scores(st["id"])
            rows.append({
                "id": st["id"], "name": st["name"], "school": st["school"],
                "averages": {ex: exam_average(table, ex) for ex in EXAMS},
            })
        return render_template("teacher.html", user=user, exams=EXAMS, rows=rows)

    @app.route("/admin")
    @role_required("admin")
    def admin_page():
        user = current_user()
        audit("view_admin")
        hens = deviation_values()
        rows = []
        for st in all_students():
            table = get_scores(st["id"])
            h = hens.get(st["id"])
            rows.append({
                "id": st["id"], "name": st["name"], "school": st["school"],
                "averages": {ex: exam_average(table, ex) for ex in EXAMS},
                "hensachi": h,
                "prob": pass_probability(h, st["school"]),
            })
        return render_template("admin.html", user=user, exams=EXAMS, rows=rows)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("error.html", code=403,
                               message="このページを見る権限がありません。"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404,
                               message="見つかりませんでした。"), 404


app = create_app()

if __name__ == "__main__":
    # 開発用。本番はWSGI(gunicorn等)で起動する
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")), debug=False)
