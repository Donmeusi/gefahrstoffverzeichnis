import urllib.request
import os

key = 'GHS08'
filename = 'GHS-pictogram-silhouette.svg'

base_url = "https://commons.wikimedia.org/wiki/Special:FilePath/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

url = base_url + filename
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        data = response.read()
        if b'<svg' in data:
            with open(f'static/pictograms/{key}.svg', 'wb') as out_file:
                out_file.write(data)
            print(f"Successfully downloaded {key}.svg ({filename})")
        else:
            print(f"Failed: Not an SVG for {key}.svg")
except Exception as e:
    print(f"Failed to download {key}.svg ({filename}): {e}")
