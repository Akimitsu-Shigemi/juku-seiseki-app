"""「対策が効いていること」を証明するテスト（講座Day21の考え方）。
実装しただけでは不十分で、効いている証拠＝テストがBlue(緑)になることを示す。

対象:
- 監査ログ（B22）：ログイン・点数変更が記録される
- SQLインジェクション対策（B17）：悪意ある入力でログイン突破・テーブル破壊ができない
- XSS対策（B25）：保存された文字列がそのままHTMLに出ず、エスケープされる
- P0完了判定（B24）：別生徒・別保護者・未ログインからのアクセスを拒否できる

生徒ID: tanaka=1, nakamura=2, suzuki=3 / 先生 sensei / 運営 unei / 保護者 oya_tanaka(子=tanaka)
"""
import os
import re
import sqlite3

from conftest import login


def _db():
    return sqlite3.connect(os.environ["DB_PATH"])


def _audit(action):
    db = _db()
    rows = db.execute(
        "SELECT actor, action, detail FROM audit_log WHERE action = ?",
        (action,)).fetchall()
    db.close()
    return rows


def _csrf(client, url):
    m = re.search(rb'name="csrf_token" value="([^"]+)"', client.get(url).data)
    return m.group(1).decode() if m else None


# ---- 監査ログ（B22）----
def test_login_success_is_audited(client):
    login(client, "sensei", "teacher2026")
    rows = _audit("login_success")
    assert any(r[0] == "sensei" for r in rows)      # actor が記録されている


def test_login_fail_is_audited(client):
    login(client, "sensei", "wrong-password")
    assert len(_audit("login_fail")) >= 1           # 失敗も記録される


def test_score_update_is_audited(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    client.post("/teacher/input/3",
                data={"csrf_token": token, "exam": "2026-05",
                      "score_kokugo": "80"})
    rows = _audit("score_update")
    assert any("student=3" in (r[2] or "") for r in rows)   # 誰のを変えたか残る


# ---- SQLインジェクション対策（B17）----
def test_sqli_login_not_bypassed(client):
    # 典型的な突破ペイロードでログインできない（プレースホルダなので文字列として扱われる）
    for payload in ("' OR '1'='1", "admin'--", "' OR 1=1--", "\" OR \"\"=\""):
        login(client, payload, "anything")
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_sqli_does_not_destroy_table(client):
    # テーブル破壊を狙う入力でも users テーブルは無傷（命令として実行されない）
    login(client, "x'; DROP TABLE users;--", "anything")
    db = _db()
    n = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    db.close()
    assert n == 12          # 生徒8＋保護者2＋先生1＋運営1


# ---- XSS対策（B25）----
def test_stored_xss_is_escaped(client):
    # 悪意あるスクリプト文字列を名前として保存しても、そのままHTMLに出ない
    payload = "<script>alert(1)</script>"
    db = _db()
    db.execute("UPDATE users SET name = ? WHERE id = 3", (payload,))
    db.commit()
    db.close()

    login(client, "sensei", "teacher2026")
    body = client.get("/teacher").data.decode()
    assert payload not in body                      # 生のタグは出ない
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body   # エスケープ済み


# ---- P0完了判定（B24）受入テスト ----
def test_p0_acceptance_rejects_others(client):
    # 未ログインは入れない
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["Location"]

    # 別の生徒の成績に届かない
    login(client, "tanaka", "sakura123")
    assert client.get("/student/2").status_code == 403

    # 別家庭の子に届かない（oya_tanaka の子は tanaka=1 のみ）
    login(client, "oya_tanaka", "chichi100")
    assert client.get("/student/3").status_code == 403


def test_student_page_hides_pass_probability(client):
    # 生徒の画面に合格確率（運営・先生専用）が漏れていない（B16）
    login(client, "tanaka", "sakura123")
    body = client.get("/student/1").data.decode()
    assert "合格確率" not in body
