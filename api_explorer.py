#!/usr/bin/env python3
"""
A sandbox script to interact with the localhost API and explore endpoints.
"""
import json

import requests
from requests.auth import HTTPBasicAuth

# ----------------------------------------------------------------------
# 🔧 USER GLOBALS
# ----------------------------------------------------------------------
BASE_URL: str = "http://localhost:8000"
USERNAME, PASSWORD = "admin", "admin"


def get_request(endpoint: str, auth: HTTPBasicAuth) -> dict:
    """Helper to make a GET request and return JSON."""
    try:
        print(f"▶️  Sending request to {endpoint}...")
        r = requests.get(f"{BASE_URL}{endpoint}", auth=auth, timeout=30)
        print(f"◀️  Received response (status: {r.status_code})")
        r.raise_for_status()  # Raise an exception for bad status codes
        return r.json()
    except requests.exceptions.RequestException as exc:
        print(f"❌  Request failed: {exc}")
        return {"error": str(exc)}
    except ValueError:
        print("❌  Failed to decode JSON.")
        return {"error": "non-JSON response", "raw": r.text[:500]}


def main():
    """Explore the API to get controller information."""
    auth = HTTPBasicAuth(USERNAME, PASSWORD)

    print("--- 1. Listing all available controllers ---")
    controllers = get_request("/list-controllers", auth)
    print(json.dumps(controllers, indent=2))
    print("─" * 50)

    if "error" not in controllers:
        # Let's get configs for the controllers of interest
        controllers_to_inspect = {
            "pmm_simple": "market_making",
            "pmm_dynamic": "market_making",
            "dman_v3": "directional_trading",
            "dman_maker_v2": "market_making"
        }

        for name, controller_type in controllers_to_inspect.items():
            print(f"--- 2. Getting config for '{name}' ({controller_type}) ---")
            # Corrected endpoint path construction
            endpoint = f"/controller-config-pydantic/{controller_type}/{name}"
            config = get_request(endpoint, auth)
            print(json.dumps(config, indent=2))
            print("─" * 50)


if __name__ == "__main__":
    main() 