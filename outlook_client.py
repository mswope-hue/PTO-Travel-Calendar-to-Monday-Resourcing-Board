import json
import os
import requests
import msal

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DELTA_FILE = ".delta_tokens.json"


class OutlookClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, user_email: str):
        self.user_email = user_email
        self._app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _token(self) -> str:
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Token acquisition failed: {result.get('error_description', result)}"
            )
        return result["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Calendar helpers
    # ------------------------------------------------------------------

    def _travel_calendar_id(self) -> str:
        url = f"{GRAPH_BASE}/users/{self.user_email}/calendars"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        for cal in resp.json().get("value", []):
            if cal["name"].lower() == "travel":
                return cal["id"]
        raise ValueError(
            f"No calendar named 'Travel' found for {self.user_email}. "
            "Check the calendar name in Outlook."
        )

    # ------------------------------------------------------------------
    # Delta-based event fetching (only new/changed events per run)
    # ------------------------------------------------------------------

    def get_new_events(self) -> list[dict]:
        """Return events that are new or changed since the last run."""
        calendar_id = self._travel_calendar_id()
        delta_tokens = self._load_delta_tokens()
        stored = delta_tokens.get(calendar_id)

        if stored:
            url = stored  # deltaLink from previous run
        else:
            # First run: seed with today's events only to avoid processing history
            url = (
                f"{GRAPH_BASE}/users/{self.user_email}/calendars/{calendar_id}"
                "/events/delta"
                "?$select=subject,start,end,isAllDay,createdDateTime"
                "&$filter=start/dateTime ge '" + _today_iso() + "'"
            )

        events: list[dict] = []
        while url:
            resp = requests.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            events.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            if "@odata.deltaLink" in data:
                delta_tokens[calendar_id] = data["@odata.deltaLink"]
                self._save_delta_tokens(delta_tokens)
                break

        # Exclude deleted/cancelled events (Graph marks them with @removed)
        return [e for e in events if "@removed" not in e]

    # ------------------------------------------------------------------
    # Delta token persistence
    # ------------------------------------------------------------------

    def _load_delta_tokens(self) -> dict:
        if os.path.exists(DELTA_FILE):
            with open(DELTA_FILE) as f:
                return json.load(f)
        return {}

    def _save_delta_tokens(self, tokens: dict) -> None:
        with open(DELTA_FILE, "w") as f:
            json.dump(tokens, f, indent=2)

    # ------------------------------------------------------------------
    # Webhook subscription management
    # ------------------------------------------------------------------

    def create_subscription(self, notification_url: str, secret: str, calendar_id: str = None) -> dict:
        """Register an MS Graph change notification subscription for the Travel calendar."""
        if not calendar_id:
            calendar_id = self._travel_calendar_id()
        payload = {
            "changeType": "created,updated",
            "notificationUrl": notification_url,
            "resource": f"/users/{self.user_email}/calendars/{calendar_id}/events",
            "expirationDateTime": _expiry_iso(days=2),
            "clientState": secret,
        }
        resp = requests.post(
            f"{GRAPH_BASE}/subscriptions",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_event(self, event_id: str) -> dict:
        url = f"{GRAPH_BASE}/users/{self.user_email}/events/{event_id}?$select=subject,start,end,isAllDay"
        resp = requests.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _today_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


def _expiry_iso(days: int) -> str:
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
