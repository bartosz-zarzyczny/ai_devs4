from L02 import verify_findhim_candidates as vfc
import json
import os
import sys


def main():
    vfc.load_env_file(vfc.ENV_FILE)
    api = os.getenv("AI_DEVS_4_API_KEY")
    if not api:
        print("Brak AI_DEVS_4_API_KEY in environment or .env")
        sys.exit(1)

    report_path = "L02/findhim_report.json"
    if not os.path.exists(report_path):
        print("Brak pliku findhim_report.json. Uruchom pipeline najpierw.")
        sys.exit(1)

    report = json.loads(open(report_path, encoding="utf-8").read())
    selected = report.get("selected")
    if not selected:
        print("Brak wybranego kandydata w raporcie.")
        sys.exit(1)

    ok, resp = vfc.verify_answer(api, selected)
    print("OK:", ok)
    print(resp)


if __name__ == "__main__":
    main()
