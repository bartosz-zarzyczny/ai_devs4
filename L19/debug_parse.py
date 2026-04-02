import re, requests, zipfile, io, importlib.util, sys

spec = importlib.util.spec_from_file_location('task', r'd:\Repo\AI_Devs4\ai_devs4\L19\task.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

r = requests.get('https://hub.ag3nts.org/dane/natan_notes.zip', timeout=60)
z = zipfile.ZipFile(io.BytesIO(r.content))
text = z.read('ogłoszenia.txt').decode('utf-8', errors='replace')
line = [l for l in text.splitlines() if 'Opalino' in l][0]
print('line:', line)

tokens=re.findall(r"[0-9]+|[A-Za-zĄąĆćĘęŁłŃńÓóŚśŹźŻż]+", line)
print('tokens', tokens)

city='Opalino'
parsed={city:{}}
i = 0
while i < len(tokens):
    tok = tokens[i]
    if tok.isdigit():
        qty = int(tok)
        if i+1 < len(tokens):
            tok1 = tokens[i+1].lower()
            if tok1 in ('workow','butelek','kg') and i+2 < len(tokens):
                good = t.normalize_good(tokens[i+2])
                i += 3
                print('case unit', qty, tok1, tokens[i-1], '=>', good)
            else:
                good = t.normalize_good(tokens[i+1])
                i += 2
                print('case adj', qty, tok1, '=>', good)
            if good in ('kg','workow','butelek','mniejsza','x'):
                continue
            if good not in t.GOOD_WHITELIST:
                print('skip not whitelist', good)
                continue
            if good == 'porcja' and i+1 < len(tokens):
                maybe = t.normalize_good(tokens[i+1])
                if maybe in t.GOOD_WHITELIST and maybe != 'porcja':
                    good = maybe
                    i += 1
            parsed[city][good] = parsed[city].get(good,0) + qty
            print('add', good, qty)
            continue
    elif i+1 < len(tokens) and tokens[i+1].isdigit():
        good = t.normalize_good(tok)
        qty = int(tokens[i+1])
        print('reverse', good, qty)
        if good in ('kg','workow','butelek','mniejsza','x'):
            i += 2
            continue
        if good not in t.GOOD_WHITELIST:
            print('skip not whitelist reverse', good)
            i += 2
            continue
        if good == 'porcja' and i+2 < len(tokens):
            maybe = t.normalize_good(tokens[i+2])
            if maybe in t.GOOD_WHITELIST and maybe != 'porcja':
                good = maybe
                i += 1
        parsed[city][good] = parsed[city].get(good,0) + qty
        print('add reverse', good, qty)
        i += 2
        continue
    i += 1

print('parsed', parsed)
