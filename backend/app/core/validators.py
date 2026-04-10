def validate_self_assessment_tags(task_entries_data: list) -> None:
    """
    For each task entry, ensure exactly one tag has is_primary=True.
    Raises ValueError with descriptive message if invalid.
    """
    for i, entry in enumerate(task_entries_data):
        if hasattr(entry, "self_assessment_tags"):
            tags = entry.self_assessment_tags or []
            primary_count = sum(1 for t in tags if t.is_primary)
            description = getattr(entry, "task_description", "")
        else:
            tags = entry.get("self_assessment_tags", [])
            primary_count = sum(1 for t in tags if t.get("is_primary", False))
            description = entry.get("task_description", "")

        if primary_count == 0:
            raise ValueError(
                f"Task entry {i + 1} ('{description}') has no primary self-assessment tag. "
                "Exactly one must be marked primary."
            )
        if primary_count > 1:
            raise ValueError(
                f"Task entry {i + 1} ('{description}') has {primary_count} primary tags. "
                "Exactly one must be marked primary."
            )
