from app.pages.home.results_section import _resolve_current_event_index


def test_resolve_current_event_index_uses_active_started_event():
    started_events = [
        {"OfficialEventName": "Canadian Grand Prix"},
        {"OfficialEventName": "Monaco Grand Prix"},
    ]

    index = _resolve_current_event_index(started_events, "Monaco Grand Prix")

    assert index == 1


def test_resolve_current_event_index_falls_back_to_latest_started_event():
    started_events = [
        {"OfficialEventName": "Canadian Grand Prix"},
        {"OfficialEventName": "Monaco Grand Prix"},
    ]

    index = _resolve_current_event_index(started_events, "Spanish Grand Prix")

    assert index == 1
