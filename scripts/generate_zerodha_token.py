"""generate_zerodha_token.py

Automatically fetches ZERODHA_API_KEY and ZERODHA_API_SECRET from the project‑root
`.env`, launches the Zerodha login flow in a browser, captures the `request_token`,
exchanges it for an `access_token`, and stores/updates `ZERODHA_ACCESS_TOKEN`
in the same `.env` — without touching your other environment variables.
"""

import os
import webbrowser
from pathlib import Path

from flask import Flask, request
from kiteconnect import KiteConnect
from dotenv import load_dotenv, set_key

# ──────────────────────────────────────────────────────────────────────────────
# 🔍 Locate the project‑root .env (one directory above this script)
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parent / ".env"

if not ENV_PATH.exists():
    raise FileNotFoundError(
        f"⚠️ .env not found at expected location: {ENV_PATH}.\n"
        "Make sure your project root contains the .env with ZERODHA_API_KEY and ZERODHA_API_SECRET."
    )

# Load variables so they are available via os.getenv
load_dotenv(ENV_PATH)

API_KEY = os.getenv("ZERODHA_API_KEY")
API_SECRET = os.getenv("ZERODHA_API_SECRET")

if not API_KEY or not API_SECRET:
    raise RuntimeError(
        "ZERODHA_API_KEY or ZERODHA_API_SECRET missing in .env.\n"
        "Add them in the format:\n"
        "ZERODHA_API_KEY='your_key_here'\nZERODHA_API_SECRET='your_secret_here'"
    )

# ──────────────────────────────────────────────────────────────────────────────
# 🪁  Kite Connect setup
# ──────────────────────────────────────────────────────────────────────────────
kite = KiteConnect(api_key=API_KEY)
app = Flask(__name__)


@app.route("/")
def catch_token():
    """Endpoint hit by Zerodha after successful login — grabs `request_token`."""
    request_token = request.args.get("request_token")
    if not request_token:
        return "Missing request_token", 400

    try:
        session_data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = session_data["access_token"]

        # Persist the new token alongside existing vars
        set_key(str(ENV_PATH), "ZERODHA_ACCESS_TOKEN", access_token)

        return "✅ Access token saved in .env — you may close this tab."
    except Exception as e:
        return f"Error exchanging token: {e}", 500


# ──────────────────────────────────────────────────────────────────────────────
# 🚀 Main entrypoint
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    login_url = kite.login_url()
    print("🔗  Open the following URL to authenticate (your browser should open automatically):\n")
    print(login_url)

    # Pop open the login page in the default browser
    webbrowser.open(login_url)

    print("🌐  Waiting for redirect and token capture on http://localhost:8000 ...")
    app.run(port=8000)


if __name__ == "__main__":
    main()


