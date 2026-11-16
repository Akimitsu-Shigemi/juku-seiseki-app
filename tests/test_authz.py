"""認可（誰が何を見てよいか）のテスト。本アプリの肝。
生徒ID: tanaka=1, nakamura=2, suzuki=3 ... / 保護者 oya_tanaka の子は tanaka(1)
"""
from conftest import login


def test_login_required(client):
    # 未ログインはログイン画面へ
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_wrong_password_rejected(client):
    login(client, "tanaka", "wrong-password")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_student_sees_only_self(client):
    login(client, "tanaka", "sakura123")
    assert client.get("/student/1").status_code == 200       # 自分
    assert client.get("/student/2").status_code == 403       # 他人は不可


def test_parent_sees_only_own_child(client):
    login(client, "oya_tanaka", "chichi100")
    assert client.get("/student/1").status_code == 200       # 自分の子
    assert client.get("/student/2").status_code == 403       # よその子は不可


def test_teacher_sees_all_but_not_admin(client):
    login(client, "sensei", "teacher2026")
    assert client.get("/teacher").status_code == 200
    assert client.get("/student/5").status_code == 200       # 全生徒OK
    assert client.get("/admin").status_code == 403           # 運営専用は不可


def test_student_cannot_open_admin(client):
    login(client, "tanaka", "sakura123")
    assert client.get("/admin").status_code == 403
    assert client.get("/teacher").status_code == 403


def test_admin_sees_admin(client):
    login(client, "unei", "admin0000")
    assert client.get("/admin").status_code == 200
