import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

url = 'https://de.wikipedia.org/wiki/H-_und_P-S%C3%A4tze'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    html = urllib.request.urlopen(req, context=ctx).read()
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table', class_='wikitable')
    data = {'h_saetze': [], 'p_saetze': [], 'euh_saetze': []}
    
    for table in tables:
        rows = table.find_all('tr')
        if not rows: continue
        headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
        if 'Code' in headers or len(headers) >= 2:
            for row in rows[1:]:
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    code = cols[0].text.strip()
                    desc = cols[1].text.strip()
                    
                    code = code.split('[')[0].strip()
                    desc = desc.split('[')[0].strip()

                    # Only capture actual H/P codes, e.g., H200, P101, EUH014
                    if code.startswith('H') and len(code) >= 4:
                        data['h_saetze'].append({'code': code, 'text': desc})
                    elif code.startswith('P') and len(code) >= 4:
                        data['p_saetze'].append({'code': code, 'text': desc})
                    elif code.startswith('EUH') and len(code) >= 6:
                        data['euh_saetze'].append({'code': code, 'text': desc})
    
    with open('static/hp_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Extraction successful: {len(data['h_saetze'])} H, {len(data['p_saetze'])} P, {len(data['euh_saetze'])} EUH.")
except Exception as e:
    print('Error:', e)
