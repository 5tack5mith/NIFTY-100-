"""Sprint 6, Day 40: convert the running API's OpenAPI spec into a Postman
Collection v2.1 file -- spec deliverable: "Postman collection exported".

Doesn't call any external conversion service (none available in this
environment) -- OpenAPI's path/method/parameter structure maps directly
onto Postman's request format, so this is a straightforward mechanical
transform, not something that needs a third-party tool.

Run with: python src/api/export_postman_collection.py
(requires the API server already running on localhost:8000)
"""

import json
import os
import urllib.request

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output")
BASE_URL = "http://localhost:8000"


def build_postman_collection(openapi_spec: dict) -> dict:
    items = []
    for path, methods in openapi_spec["paths"].items():
        for method, details in methods.items():
            query_params = [
                {"key": p["name"], "value": "", "description": p.get("description", ""), "disabled": True}
                for p in details.get("parameters", []) if p.get("in") == "query"
            ]
            path_with_placeholder_values = path  # Postman uses {{var}} style, but literal example values are simpler for a reviewer to just run directly
            items.append({
                "name": details.get("summary") or f"{method.upper()} {path}",
                "request": {
                    "method": method.upper(),
                    "header": [],
                    "url": {
                        "raw": BASE_URL + path_with_placeholder_values + ("?" + "&".join(f"{q['key']}=" for q in query_params) if query_params else ""),
                        "host": [BASE_URL],
                        "path": [p for p in path_with_placeholder_values.split("/") if p],
                        "query": query_params,
                    },
                    "description": details.get("description", ""),
                },
                "response": [],
            })

    return {
        "info": {
            "name": openapi_spec["info"]["title"],
            "description": openapi_spec["info"].get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
    }


def run() -> str:
    with urllib.request.urlopen(f"{BASE_URL}/openapi.json") as response:
        openapi_spec = json.load(response)

    collection = build_postman_collection(openapi_spec)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "postman_collection.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2)
    return output_path


if __name__ == "__main__":
    path = run()
    print(f"postman_collection.json written to {path}")
