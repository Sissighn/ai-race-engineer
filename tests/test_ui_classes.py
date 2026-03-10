from types import SimpleNamespace

from app.components.glow_card import GlowCard
from app.components.navbar import Navbar


def test_glowcard_render_calls_markdown(monkeypatch):
    calls = []

    def fake_markdown(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("app.components.glow_card.st.markdown", fake_markdown)

    GlowCard.render("Title", "Value")

    assert len(calls) >= 2  # inject CSS/JS + card HTML
    assert any("glow-card-wrapper" in (args[0] if args else "") for args, _ in calls)


def test_navbar_load_asset_missing_returns_empty(monkeypatch):
    nav = Navbar()
    monkeypatch.setattr("app.components.navbar.os.path.exists", lambda _p: False)
    assert nav._load_asset("does_not_exist.txt") == ""


def test_navbar_get_logo_missing_returns_none(monkeypatch):
    nav = Navbar()
    monkeypatch.setattr("app.components.navbar.os.path.exists", lambda _p: False)
    assert nav._get_logo_b64() is None


def test_navbar_render_uses_markdown_when_html_unavailable(monkeypatch):
    nav = Navbar()

    monkeypatch.setattr(
        nav, "_load_asset", lambda name: "<div>{{CSS_STYLE}}{{LOGO_HTML}}</div>"
    )
    monkeypatch.setattr(nav, "_get_logo_b64", lambda: None)

    calls = []

    def fake_markdown(*args, **kwargs):
        calls.append((args, kwargs))

    fake_st = SimpleNamespace(markdown=fake_markdown)
    monkeypatch.setattr("app.components.navbar.st", fake_st)

    nav.render()

    assert len(calls) == 1
    assert "<div>" in calls[0][0][0]
