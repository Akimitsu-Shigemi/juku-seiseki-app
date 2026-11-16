import os
import sys
import tempfile

import pytest

# テスト用の設定を import 前に用意する
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SECRET_KEY"] = "test-only-secret-key"
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name

import seed  # noqa: E402
seed.DB_PATH = _tmp.name


@pytest.fixture()
def client():
    seed.main()                       # 毎回クリーンなダミーデータ
    import importlib
    import app as app_module
    importlib.reload(app_module)
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c
    os.path.exists(_tmp.name) and os.remove(_tmp.name)


def login(client, username, password):
    return client.post("/login",
                       data={"username": username, "password": password},
                       follow_redirects=False)
