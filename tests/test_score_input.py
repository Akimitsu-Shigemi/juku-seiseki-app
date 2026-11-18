"""点数入力機能のテスト。
- 入力できるのは先生・運営だけ（生徒・保護者は拒否）
- CSRFトークンが無いPOSTは拒否
- 不正な点数（0〜100外・数字でない）、候補外の回は保存しない
- 正しい入力は上書き保存され、重複行を作らない
生徒ID: tanaka=1, suzuki=3 / 先生 sensei / 運営 unei / 保護者 oya_tanaka
"""
import os
import re
import sqlite3

from conftest import login


def _csrf(client, url):
    """フォーム画面からCSRFトークンを取り出す。"""
    r = client.get(url)
    m = re.search(rb'name="csrf_token" value="([^"]+)"', r.data)
    return m.group(1).decode() if m else None


def _score(student_id, exam, subject):
    db = sqlite3.connect(os.environ["DB_PATH"])
    row = db.execute(
        "SELECT score FROM scores WHERE student_id=? AND exam=? AND subject=?",
        (student_id, exam, subject)).fetchone()
    db.close()
    return row[0] if row else None


def _count(student_id, exam, subject):
    db = sqlite3.connect(os.environ["DB_PATH"])
    n = db.execute(
        "SELECT COUNT(*) FROM scores WHERE student_id=? AND exam=? AND subject=?",
        (student_id, exam, subject)).fetchone()[0]
    db.close()
    return n


# ---- 認可 ----
def test_teacher_can_open_input(client):
    login(client, "sensei", "teacher2026")
    assert client.get("/teacher/input/1").status_code == 200


def test_admin_can_open_input(client):
    login(client, "unei", "admin0000")
    assert client.get("/teacher/input/1").status_code == 200


def test_student_cannot_open_input(client):
    login(client, "tanaka", "sakura123")
    assert client.get("/teacher/input/1").status_code == 403


def test_parent_cannot_open_input(client):
    login(client, "oya_tanaka", "chichi100")
    assert client.get("/teacher/input/1").status_code == 403


def test_student_cannot_post_score(client):
    login(client, "tanaka", "sakura123")
    before = _score(3, "2026-05", "kokugo")
    r = client.post("/teacher/input/3",
                    data={"exam": "2026-05", "score_kokugo": "10"})
    assert r.status_code == 403
    assert _score(3, "2026-05", "kokugo") == before   # 変わっていない


# ---- CSRF ----
def test_post_without_csrf_rejected(client):
    login(client, "sensei", "teacher2026")
    before = _score(3, "2026-05", "kokugo")
    r = client.post("/teacher/input/3",
                    data={"exam": "2026-05", "score_kokugo": "10"})  # トークン無し
    assert r.status_code == 400
    assert _score(3, "2026-05", "kokugo") == before


# ---- 入力検証 ----
def test_teacher_can_save_and_overwrite(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    r = client.post("/teacher/input/3",
                    data={"csrf_token": token, "exam": "2026-05",
                          "score_kokugo": "88"})
    assert r.status_code == 200
    assert _score(3, "2026-05", "kokugo") == 88
    # もう一度上書きしても重複行にならない
    client.post("/teacher/input/3",
                data={"csrf_token": token, "exam": "2026-05",
                      "score_kokugo": "91"})
    assert _score(3, "2026-05", "kokugo") == 91
    assert _count(3, "2026-05", "kokugo") == 1


def test_boundary_values_ok(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    client.post("/teacher/input/3",
                data={"csrf_token": token, "exam": "2026-08",
                      "score_sentaku": "0", "score_eigo": "100"})
    assert _score(3, "2026-08", "sentaku") == 0
    assert _score(3, "2026-08", "eigo") == 100


def test_out_of_range_rejected(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    before = _score(3, "2026-05", "kokugo")
    r = client.post("/teacher/input/3",
                    data={"csrf_token": token, "exam": "2026-05",
                          "score_kokugo": "150"})
    assert r.status_code == 400
    assert _score(3, "2026-05", "kokugo") == before


def test_non_integer_rejected(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    before = _score(3, "2026-05", "kokugo")
    for bad in ("-5", "7.5", "abc"):
        r = client.post("/teacher/input/3",
                        data={"csrf_token": token, "exam": "2026-05",
                              "score_kokugo": bad})
        assert r.status_code == 400
    assert _score(3, "2026-05", "kokugo") == before


def test_unknown_subject_ignored(client):
    # 候補外の科目フィールドは無視される（ホワイトリスト）
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    r = client.post("/teacher/input/3",
                    data={"csrf_token": token, "exam": "2026-05",
                          "score_sugaku": "77"})      # sugakuは候補外
    assert r.status_code == 200
    assert _score(3, "2026-05", "sugaku") is None     # 保存されない


def test_unknown_exam_rejected(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    r = client.post("/teacher/input/3",
                    data={"csrf_token": token, "exam": "2099-99",
                          "score_kokugo": "50"})
    assert r.status_code == 400
    assert _score(3, "2099-99", "kokugo") is None


def test_empty_field_leaves_score_unchanged(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    before = _score(3, "2026-05", "sentaku")
    client.post("/teacher/input/3",
                data={"csrf_token": token, "exam": "2026-05",
                      "score_kokugo": "70", "score_sentaku": ""})
    assert _score(3, "2026-05", "kokugo") == 70          # 入れた方は更新
    assert _score(3, "2026-05", "sentaku") == before     # 空欄は変更なし
