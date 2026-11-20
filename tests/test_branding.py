"""塾ブランド（塾名・タグライン・コンセプト文）の表示テスト。"""
from conftest import login


def test_login_page_shows_concept(client):
    body = client.get("/login").data.decode()
    assert "今治一点突破ゼミナール" in body          # 塾名
    assert "英語・国語・政治経済" in body            # 3科目の説明
    assert "156人中149位" in body                    # 実話の数字
    assert "明治" in body                            # 結果


def test_header_shows_juku_name(client):
    # ログイン後の各ページ共通ヘッダーにも塾名が出る
    login(client, "sensei", "teacher2026")
    body = client.get("/teacher").data.decode()
    assert "今治一点突破ゼミナール" in body
