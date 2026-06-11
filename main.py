"""
Entry point. Two modes:

  python main.py poll
      Fetch events added/changed since the last run (delta query) and process PTO.
      Safe to run on a schedule (cron, Task Scheduler).

  python main.py webhook
      Start a Flask server that receives MS Graph change notifications.
      Requires a public HTTPS URL (use ngrok for local testing).
      On first run in webhook mode, the subscription is registered automatically.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _build_clients():
    from outlook_client import OutlookClient
    from monday_client import MondayClient

    outlook = OutlookClient(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
        user_email=os.environ["OUTLOOK_USER_EMAIL"],
    )
    monday = MondayClient(
        api_key=os.environ["MONDAY_API_KEY"],
        board_id=int(os.environ.get("MONDAY_BOARD_ID", "18397329110")),
    )
    return outlook, monday


# ------------------------------------------------------------------
# Poll mode
# ------------------------------------------------------------------

def run_poll():
    from pto_processor import PTOProcessor
    outlook, monday = _build_clients()
    processor = PTOProcessor(outlook, monday)
    processor.process_new_events()


# ------------------------------------------------------------------
# Webhook mode
# ------------------------------------------------------------------

def run_webhook():
    import hmac
    import hashlib
    from flask import Flask, request, jsonify
    from pto_processor import PTOProcessor

    secret = os.environ.get("WEBHOOK_SECRET", "")
    port = int(os.environ.get("WEBHOOK_PORT", 5000))
    notification_url = os.environ.get("WEBHOOK_NOTIFICATION_URL", "")

    outlook, monday = _build_clients()
    processor = PTOProcessor(outlook, monday)

    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook():
        # MS Graph sends a validationToken on subscription creation
        validation_token = request.args.get("validationToken")
        if validation_token:
            return validation_token, 200, {"Content-Type": "text/plain"}

        # Validate client state to confirm the notification is from Graph
        data = request.get_json(silent=True) or {}
        for notification in data.get("value", []):
            if secret and notification.get("clientState") != secret:
                continue
            resource_data = notification.get("resourceData", {})
            event_id = resource_data.get("id")
            if event_id:
                try:
                    processor.process_event_by_id(event_id)
                except Exception as exc:
                    print(f"Error processing event {event_id}: {exc}")

        return jsonify({"status": "ok"}), 202

    # Register the subscription if a notification URL is configured
    if notification_url:
        try:
            sub = outlook.create_subscription(notification_url + "/webhook", secret)
            print(f"Subscription registered: {sub.get('id')} (expires {sub.get('expirationDateTime')})")
        except Exception as exc:
            print(f"WARNING: Could not register subscription: {exc}")
            print("Start the server anyway — register the subscription manually if needed.")

    print(f"Webhook server listening on port {port} …")
    app.run(host="0.0.0.0", port=port)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "poll"
    if mode == "webhook":
        run_webhook()
    else:
        run_poll()
