"""P0 受入テスト（講座Day21のバックログ B01〜B24 に対応）。

考え方（講師のやり方）:
- 設計図と開発バックログをもとに、まず「P0のテスト」を用意する。
- 実装済みの対策は緑（Blue/通過）になり、"効いている証拠" になる。
- まだ実装していないP0項目は、ここで赤（または xfail=想定どおり未達）として見える化する。

このアプリは既に実装済みなので、実装済み項目は緑、未実装項目（例: アカウント無効化）は
xfail として「P0未達」が一目で分かるようにしている。対応表は tests/p0/P0対応表.md。

生徒ID: tanaka=1, nakamura=2, suzuki=3 / 先生 sensei / 運営 unei / 保護者 oya_tanaka(子=tanaka)
"""
import os
import re
import sqlite3

import pytest

from conftest import login


def _db():
    return sqlite3.connect(os.environ["DB_PATH"])


def _csrf(client, url):
    m = re.search(rb'name="csrf_token" value="([^"]+)"', client.get(url).data)
    return m.group(1).decode() if m else None


# ============================================================
# P0完了判定（B24）= 別生徒・別保護者・未ログインからのアクセスを拒否できる
# ============================================================
def test_B24_unauthenticated_is_rejected(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_B24_other_student_is_rejected(client):
    login(client, "tanaka", "sakura123")
    assert client.get("/student/1").status_code == 200   # 自分
    assert client.get("/student/2").status_code == 403   # 別の生徒


def test_B24_other_family_is_rejected(client):
    login(client, "oya_tanaka", "chichi100")
    assert client.get("/student/1").status_code == 200   # 自分の子
    assert client.get("/student/3").status_code == 403   # 別家庭の子


# ============================================================
# B10 共通の権限確認（役割・生徒との関係を毎回検証）
# ============================================================
def test_B10_role_pages_are_guarded(client):
    login(client, "tanaka", "sakura123")
    assert client.get("/teacher").status_code == 403
    assert client.get("/admin").status_code == 403
    assert client.get("/hantei/1").status_code == 403


# ============================================================
# B12 成績登録・修正（担当者の権限・入力値・更新項目を検証）
# ============================================================
def test_B12_only_staff_can_input(client):
    login(client, "tanaka", "sakura123")              # 生徒
    assert client.get("/teacher/input/3").status_code == 403
    r = client.post("/teacher/input/3",
                    data={"exam": "2026-05", "score_kokugo": "10"})
    assert r.status_code == 403


def test_B12_input_is_validated(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    # 範囲外・数字でない・候補外の回は保存しない（400）
    for data in (
        {"exam": "2026-05", "score_kokugo": "150"},
        {"exam": "2026-05", "score_kokugo": "abc"},
        {"exam": "2099-99", "score_kokugo": "50"},
    ):
        data["csrf_token"] = token
        assert client.post("/teacher/input/3", data=data).status_code == 400


def test_B12_csrf_required(client):
    login(client, "sensei", "teacher2026")
    r = client.post("/teacher/input/3",
                    data={"exam": "2026-05", "score_kokugo": "10"})  # トークン無し
    assert r.status_code == 400


# ============================================================
# B16 情報公開範囲の制限（応答に権限外の項目を含めない）
# ============================================================
def test_B16_student_cannot_see_pass_probability(client):
    login(client, "tanaka", "sakura123")
    body = client.get("/student/1").data.decode()
    assert "合格確率" not in body


# ============================================================
# B17 インジェクション対策（入力を命令として実行しない）
# ============================================================
def test_B17_sqli_login_not_bypassed(client):
    for payload in ("' OR '1'='1", "admin'--", "x'; DROP TABLE users;--"):
        login(client, payload, "anything")
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    db = _db()
    n = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    db.close()
    assert n == 12            # テーブルは無傷


# ============================================================
# B08 乗っ取り対策（ログイン試行の回数制限）※MFAは未実装→対応表参照
# ============================================================
def test_B08_login_rate_limited(client):
    last = None
    for _ in range(6):
        last = login(client, "sensei", "wrong-password")
    assert last.status_code == 429   # 6回目はブロック


# ============================================================
# B09 セッション管理（Cookieの安全属性）
# ============================================================
def test_B09_session_cookie_flags(client):
    r = login(client, "sensei", "teacher2026")
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


# ============================================================
# B22 操作履歴（監査ログ）
# ============================================================
def test_B22_login_and_change_are_audited(client):
    login(client, "sensei", "teacher2026")
    token = _csrf(client, "/teacher/input/3")
    client.post("/teacher/input/3",
                data={"csrf_token": token, "exam": "2026-05", "score_kokugo": "80"})
    db = _db()
    actions = [r[0] for r in db.execute("SELECT action FROM audit_log").fetchall()]
    db.close()
    assert "login_success" in actions
    assert "score_update" in actions


# ============================================================
# 【P0未達・未実装】= 想定どおり失敗する（xfail）。実装したらここを緑にする。
# ============================================================
@pytest.mark.xfail(reason="未実装: アカウント無効化(is_active)機能が無い（B07/B24）", strict=True)
def test_B07_disabled_account_cannot_login(client):
    # 本来のP0条件: 無効化した職員・利用者はログインできないこと。
    # 現状 users テーブルに is_active 列が無く、無効化できない → P0未達。
    db = _db()
    cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    db.close()
    assert "is_active" in cols
