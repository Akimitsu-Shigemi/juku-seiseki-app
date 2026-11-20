"""DBを作り直してダミーデータを投入する。
使い方:  python seed.py
※学習用のダミーデータのみ。実在の個人情報は入れない（SECURITY.md）。
※私立大学・文系特化版。出身高校は今治市の高校名（表示用のダミー）、志望は大学・学部。
"""
import os
import sqlite3

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "seiseki.db"))
SCHEMA = os.path.join(BASE_DIR, "schema.sql")

# 河合塾 全統模試を想定した回
EXAMS = ["2026-05", "2026-08", "2026-11"]
# 文系3科目
SUBJECTS = ["eigo", "kokugo", "sentaku"]
SUBJECT_OFFSET = {"eigo": 3, "kokugo": 0, "sentaku": 1}

# 生徒: (username, password, 氏名, 出身高校(今治), 第一志望(大学・学部), 基準点, 伸び)
# 氏名は今治に多い名字（越智・村上・檜垣・渡部ほか）にしている。
# ログインID(username)・パスワードは従来どおり（テスト互換のため変更しない）。
STUDENTS = [
    ("tanaka",   "sakura123", "越智さくら", "今治西高校",   "早稲田大学 商学部",   72, 3),
    ("nakamura", "hana0202",  "村上はな",   "今治西高校",   "早稲田大学 商学部", 70, 3),
    ("suzuki",   "ren2026",   "檜垣れん",   "今治北高校",   "明治大学 商学部",     63, 4),
    ("takahashi","yuto0510",  "渡部ゆうと", "今治東高校",   "立教大学 経営学部",   60, 3),
    ("ito",      "mei1111",   "白石めい",   "今治南高校",   "中央大学 商学部",     55, 4),
    ("yamamoto", "sora7788",  "門田そら",   "今治北高校",   "同志社大学 商学部",   58, 3),
    ("kobayashi","aoi3344",   "菅あおい",   "今治明徳高校", "日本大学 経済学部",   48, 3),
    ("kato",     "riku9900",  "日野りく",   "今治南高校",   "松山大学 経済学部",   44, 5),
]

# 保護者: (username, password, 氏名, 子のusername)
PARENTS = [
    ("oya_tanaka", "chichi100", "越智保護者", "tanaka"),
    ("oya_suzuki", "haha200",   "檜垣保護者", "suzuki"),
]

TEACHER = ("sensei", "teacher2026", "山田先生")
ADMIN = ("unei", "admin0000", "運営")


def gen_scores(base, growth):
    out = []
    for i, exam in enumerate(EXAMS):
        for sub in SUBJECTS:
            s = base + growth * i + SUBJECT_OFFSET[sub]
            s = max(0, min(100, s))
            out.append((exam, sub, s))
    return out


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    with open(SCHEMA, encoding="utf-8") as f:
        db.executescript(f.read())

    def add_user(username, password, role, name):
        cur = db.execute(
            "INSERT INTO users (username, password_hash, role, name) VALUES (?,?,?,?)",
            (username, generate_password_hash(password), role, name),
        )
        return cur.lastrowid

    ids = {}
    for username, pw, name, highschool, school, base, growth in STUDENTS:
        uid = add_user(username, pw, "student", name)
        ids[username] = uid
        db.execute(
            "INSERT INTO students (user_id, highschool, school) VALUES (?,?,?)",
            (uid, highschool, school))
        for exam, sub, score in gen_scores(base, growth):
            db.execute(
                "INSERT INTO scores (student_id, exam, subject, score) VALUES (?,?,?,?)",
                (uid, exam, sub, score))

    for username, pw, name, child in PARENTS:
        pid = add_user(username, pw, "parent", name)
        db.execute("INSERT INTO parent_child (parent_id, student_id) VALUES (?,?)",
                   (pid, ids[child]))

    add_user(TEACHER[0], TEACHER[1], "teacher", TEACHER[2])
    add_user(ADMIN[0], ADMIN[1], "admin", ADMIN[2])

    db.commit()
    db.close()
    print(f"seeded: {DB_PATH}")
    print(f"生徒 {len(STUDENTS)}人 / 保護者 {len(PARENTS)}人 / 先生1 / 運営1")


if __name__ == "__main__":
    main()
