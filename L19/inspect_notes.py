import requests
import zipfile
import io

url = 'https://hub.ag3nts.org/dane/natan_notes.zip'
resp = requests.get(url, timeout=60)
print('status', resp.status_code)
if resp.status_code != 200:
    raise SystemExit('fetch failed')

z = zipfile.ZipFile(io.BytesIO(resp.content))
print('files:', z.namelist())
for name in z.namelist():
    if name.endswith('/'):
        continue
    print('---', name)
    data = z.read(name).decode('utf-8', errors='replace')
    print(data[:1500])
