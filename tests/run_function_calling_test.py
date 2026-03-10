import json
import traceback

from L02 import function_calling as fc
from L02 import solve_findhim as sf


def stub_post_json(url, payload):
    # Stub /api/location to return a single point at Grudziądz
    if url == sf.LOCATION_URL:
        lat, lon = sf.PLANT_CITY_COORDS["Grudziądz"]
        return [{"latitude": lat, "longitude": lon}]
    if url == sf.ACCESSLEVEL_URL:
        return {"accessLevel": 3}
    return {"ok": True}


def stub_try_post_json(url, payload):
    if url == sf.VERIFY_URL:
        return True, {"status": "ok"}
    return True, {}


if __name__ == "__main__":
    try:
        # Patch network functions in solve_findhim module
        sf.post_json = stub_post_json
        sf.try_post_json = stub_try_post_json

        print("Running solve_findhim with stubbed network calls...")
        result = fc.solve_findhim(api_key="TESTKEY", max_distance_km=10.0, verify=False, sleep_ms=0)
        print("Report:")
        print(json.dumps(result["report"], ensure_ascii=False, indent=2))
        print("Candidates count:", len(result["candidates"]))
    except Exception:
        traceback.print_exc()
