import re
from datetime import date, datetime, timedelta

from monday_client import MondayClient
from outlook_client import OutlookClient


class PTOProcessor:
    def __init__(self, outlook: OutlookClient, monday: MondayClient):
        self.outlook = outlook
        self.monday = monday

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def process_new_events(self) -> None:
        """Poll for new Travel calendar events and process any PTO ones."""
        events = self.outlook.get_new_events()
        print(f"Found {len(events)} new/changed event(s) in Travel calendar.")
        for event in events:
            self._handle_event(event)

    def process_event_by_id(self, event_id: str) -> None:
        """Process a single event by its Graph event ID (used from webhook)."""
        event = self.outlook.get_event(event_id)
        self._handle_event(event)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _handle_event(self, event: dict) -> None:
        subject = event.get("subject", "")
        label = _match_type(subject)
        if label is None:
            print(f"  Skipping (not PTO / Flex Friday): '{subject}'")
            return

        person = _extract_person(subject)
        start_date, end_date = _parse_dates(event)
        total_hours = _business_hours(start_date, end_date, event)

        if total_hours <= 0:
            print(f"  Skipping '{subject}': calculated 0 hours.")
            return

        date_label = (
            start_date.isoformat()
            if start_date == end_date
            else f"{start_date.isoformat()} – {end_date.isoformat()}"
        )
        notes = f"{label}: {date_label}"
        print(f"  {label} detected → {person} | {total_hours}h | {date_label}")

        # PTO may span multiple months – create one subitem per month
        for month_name, hours, month_start in _split_by_month(start_date, end_date, total_hours, event):
            item_id = self.monday.find_pto_item_for_month(month_name)
            if item_id is None:
                print(f"  WARNING: No '02 - PTO' row found for {month_name} on the Resourcing Board.")
                continue
            sub_id = self.monday.upsert_pto_subitem(
                parent_item_id=item_id,
                person_name=person,
                hours=hours,
                start_date=month_start.isoformat(),
                notes=notes,
            )
            print(f"  ✓ Monday.com updated → {month_name} | subitem #{sub_id} | {hours}h")


# ------------------------------------------------------------------
# Pure helpers (no I/O)
# ------------------------------------------------------------------

_KEYWORD_RE = re.compile(r'\bflex\s*friday\b|\bPTO\b', re.IGNORECASE)


def _match_type(subject: str) -> str | None:
    """Return 'PTO' or 'Flex Friday' if the subject matches, else None."""
    m = _KEYWORD_RE.search(subject)
    if not m:
        return None
    return "PTO" if m.group(0).upper() == "PTO" else "Flex Friday"


def _extract_person(subject: str) -> str:
    # Strip the keyword and common separators, leaving the name
    name = _KEYWORD_RE.sub('', subject)
    name = re.sub(r'^[\s\-–—:,]+|[\s\-–—:,]+$', '', name)
    return name.strip() or subject.strip()


def _parse_dates(event: dict) -> tuple[date, date]:
    def _to_date(val: dict) -> date:
        if "date" in val:
            return date.fromisoformat(val["date"])
        return datetime.fromisoformat(val["dateTime"].rstrip("Z")).date()

    start = _to_date(event["start"])
    end = _to_date(event["end"])

    # All-day end dates in Graph are exclusive (e.g. a 1-day event ends the next day)
    is_all_day = "date" in event.get("start", {})
    if is_all_day and end > start:
        end -= timedelta(days=1)

    return start, end


def _business_hours(start: date, end: date, event: dict) -> float:
    is_all_day = "date" in event.get("start", {})

    if is_all_day:
        return _count_weekdays(start, end) * 8.0

    # Timed event: use actual duration in hours
    dt_start = datetime.fromisoformat(event["start"]["dateTime"].rstrip("Z"))
    dt_end = datetime.fromisoformat(event["end"]["dateTime"].rstrip("Z"))
    return round((dt_end - dt_start).total_seconds() / 3600, 2)


def _count_weekdays(start: date, end: date) -> int:
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon–Fri
            count += 1
        current += timedelta(days=1)
    return count


def _split_by_month(
    start: date, end: date, total_hours: float, event: dict
) -> list[tuple[str, float, date]]:
    """
    Split a PTO range across calendar months, proportioning hours by weekday count.
    Returns [(month_name, hours, first_date_in_month), ...].
    """
    if start.year == end.year and start.month == end.month:
        month_name = start.strftime("%B %Y")
        return [(month_name, total_hours, start)]

    total_days = _count_weekdays(start, end)
    if total_days == 0:
        return []

    results: list[tuple[str, float, date]] = []
    cursor = start
    while cursor <= end:
        # Find end of current month within the range
        if cursor.month == 12:
            month_end = date(cursor.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(cursor.year, cursor.month + 1, 1) - timedelta(days=1)
        segment_end = min(end, month_end)

        days_in_segment = _count_weekdays(cursor, segment_end)
        hours_in_segment = round(total_hours * days_in_segment / total_days, 2)
        if hours_in_segment > 0:
            results.append((cursor.strftime("%B %Y"), hours_in_segment, cursor))

        cursor = segment_end + timedelta(days=1)

    return results
