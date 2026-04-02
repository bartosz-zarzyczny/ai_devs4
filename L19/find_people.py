import requests, zipfile, io, re

r = requests.get('https://hub.ag3nts.org/dane/natan_notes.zip', timeout=60)
z = zipfile.ZipFile(io.BytesIO(r.content))
text = z.read('rozmowy.txt').decode('utf-8', errors='replace')
print(text)
print('---- Names ----')
names = re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)*\b", text)
print(names)
print('Unique', sorted(set(names)))
