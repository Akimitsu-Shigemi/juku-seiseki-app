"""セッションCookieの Secure 属性の切替テスト（レッドチーム指摘[中]への対策）。

- ローカル開発(HTTP)では Secure を付けない（付けるとログインできなくなる）。
- 本番(HTTPS)は環境変数 SECURE_COOKIES=1 で Secure を付ける。
"""
import importlib
import os


def _make_app_with(secure_env):
    import app as m
    importlib.reload(m)
    if secure_env is None:
        os.environ.pop("SECURE_COOKIES", None)
    else:
        os.environ["SECURE_COOKIES"] = secure_env
    try:
        return m.create_app()
    finally:
        os.environ.pop("SECURE_COOKIES", None)


def test_secure_cookie_off_by_default():
    # 既定（未設定）はローカルHTTPで動くよう Secure を付けない
    app = _make_app_with(None)
    assert app.config["SESSION_COOKIE_SECURE"] is False
    # HttpOnly / SameSite は常に付く
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_secure_cookie_on_when_env_set():
    # 本番想定: SECURE_COOKIES=1 で Secure が付く
    app = _make_app_with("1")
    assert app.config["SESSION_COOKIE_SECURE"] is True
