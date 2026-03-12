#!/usr/bin/env python3
"""Send payload_to_send.json to the Hub and log the response.

Usage:
  python send_payload.py
  python send_payload.py --payload path/to/payload.json --log path/to/send_log.txt

This script is for local use only. It will redact the `apikey` when logging the request.
"""
import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

try:
    import requests
except Exception:
    print("Missing dependency: requests. Install with: pip install requests")
    sys.exit(2)


def redact_payload(payload):
    p = dict(payload)
    if isinstance(p, dict) and "apikey" in p:
        p["apikey"] = "<REDACTED>"
    return p


def _extract_legacy_fields(text):
    """Extract key:value fields from legacy declaration format."""
    fields = {}
    for raw in text.splitlines():
        line = raw.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def _build_template_declaration(fields):
    """Build declaration in the format from Zalacznik E."""
    data = fields.get("DATE", "2026-03-12")
    origin = fields.get("ORIGIN", "ORIGIN_PLACEHOLDER")
    sender = fields.get("SENDER_ID", "SENDER_ID_PLACEHOLDER")
    dest = fields.get("DESTINATION", "DESTINATION_PLACEHOLDER")
    route = fields.get("TRASA", "TRASA_PLACEHOLDER")
    category = fields.get("KATEGORIA", "D")
    content = fields.get("CONTENT_DESCRIPTION", "CONTENT_DESCRIPTION_PLACEHOLDER")
    weight = fields.get("WEIGHT_KG", "WEIGHT_KG_PLACEHOLDER")
    wdp = fields.get("WDP", "WDP_PLACEHOLDER")
    notes = fields.get("SPECIAL_NOTES", "BRAK")
    payment = fields.get("BUDGET_PP", "BUDGET_PP_PLACEHOLDER")

    return (
        "SYSTEM PRZESYŁEK\n"
        "KONDUKTORSKICH - DEKLARACJA\n"
        "ZAWARTOŚCI\n"
        "======================================================\n"
        f"DATA: {data}\n"
        f"PUNKT NADAWCZY: {origin}\n"
        "------------------------------------------------------\n"
        f"NADAWCA: {sender}\n"
        f"PUNKT DOCELOWY: {dest}\n"
        f"TRASA: {route}\n"
        "------------------------------------------------------\n"
        "KATEGORIA PRZESYŁKI:\n"
        f"{category}\n"
        "------------------------------------------------------\n"
        "OPIS ZAWARTOŚCI (max 200 znaków):\n"
        f"{content}\n"
        "------------------------------------------------------\n"
        "DEKLAROWANA MASA (kg):\n"
        f"{weight}\n"
        "------------------------------------------------------\n"
        "WDP:\n"
        f"{wdp}\n"
        "------------------------------------------------------\n"
        "UWAGI SPECJALNE:\n"
        f"{notes}\n"
        "------------------------------------------------------\n"
        "KWOTA DO ZAPŁATY:\n"
        f"{payment}\n"
        "------------------------------------------------------\n"
        "OŚWIADCZAM, ŻE PODANE INFORMACJE SĄ PRAWDZIWE.\n"
        "BIORĘ NA SIEBIE KONSEKWENCJE ZA FAŁSZYWE OŚWIADCZENIE.\n"
        "======================================================\n"
    )


