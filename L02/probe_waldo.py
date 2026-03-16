import json, requests

URL = "https://hub.ag3nts.org/api/accesslevel"
API = "5f9f1207-390f-4032-b98a-72075b11e655"

names = [
    ("Martin", "Handford"),
    ("Wally", "Handford"),
    ("Waldo", "Handford"),
    ("Wally", "Wally"),
    ("Waldo", "Waldo"),
    ("Martin", "Wally"),
    ("Martin", "Waldo")
]

for n, s in names:
    for year in [1986, 1987, 1988, 1989, 1990]:
        payload = {
            "apikey": API,
            "name": n,
            "surname": s,
            "birthYear": year
        }
        try:
            r = requests.post(URL, json=payload, timeout=10)
            if r.status_code == 200:
                d = r.json()
                print(f"n={n} s={s} y={year} => {d}")
                if "FLG" in str(d):
                    print("!!! FLAG FOUND:", d)
            else:
                pass
        except:
            pass
