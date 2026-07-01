"""Request-guard auth: disabled by default; when a token is configured the API requires it
(Bearer or X-Auth-Token), with /health exempt."""


def _reset(monkeypatch, token=None):
    if token is None:
        monkeypatch.delenv("LU_AUTH_TOKEN", raising=False)
    else:
        monkeypatch.setenv("LU_AUTH_TOKEN", token)
    from lucore.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_auth_disabled_allows_everything(monkeypatch):
    _reset(monkeypatch, None)
    from luapi.guard import check_auth

    assert check_auth("/stocks/NVDA/quote", {}) is True


def test_auth_required_when_token_set(monkeypatch):
    _reset(monkeypatch, "s3cret")
    from luapi.guard import check_auth

    assert check_auth("/stocks/x", {}) is False                                  # missing
    assert check_auth("/stocks/x", {"x-auth-token": "s3cret"}) is True           # header
    assert check_auth("/stocks/x", {"authorization": "Bearer s3cret"}) is True   # bearer
    assert check_auth("/stocks/x", {"authorization": "Bearer nope"}) is False    # wrong
    assert check_auth("/stocks/x", {"x-auth-token": "nope"}) is False
    assert check_auth("/health", {}) is True                                      # exempt
