import pandas as pd

from app.components.results_view import clean_position, format_f1_time, render_f1_table


def test_clean_position_valid_and_invalid():
    assert clean_position("1") == 1
    assert clean_position("1.0") == 1
    assert clean_position("DNF") == "DNF"


def test_format_f1_time_formats_expected_pattern():
    formatted = format_f1_time("0 days 00:25:09.054000")
    assert formatted == "25:09.054"


def test_render_f1_table_empty_returns_placeholder_html():
    html = render_f1_table(pd.DataFrame(), "Race")
    assert "No data yet." in html
    assert "glow-large" in html


def test_render_f1_table_formats_columns_and_returns_table():
    df = pd.DataFrame(
        {
            "Position": ["1.0", "2.0"],
            "Abbreviation": ["VER", "HAM"],
            "Time": ["0 days 00:25:09.054000", "0 days 00:25:10.120000"],
            "Status": ["Finished", "Finished"],
        }
    )

    html = render_f1_table(df, "Qualifying")

    assert "Qualifying" in html
    assert "VER" in html
    assert "25:09.054" in html
    assert "Status" not in html


def test_render_f1_table_handles_to_html_error(monkeypatch):
    df = pd.DataFrame({"Position": [1], "Abbreviation": ["VER"]})

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(pd.DataFrame, "to_html", raise_error)

    html = render_f1_table(df, "Race")
    assert "Could not render table." in html
