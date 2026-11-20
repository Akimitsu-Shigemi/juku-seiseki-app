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
import secrets
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

# 文系3科目（少科目特化）
SUBJECTS = [("eigo", "英語"), ("kokugo", "国語"), ("sentaku", "選択(地歴公民)")]
SUBJECT_KEYS = {key for key, _ in SUBJECTS}   # 入力検証用のホワイトリスト
# 河合塾 全統模試を想定した回
EXAMS = ["2026-05", "2026-08", "2026-11"]

# 志望校（私立大学・学部）の目安データ。
#   hensachi : 河合塾のボーダー偏差値を参考にした「目安」。年度・方式で変わるため要更新。
#   subjects : その学部の必要科目の「目安」。実際は募集要項で要確認。
# 合格確率・合否判定は先生・運営のみが使う（生徒には合格確率を見せない）。
TARGETS = [
    {"name": "早稲田大学 政治経済学部", "group": "早慶上智ICU", "hensachi": 70.0,
     "subjects": "共通テスト＋学部独自(総合問題)。数学が必須"},
    {"name": "早稲田大学 商学部", "group": "早慶上智ICU", "hensachi": 70.0,
     "subjects": "英語・国語・選択(地歴/数学)"},
    {"name": "慶應義塾大学 経済学部", "group": "早慶上智ICU", "hensachi": 67.5,
     "subjects": "英語・数学or地歴＋小論文（国語なし）"},
    {"name": "慶應義塾大学 商学部", "group": "早慶上智ICU", "hensachi": 67.5,
     "subjects": "英語・地歴＋数学or小論文（国語なし）"},
    {"name": "上智大学 経済学部", "group": "早慶上智ICU", "hensachi": 65.0,
     "subjects": "英語外部試験(TEAP)・共通テスト併用など"},
    {"name": "国際基督教大学(ICU) 教養学部", "group": "早慶上智ICU", "hensachi": 67.5,
     "subjects": "独自試験(総合教養＋人文/社会科学)"},
    {"name": "明治大学 商学部", "group": "MARCH", "hensachi": 62.5,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "明治大学 政治経済学部", "group": "MARCH", "hensachi": 62.5,
     "subjects": "英語・国語・選択(地歴公民/数学)"},
    {"name": "青山学院大学 経営学部", "group": "MARCH", "hensachi": 62.5,
     "subjects": "英語・国語・選択(共通テスト併用の方式あり)"},
    {"name": "立教大学 経営学部", "group": "MARCH", "hensachi": 65.0,
     "subjects": "英語外部試験＋共通テスト＋独自"},
    {"name": "中央大学 商学部", "group": "MARCH", "hensachi": 60.0,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "法政大学 経営学部", "group": "MARCH", "hensachi": 60.0,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "関西大学 経済学部", "group": "関関同立", "hensachi": 57.5,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "関西学院大学 商学部", "group": "関関同立", "hensachi": 57.5,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "同志社大学 商学部", "group": "関関同立", "hensachi": 62.5,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "立命館大学 経営学部", "group": "関関同立", "hensachi": 57.5,
     "subjects": "英語・国語・選択(全学統一方式など)"},
    {"name": "学習院大学 経済学部", "group": "その他", "hensachi": 60.0,
     "subjects": "英語・国語・選択(地歴公民)"},
    {"name": "日本大学 経済学部", "group": "その他", "hensachi": 55.0,
     "subjects": "英語・国語・選択(N方式など)"},
    {"name": "松山大学 経済学部", "group": "その他", "hensachi": 50.0,
     "subjects": "英語・国語・選択(地歴公民)"},
]
TARGET_BY_NAME = {t["name"]: t for t in TARGETS}

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


# ---------- CSRF対策（更新系POST用） ----------
def get_csrf_token():
    """セッションごとのCSRFトークン。無ければ発行する。"""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_ok():
    """POSTのトークンがセッションのトークンと一致するか（タイミング安全に比較）。"""
    sent = request.form.get("csrf_token", "")
    real = session.get("csrf_token", "")
    return bool(real) and secrets.compare_digest(sent, real)


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
        """SELECT u.id, u.name, s.highschool, s.school
           FROM users u JOIN students s ON s.user_id = u.id
           WHERE u.id = ? AND u.role = 'student'""",
        (student_id,),
    ).fetchone()


def target_subjects(school):
    """志望校（大学・学部）の必要科目（目安）。未登録ならNone。"""
    t = TARGET_BY_NAME.get(school)
    return t["subjects"] if t else None


def get_scores(student_id):
    rows = get_db().execute(
        "SELECT exam, subject, score FROM scores WHERE student_id = ?",
        (student_id,),
    ).fetchall()
    table = {ex: {} for ex in EXAMS}
    for r in rows:
        table.setdefault(r["exam"], {})[r["subject"]] = r["score"]
    return table


