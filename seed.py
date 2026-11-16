"""DBを作り直してダミーデータを投入する。
使い方:  python seed.py
※学習用のダミーデータのみ。実在の個人情報は入れない（SECURITY.md）。
"""
import os
import sqlite3

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "seiseki.db"))
SCHEMA = os.path.join(BASE_DIR, "schema.sql")

EXAMS = ["2026-04", "2026-07", "2026-10"]
SUBJECTS = ["kokugo", "sugaku", "eigo", "rika", "shakai"]
SUBJECT_OFFSET = {"kokugo": 2, "sugaku": -1, "eigo": 1, "rika": 0, "shakai": 3}

# 生徒: (username, password, 氏名, 志望校, 基準点, 伸び)
STUDENTS = [
    ("tanaka",   "sakura123", "田中さくら", "今治西高校",  78,  4),
    ("nakamura", "hana0202",  "中村はな",   "今治西高校",  72,  3),
    ("suzuki",   "ren2026",   "鈴木れん",   "今治北高校",  64,  5),
    ("takahashi","yuto0510",  "高橋ゆうと", "今治北高校",  60,  2),
    ("ito",      "mei1111",   "伊藤めい",   "今治南高校",  52,  4),
    ("yamamoto", "sora7788",  "山本そら",   "今治南高校",  48,  6),
    ("kobayashi","aoi3344",   "小林あおい", "今治工業高校",44,  3),
    ("kato",     "riku9900",  "加藤りく",   "今治明徳高校",40,  5),
]

# 保護者: (username, password, 氏名, 子のusername)
PARENTS = [
    ("oya_tanaka", "chichi100", "田中保護者", "tanaka"),
    ("oya_suzuki", "haha200",   "鈴木保護者", "suzuki"),
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
    for username, pw, name, school, base, growth in STUDENTS:
        uid = add_user(username, pw, "student", name)
        ids[username] = uid
        db.execute("INSERT INTO students (user_id, school) VALUES (?,?)", (uid, school))
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
