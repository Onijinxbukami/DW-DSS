"""
Model 1 – DPD-Based Channel Assignment (Decision Under Certainty)
Maps current DPD to a collection channel.
"""


def assign_channel(dpd: int) -> tuple[str, str]:
    """
    Returns (dpd_bucket, assigned_channel).

    DPD=0       → ON_TIME / NONE
    1-9         → A / EMAIL
    10-19       → B / SMS
    20-29       → C / CALL
    ≥30         → D / FIELD
    """
    dpd = int(dpd) if dpd else 0
    if dpd <= 0:
        return ("ON_TIME", "NONE")
    elif dpd <= 9:
        return ("A", "EMAIL")
    elif dpd <= 19:
        return ("B", "SMS")
    elif dpd <= 29:
        return ("C", "CALL")
    else:
        return ("D", "FIELD")


CHANNEL_TO_TEAM = {
    "EMAIL": "EMAIL_SMS",
    "SMS":   "EMAIL_SMS",
    "CALL":  "CALL",
    "FIELD": "FIELD",
    "NONE":  None,
}