def save_score(student_id, exam, subject, score):
    """点数を1件、上書き保存する（同じ生徒・回・教科は更新）。
    呼ぶ前に exam/subject/score を検証済みであること。SQLはプレースホルダのみ。"""
    db = get_db()
    db.execute(
        """INSERT INTO scores (student_id, exam, subject, score)
           VALUES (?,?,?,?)
           ON CONFLICT (student_id, exam, subject)
           DO UPDATE SET score = excluded.score""",
        (student_id, exam, subject, score),
    )
    db.commit()


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
    """先生・運営のみ。生徒の偏差値と志望校（大学・学部）の基準偏差値から合格確率(%)。"""
    target = TARGET_BY_NAME.get(school)
    if student_hensachi is None or target is None:
        return None
    p = 50 + (student_hensachi - target["hensachi"]) * 5
    return max(1, min(99, round(p)))


# 判定ランク（河合塾式の目安）。本人の偏差値 − ボーダー偏差値 の差(gap)で決める。
#   gap が大きい（本人がボーダーを上回る）ほど合格に近い。
JUDGE_BANDS = [
    (6.0, "A", "合格圏"),
    (3.0, "B", "合格有望"),
    (0.0, "C", "ボーダー"),
    (-3.0, "D", "要努力"),
]  # これ未満は E（努力圏）


def judgement(student_hensachi, school):
    """先生・運営のみ。本人の偏差値とボーダー偏差値から判定ランクと差を返す。
    gap>0=ボーダーを上回る（届いている）、gap<0=あと何偏差値で届くか。"""
    target = TARGET_BY_NAME.get(school)
    if student_hensachi is None or target is None:
        return None
    gap = round(student_hensachi - target["hensachi"], 1)
    rank, label = "E", "努力圏"
    for threshold, r, l in JUDGE_BANDS:
        if gap >= threshold:
            rank, label = r, l
            break
    return {"rank": rank, "label": label, "gap": gap}


# ---------- ルート ----------
def register_routes(app):
    app.teardown_appcontext(close_db)

    @app.context_processor
    def inject_csrf():
        # テンプレートから {{ csrf_token() }} で使えるようにする
        return {"csrf_token": get_csrf_token}

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
            req_subjects=target_subjects(student["school"]),
            can_judge=user["role"] in ("teacher", "admin"),
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

    @app.route("/teacher/input/<int:student_id>", methods=["GET", "POST"])
    @role_required("teacher", "admin")
    def score_input(student_id):
        # 認可: 入力できるのは先生・運営のみ（デコレータで担保）
        student = get_student(student_id)
        if student is None:
            abort(404)

        error = None
        saved_exam = None
        if request.method == "POST":
            # 1) CSRFトークンの照合（更新系の必須チェック）
            if not csrf_ok():
                audit("score_input_csrf_ng", str(student_id))
                abort(400)

            # 2) 回（exam）はホワイトリストのみ
            exam = request.form.get("exam", "")
            if exam not in EXAMS:
                error = "不正な回が指定されました。"
            else:
                # 3) 各教科の点数を検証（空欄は変更しない）
                to_save = []
                for key in SUBJECT_KEYS:
                    raw = request.form.get("score_" + key, "").strip()
                    if raw == "":
                        continue
                    if not raw.isdigit():        # マイナス・小数・文字を弾く
                        error = "点数は0〜100の整数で入力してください。"
                        break
                    val = int(raw)
                    if not (0 <= val <= 100):
                        error = "点数は0〜100の範囲で入力してください。"
                        break
                    to_save.append((key, val))
                else:
                    # 検証を全部通ったときだけ保存する
                    for key, val in to_save:
                        save_score(student_id, exam, key, val)
                    audit("score_update",
                          f"student={student_id} exam={exam} "
                          f"subjects={','.join(k for k, _ in to_save)}")
                    saved_exam = exam

        table = get_scores(student_id)
        return render_template(
            "score_input.html", user=current_user(), student=student,
            subjects=SUBJECTS, exams=EXAMS, table=table,
            error=error, saved_exam=saved_exam,
        ), (400 if error else 200)

    @app.route("/hantei/<int:student_id>")
    @role_required("teacher", "admin")
    def hantei(student_id):
        # 合否判定: 生徒1人について、各大学・学部の合格確率と必要科目を一覧（先生・運営のみ）
        student = get_student(student_id)
        if student is None:
            abort(404)
        audit("view_hantei", str(student_id))
        hensachi = deviation_values().get(student_id)

        # グループ順にまとめる
        order = ["早慶上智ICU", "MARCH", "関関同立", "その他"]
        groups = {g: [] for g in order}
        for t in TARGETS:
            groups[t["group"]].append({
                "name": t["name"], "hensachi": t["hensachi"],
                "subjects": t["subjects"],
                "prob": pass_probability(hensachi, t["name"]),
                "judge": judgement(hensachi, t["name"]),
            })
        grouped = [(g, groups[g]) for g in order if groups[g]]
        return render_template(
            "hantei.html", user=current_user(), student=student,
            hensachi=hensachi, grouped=grouped)

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
