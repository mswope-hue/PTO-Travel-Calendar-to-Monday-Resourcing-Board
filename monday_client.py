import json
import requests

MONDAY_API = "https://api.monday.com/v2"

# Subitems board for the Resourcing Board (discovered from board metadata)
SUBITEMS_BOARD_ID = "18397329129"

# Column IDs on the main Resourcing Board
COL_PROJECT_NAME = "text_mm0gsedz"       # "02 - PTO"

# Column IDs on the subitems board
SUBCOL_PLANNED_HRS = "numeric_mkzkw9qz"  # Planned hours
SUBCOL_DATE = "date_mm33e7b7"            # Date (start of PTO)
SUBCOL_NOTES = "text_mm35wh5a"           # Notes (date range)


class MondayClient:
    def __init__(self, api_key: str, board_id: int):
        self.board_id = board_id
        self._headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "API-Version": "2024-01",
        }

    # ------------------------------------------------------------------
    # Internal GraphQL helper
    # ------------------------------------------------------------------

    def _gql(self, query: str, variables: dict = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = requests.post(MONDAY_API, json=payload, headers=self._headers)
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(f"Monday.com API error: {body['errors']}")
        return body["data"]

    # ------------------------------------------------------------------
    # PTO item lookup
    # ------------------------------------------------------------------

    def find_pto_item_for_month(self, month_name: str) -> int | None:
        """
        Return the item ID for the '02 - PTO' row whose name matches month_name
        (e.g. 'June 2026'). Returns None if not found.
        """
        query = """
        query ($board_id: ID!) {
          items_page_by_column_values(
            limit: 500
            board_id: $board_id
            columns: [{ column_id: "text_mm0gsedz", column_values: ["02 - PTO"] }]
          ) {
            items { id name }
          }
        }
        """
        data = self._gql(query, {"board_id": str(self.board_id)})
        for item in data["items_page_by_column_values"]["items"]:
            if item["name"] == month_name:
                return int(item["id"])
        return None

    # ------------------------------------------------------------------
    # Subitem management
    # ------------------------------------------------------------------

    def upsert_pto_subitem(
        self,
        parent_item_id: int,
        person_name: str,
        hours: float,
        start_date: str,
        notes: str,
    ) -> int:
        """
        Create a subitem for person_name under parent_item_id, or update it if
        one with the same name already exists. Returns the subitem ID.
        """
        existing_id = self._find_subitem(parent_item_id, person_name)
        if existing_id:
            self._update_subitem(existing_id, hours, start_date, notes)
            return existing_id
        return self._create_subitem(parent_item_id, person_name, hours, start_date, notes)

    def _find_subitem(self, parent_item_id: int, person_name: str) -> int | None:
        query = """
        query ($id: ID!) {
          items(ids: [$id]) {
            subitems { id name }
          }
        }
        """
        data = self._gql(query, {"id": str(parent_item_id)})
        for sub in data["items"][0].get("subitems") or []:
            if sub["name"].strip().lower() == person_name.strip().lower():
                return int(sub["id"])
        return None

    def _create_subitem(
        self,
        parent_item_id: int,
        person_name: str,
        hours: float,
        start_date: str,
        notes: str,
    ) -> int:
        col_values = json.dumps(
            {
                SUBCOL_PLANNED_HRS: hours,
                SUBCOL_DATE: {"date": start_date},
                SUBCOL_NOTES: notes,
            }
        )
        query = """
        mutation ($parent_id: ID!, $name: String!, $column_values: JSON!) {
          create_subitem(
            parent_item_id: $parent_id
            item_name: $name
            column_values: $column_values
          ) { id name }
        }
        """
        data = self._gql(
            query,
            {"parent_id": str(parent_item_id), "name": person_name, "column_values": col_values},
        )
        return int(data["create_subitem"]["id"])

    def _update_subitem(
        self, subitem_id: int, hours: float, start_date: str, notes: str
    ) -> None:
        col_values = json.dumps(
            {
                SUBCOL_PLANNED_HRS: hours,
                SUBCOL_DATE: {"date": start_date},
                SUBCOL_NOTES: notes,
            }
        )
        query = """
        mutation ($item_id: ID!, $board_id: ID!, $column_values: JSON!) {
          change_multiple_column_values(
            item_id: $item_id
            board_id: $board_id
            column_values: $column_values
          ) { id }
        }
        """
        self._gql(
            query,
            {
                "item_id": str(subitem_id),
                "board_id": SUBITEMS_BOARD_ID,
                "column_values": col_values,
            },
        )
