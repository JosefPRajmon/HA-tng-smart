"""Převod mezi lidsky čitelným zápisem hodinového rozvrhu ('6-8,16-22')
a polem 24 boolů (True = denní teplota), jak to čeká/vrací tngsmart.cz."""
from __future__ import annotations


def hours_from_ranges(range_str: str) -> list[bool]:
    """'6-8,16-22' -> [False]*6 + [True]*3 + [False]*7 + [True]*7 + [False]."""
    hours = [False] * 24
    range_str = (range_str or "").strip()
    if not range_str:
        return hours

    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)

        start = max(0, min(23, start))
        end = max(0, min(23, end))

        if start <= end:
            for h in range(start, end + 1):
                hours[h] = True
        else:
            # přes půlnoc, např. 22-2
            for h in list(range(start, 24)) + list(range(0, end + 1)):
                hours[h] = True

    return hours


def ranges_from_hours(hours: list[bool]) -> str:
    """Opak hours_from_ranges - pro zobrazení aktuálního rozvrhu."""
    ranges: list[str] = []
    start: int | None = None

    for h in range(24):
        if hours[h] and start is None:
            start = h
        if (not hours[h] or h == 23) and start is not None:
            end = h if hours[h] else h - 1
            ranges.append(f"{start}-{end}" if start != end else f"{start}")
            start = None

    return ",".join(ranges)
