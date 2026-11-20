"""政経受験可否（○/△/×）の組み込みテスト。

- 全19校に seikei(○/△/×) が設定されている（要確認を残さない）。
- 既知の値が正しい（明治=○、慶應=×、青学=△ など）。
- 合否判定ページ（先生・運営）に政経の○×が出る。
- 生徒ページに「政治・経済で受験」が出る。
生徒ID: tanaka=1(早稲田商→○), suzuki=3 / 先生 sensei / 運営 unei
"""
import importlib

from conftest import login


def _app():
    import app as app_module
    return importlib.reload(app_module)


# ---- データ ----
def test_all_targets_have_seikei():
    m = _app()
    assert len(m.TARGETS) == 19
    for t in m.TARGETS:
        assert t.get("seikei") in ("○", "△", "×"), t["name"]


def test_known_seikei_values():
    m = _app()
    expect = {
        "明治大学 商学部": "○",
        "明治大学 政治経済学部": "○",
        "慶應義塾大学 経済学部": "×",
        "慶應義塾大学 商学部": "×",
        "早稲田大学 政治経済学部": "×",
        "早稲田大学 商学部": "○",
        "青山学院大学 経営学部": "△",
        "関西学院大学 商学部": "×",
    }
    for name, mark in expect.items():
        assert m.TARGET_BY_NAME[name]["seikei"] == mark, name


def test_seikei_counts():
    m = _app()
    marks = [t["seikei"] for t in m.TARGETS]
    assert marks.count("○") + marks.count("△") == 13   # 個別で政経可（条件付き含む）
    assert marks.count("×") == 6


def test_target_seikei_helper():
    m = _app()
    assert m.target_seikei("明治大学 商学部")["mark"] == "○"
    assert m.target_seikei("慶應義塾大学 経済学部")["mark"] == "×"
    assert m.target_seikei("存在しない大学") is None


# ---- 画面表示 ----
def test_hantei_shows_seikei(client):
    login(client, "sensei", "teacher2026")
    body = client.get("/hantei/1").data.decode()
    assert "政経" in body            # 列見出し
    assert "共テ利用のみ" in body     # ×の理由メモが出る


def test_student_page_shows_seikei(client):
    # tanaka(1)の第一志望は早稲田商=○
    login(client, "tanaka", "sakura123")
    body = client.get("/student/1").data.decode()
    assert "政治・経済で受験" in body
