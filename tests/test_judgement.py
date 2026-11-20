"""判定ランク＋あと偏差値（合否判定ページの追加機能）のテスト。

ロジック:
- 本人の偏差値 − ボーダー偏差値 = gap。
- gap>=6:A合格圏 / >=3:B合格有望 / >=0:C ボーダー / >=-3:D要努力 / それ未満:E努力圏。
- 判定は先生・運営のみ閲覧（生徒・保護者には出さない）。
生徒ID: tanaka=1, suzuki=3 / 先生 sensei / 運営 unei / 保護者 oya_tanaka
"""
import importlib

from conftest import login


def _app():
    import app as app_module
    return importlib.reload(app_module)


# ---- ロジック（純粋関数）----
def test_judge_rank_boundaries():
    m = _app()
    # ボーダー65.0の学部を使う（上智 経済 / 立教 経営 など）
    school = "上智大学 経済学部"
    assert m.TARGET_BY_NAME[school]["hensachi"] == 65.0
    cases = {
        72.0: "A",   # +7.0
        68.0: "B",   # +3.0
        65.0: "C",   # +0.0
        63.0: "D",   # -2.0
        60.0: "E",   # -5.0
    }
    for hensachi, rank in cases.items():
        assert m.judgement(hensachi, school)["rank"] == rank


def test_judge_gap_value():
    m = _app()
    school = "上智大学 経済学部"          # ボーダー65.0
    j = m.judgement(61.0, school)
    assert j["gap"] == -4.0              # あと偏差値4.0
    assert j["rank"] == "E"
    j2 = m.judgement(70.0, school)
    assert j2["gap"] == 5.0              # 届いている(+5.0)
    assert j2["rank"] == "B"


def test_judge_none_when_no_hensachi():
    m = _app()
    assert m.judgement(None, "上智大学 経済学部") is None
    assert m.judgement(65.0, "存在しない大学") is None


# ---- 画面表示（権限込み）----
def test_teacher_sees_rank_on_hantei(client):
    login(client, "sensei", "teacher2026")
    body = client.get("/hantei/1").data.decode()
    assert "判定" in body
    # ランク（A〜E いずれか）と差の表記が出る
    assert any(f">{r}<" in body for r in ["A", "B", "C", "D", "E"])
    assert ("あと" in body) or ("届いている" in body)


def test_student_cannot_see_rank(client):
    # 生徒は合否判定ページ自体に入れない（判定ランクも見えない）
    login(client, "tanaka", "sakura123")
    assert client.get("/hantei/1").status_code == 403
    # 生徒ページ本文にも判定ランクの文言は出ない
    body = client.get("/student/1").data.decode()
    assert "合格圏" not in body
    assert "努力圏" not in body
