from datetime import timedelta

def due_dates(next_due, until, interval_days, limit=12):
    """Fixed-calendar schedule. Backlog is retained, never silently skipped."""
    if not 1 <= interval_days <= 3650:
        raise ValueError('Interval harus 1 sampai 3650 hari.')
    dates = []
    while next_due <= until and len(dates) < limit:
        dates.append(next_due)
        next_due += timedelta(days=interval_days)
    return dates, next_due
