"""合否判定ページ（生徒個別の合格確率）の認可テスト。
合格確率は先生・運営だけが見られる。生徒・保護者は見られない。
生徒ID: tanaka=1, suzuki=3 / 先生 sensei / 運営 unei / 保護者 oya_tanaka
"""
from conftest import login


def test_teacher_can_see_hantei(client):
    login(client, "sensei", "teacher2026")
    r = client.get("/hantei/3")
    assert r.status_code == 200
    assert "合格確率" in r.data.decode()


def test_admin_can_see_hantei(client):
    login(client, "unei", "admin0000")
    assert client.get("/hantei/3").status_code == 200


def test_student_cannot_see_hantei(client):
    login(client, "tanaka", "sakura123")
    # 自分の判定でも、生徒は合格確率を見られない
    assert client.get("/hantei/1").status_code == 403


def test_parent_cannot_see_hantei(client):
    login(client, "oya_tanaka", "chichi100")
    assert client.get("/hantei/1").status_code == 403


def test_hantei_requires_login(client):
    r = client.get("/hantei/1", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
