import pandas as pd

def coaching_suggestions(df: pd.DataFrame, driver_a: str, driver_b: str):
    """
    Generate automatic improvement suggestions based on:
    - Time loss
    - Entry / Apex / Exit speed deficits
    - Brake / Throttle behavior
    """

    suggestions = []

    for _, row in df.iterrows():
        c = int(row["Corner"])
        loss = row["TimeLoss"]   # positive = Aahead, negative = B ahead

        entry = row["Delta_EntrySpeed"]
        apex  = row["Delta_ApexSpeed"]
        exit  = row["Delta_ExitSpeed"]
        brake = row["Delta_AvgBrake"]
        throt = row["Delta_ThrottleBelow30Pct"]

        # Determine who needs advice
        if loss < 0:  
            losing_driver = driver_a
            winning_driver = driver_b
        elif loss > 0:
            losing_driver = driver_b
            winning_driver = driver_a
        else:
            continue

        line = f"Corner {c} – {losing_driver}: "

        # EXIT SPEED – höchste Priorität
        if abs(exit) > 1.0:
            if losing_driver == driver_a and exit < 0:
                line += "Improve exit acceleration. Consider earlier throttle commitment and smoother rotation. "
            elif losing_driver == driver_b and exit > 0:
                line += "Improve exit acceleration. Focus on earlier throttle application and reducing hesitation. "

        # APEX SPEED
        if abs(apex) > 1.0:
            if losing_driver == driver_a and apex < 0:
                line += "Increase apex speed. Possible later turn-in, less brake pressure at rotation point. "
            elif losing_driver == driver_b and apex > 0:
                line += "Increase apex speed. Commit more to mid-corner rotation and carry more minimum speed. "

        # ENTRY SPEED
        if abs(entry) > 1.0:
            if losing_driver == driver_a and entry < 0:
                line += "Raise entry speed by braking slightly later and reducing pre-apex conservatism. "
            elif losing_driver == driver_b and entry > 0:
                line += "Raise entry speed by braking later and reducing early brake-phase. "

        # BRAKING BEHAVIOR
        if abs(brake) > 0.1:
            if losing_driver == driver_a and brake < 0:
                line += "Increase brake pressure stability to shorten braking phase. "
            elif losing_driver == driver_b and brake > 0:
                line += "Optimize brake pressure modulation to avoid over-braking. "

        # THROTTLE HESITATION
        if abs(throt) > 0.05:
            if losing_driver == driver_a and throt < 0:
                line += "Reduce throttle hesitation at the exit. "
            elif losing_driver == driver_b and throt > 0:
                line += "Minimize coasting time after apex. "

        if line.strip() != f"Corner {c} – {losing_driver}:":
            suggestions.append(line.strip())

    return suggestions
