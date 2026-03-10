from app.components.report_view import render_race_engineer_report


def test_render_race_engineer_report_no_data_returns(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.components.report_view.st.markdown", lambda *a, **k: calls.append((a, k))
    )

    render_race_engineer_report(None)

    assert calls == []


def test_render_race_engineer_report_renders_html(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.components.report_view.st.markdown", lambda *a, **k: calls.append((a, k))
    )

    render_race_engineer_report(
        {
            "headline": "**Headline**",
            "type_summary": ["**A**", "B"],
            "key_fix": "**Fix**",
        }
    )

    assert len(calls) >= 2
    rendered_html = calls[-1][0][0]
    assert "<b>Headline</b>" in rendered_html
    assert "RACE ENGINEER SUMMARY" in rendered_html


def test_render_race_engineer_report_handles_markdown_error(monkeypatch):
    state = {"count": 0, "warned": False}

    def flaky_markdown(*_args, **_kwargs):
        state["count"] += 1
        if state["count"] >= 2:
            raise RuntimeError("markdown failed")

    monkeypatch.setattr("app.components.report_view.st.markdown", flaky_markdown)
    monkeypatch.setattr(
        "app.components.report_view.st.warning",
        lambda *_a, **_k: state.__setitem__("warned", True),
    )

    render_race_engineer_report(
        {"headline": "H", "type_summary": ["A"], "key_fix": "K"}
    )

    assert state["warned"] is True
