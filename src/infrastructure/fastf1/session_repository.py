import fastf1


def get_session(year: int, grand_prix: str, session_type: str):
    """Get a FastF1 session object.

    Args:
        year: Championship season year.
        grand_prix: Grand Prix name or location.
        session_type: Session type code (Q, R, FP1, FP2, FP3, S).

    Returns:
        FastF1 Session object (not yet loaded).
    """
    return fastf1.get_session(year, grand_prix, session_type)