def _apply_overrides_to_declaration(decl, route=None, wdp=None):
    """Apply route/WDP overrides directly to declaration text."""
    if route:
        decl = re.sub(r"(^TRASA:\s*).*$", rf"\1{route}", decl, flags=re.MULTILINE)
    if wdp is not None:
        # Replace the value line right after 'WDP:' section header
        decl = re.sub(
            r"(WDP:\n)(.*?)(\n-+\n)",
            lambda m: f"{m.group(1)}{wdp}{m.group(3)}",
            decl,
            flags=re.DOTALL,
        )
    return decl


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_payload = os.path.join(here, "payload_to_send.json")
    default_log = os.path.join(here, "send_log.txt")

    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", default=default_payload, help="Path to payload JSON")
    parser.add_argument("--log", default=default_log, help="Path to log file")
    parser.add_argument("--url", default="https://hub.ag3nts.org/verify", help="Target URL")
    parser.add_argument("--apikey", default=None, help="API key to use (overrides payload or env)")
    parser.add_argument("--route", default=None, help="Override TRASA code in declaration, e.g. X-01")
    parser.add_argument("--wdp", default=None, help="Override WDP value in declaration, e.g. 0")
    parser.add_argument("--dry-run", action="store_true", help="Do not perform network request; simulate only")
    parser.add_argument("--response-log", default=os.path.join(here, "response_log.json"),
                        help="Path to separate JSON file with timestamped API responses")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.log, encoding="utf-8", mode="a"), logging.StreamHandler()],
    )

    if not os.path.exists(args.payload):
        logging.error("Payload file not found: %s", args.payload)
        sys.exit(3)

    try:
        with open(args.payload, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        logging.exception("Failed to load payload: %s", e)
        sys.exit(4)

    # Allow overriding apikey from CLI or environment
    env_key = os.environ.get("AI_DEVS_4_API_KEY")
    if args.apikey:
        payload["apikey"] = args.apikey
    elif payload.get("apikey") in (None, "", "<TWOJ_API_KEY_TUTAJ>", "AI_DEVS_4_API_KEY") and env_key:
        payload["apikey"] = env_key

    # Validate apikey presence and basic format before sending
    apikey = payload.get("apikey")
    if not apikey or not isinstance(apikey, str) or apikey.strip() == "" or apikey.startswith("<"):
        logging.error("Invalid or missing apikey in payload. Provide a valid key via payload file, --apikey, or AI_DEVS_4_API_KEY env var.")
        sys.exit(6)

    payload_redacted = redact_payload(payload)
    logging.info("Prepared payload (apikey redacted): %s", json.dumps(payload_redacted, ensure_ascii=False))

    # Sanitize declaration formatting and ensure template start marker from Zalacznik E
    try:
        decl = payload.get("answer", {}).get("declaration")
        if decl is None:
            logging.error("Payload missing answer.declaration field")
            sys.exit(7)
        # normalize newlines
        decl = decl.replace('\r\n', '\n')
        # remove leading whitespace/newlines
        decl = decl.lstrip()

        required_start = "SYSTEM PRZESYŁEK\nKONDUKTORSKICH - DEKLARACJA\nZAWARTOŚCI"
        legacy_start = "==== BEGIN DECLARATION ===="

        if decl.startswith(legacy_start):
            logging.warning("Legacy declaration format detected; converting to Zalacznik E template")
            fields = _extract_legacy_fields(decl)
            decl = _build_template_declaration(fields)
        elif not decl.startswith(required_start):
            logging.warning("Declaration missing required template start marker; rebuilding template")
            fields = _extract_legacy_fields(decl)
            decl = _build_template_declaration(fields)

        # Optional command-line overrides for quick testing
        decl = _apply_overrides_to_declaration(decl, route=args.route, wdp=args.wdp)

        payload["answer"]["declaration"] = decl
        payload_redacted = redact_payload(payload)
        logging.info("Declaration sanitized (apikey redacted): %s", json.dumps(payload_redacted, ensure_ascii=False))
    except Exception:
        logging.exception("Failed to sanitize declaration")
        sys.exit(8)

    if args.dry_run:
        logging.info("Dry-run enabled — not performing network request. URL would be: %s", args.url)
        with open(args.log, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- DRY-RUN REQUEST at {datetime.now(timezone.utc).isoformat()}Z ---\n")
            lf.write("REQUEST (redacted):\n")
            lf.write(json.dumps(payload_redacted, ensure_ascii=False, indent=2))
            lf.write("\nSIMULATED: No network request performed.\n--- END ---\n")
        print("Dry-run complete — payload prepared and logged (redacted).")
        return

    try:
        resp = requests.post(args.url, json=payload, timeout=30)
        logging.info("HTTP %s %s", resp.status_code, resp.reason)
        try:
            body = resp.json()
            logging.info("Response JSON: %s", json.dumps(body, ensure_ascii=False, indent=2))
        except Exception:
            body = None
            logging.info("Response text: %s", resp.text)

        # ── ogólny log (send_log.txt): pełny request + response
        with open(args.log, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- REQUEST at {datetime.now(timezone.utc).isoformat()}Z ---\n")
            lf.write("REQUEST (redacted):\n")
            lf.write(json.dumps(payload_redacted, ensure_ascii=False, indent=2))
            lf.write("\nRESPONSE STATUS: %s\n" % resp.status_code)
            if body is not None:
                lf.write("RESPONSE BODY:\n")
                lf.write(json.dumps(body, ensure_ascii=False, indent=2))
            else:
                lf.write("RESPONSE BODY (text):\n")
                lf.write(resp.text)
            lf.write("\n--- END ---\n")

        # ── osobny log odpowiedzi (response_log.jsonl): jedna linia JSON na wywołanie
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "status_code": resp.status_code,
            "response": body if body is not None else resp.text,
            "route": args.route,
            "wdp": args.wdp,
        }
        with open(args.response_log, "a", encoding="utf-8") as rl:
            rl.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logging.info("Response appended to: %s", args.response_log)

    except requests.RequestException as e:
        logging.exception("Request failed: %s", e)
        sys.exit(5)


if __name__ == "__main__":
    main()
