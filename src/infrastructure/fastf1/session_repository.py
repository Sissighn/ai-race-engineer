import fastf1


def get_session(year: int, grand_prix: str, session_type: str):
    return fastf1.get_session(year, grand_prix, session_type)
