def validate_self_assessment_tags(daily_work_logs_data: list) -> None:
    """
    For each daily work log, ensure exactly one tag has is_primary=True.
    Raises ValueError with descriptive message if invalid.
    """
    for i, log in enumerate(daily_work_logs_data):
        if hasattr(log, "self_assessment_tags"):
            tags = log.self_assessment_tags or []
            primary_count = sum(1 for t in tags if t.is_primary)
            note = getattr(log, "work_note", "") or ""
        else:
            tags = log.get("self_assessment_tags", [])
            primary_count = sum(1 for t in tags if t.get("is_primary", False))
            note = log.get("work_note", "") or ""

        if primary_count == 0:
            raise ValueError(
                f"Work log {i + 1} ('{note}') has no primary self-assessment tag. "
                "Exactly one must be marked primary."
            )
        if primary_count > 1:
            raise ValueError(
                f"Work log {i + 1} ('{note}') has {primary_count} primary tags. "
                "Exactly one must be marked primary."
            )
