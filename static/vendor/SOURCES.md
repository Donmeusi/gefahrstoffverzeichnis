# Herkunft der mitgelieferten Schriften und Icons

Diese Dateien werden lokal ausgeliefert. Vorher kamen sie von externen CDNs
(`fonts.googleapis.com` und `cdnjs.cloudflare.com`) — das widersprach der
eigenen Datenschutzdokumentation, die einen reinen Intranet-Betrieb und
„keinen Datenabfluss" zusichert (`DATENSCHUTZ_UND_TOM.md`, Abschnitte 1.2, 3.3
und 6). Bei jedem Seitenaufruf wurden dabei IP-Adresse und Referer an Dritte
übertragen, ohne dass die Anwendung das brauchte.

Seit dem 25.09.2026 lädt die Anwendung **keine externen Ressourcen mehr**.

## Font Awesome 6.4.0 Free

| Datei | SHA-256 |
|---|---|
| `font-awesome/css/all.min.css` | `1edb1725a9ea8ca4dcf2f5508cee183218aa1685e47c1b23056717f754f58ebf` |
| `font-awesome/webfonts/fa-solid-900.woff2` | `7152a6933ee3d690ec2af3d09da9d701723d16aa3410a6d80f28ff8866f3b880` |
| `font-awesome/webfonts/fa-regular-400.woff2` | `8e7e5ea1b15f62ab14dbd41768e8fbcd21cc859a4ea5da812457ee714299fb35` |
| `font-awesome/webfonts/fa-brands-400.woff2` | `748332090c4b8e20f95d0ff59f0be20fa9c889359d3b36d4b886d73376054207` |
| `font-awesome/webfonts/fa-v4compatibility.woff2` | `694a17c3d9d6c05f8aac63c544615552a4b220e9a4de863d87341a6bcfc1bc8d` |
| `font-awesome/LICENSE.txt` | `0aa8f86525273b2efa4f40f4272a188e187704252170e979dc06879adf68d43c` |

Quelle: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/…` —
dieselben Dateien, die die Anwendung vorher von dort geladen hat, nur lokal.
Die Lizenzdatei kommt aus dem offiziellen Repository
(`https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.4.0/LICENSE.txt`),
weil cdnjs sie nicht ausliefert.

**Lizenz — drei Teile, siehe `LICENSE.txt`:**

* **Icons: CC BY 4.0**
* **Fonts: SIL OFL 1.1**
* **Code: MIT**

⚠️ **Namensnennung ist damit Pflicht** — aber die Lizenzdatei stellt selbst
klar: *„Downloaded Font Awesome Free files already contain embedded comments
with sufficient attribution, so you shouldn't need to do anything additional
when using these files normally."* Die Attribution steckt also in den
mitgelieferten Dateien, es braucht **keine** Attributionszeile in der
Oberfläche oder im Ausdruck. Für die DSB-Dokumentation ist das der
entscheidende Satz.

**Nicht mitgeliefert:** die `.ttf`-Fassungen derselben Schnitte. `all.min.css`
nennt sie als zweite Quelle (`src: url(…woff2) format("woff2"), url(…ttf)`),
moderne Browser laden ausschließlich die zuerst genannte woff2-Datei. Ein
Uralt-Browser ohne woff2-Unterstützung bekäme die Symbole nicht — das ist für
den vorgesehenen Einsatz (aktueller Browser im Intranet) unerheblich.

## Inter v20 (Variable Font)

| Datei | SHA-256 |
|---|---|
| `fonts/inter-v20-latin.woff2` | `c940764593d0fe5d596be327ca7558855e018039fb78509aa21921fd3644c3e4` |
| `fonts/inter-v20-latin-ext.woff2` | `a28eb6d3ccb534ae0c94ca999371df024aab60b08c3c8a5720ee9e32fa0faaa2` |
| `fonts/inter.css` | `6db3a5a5631beff15e1295fd84df62ea0d677f73df3aa9af38acf2a1842da57e` |
| `fonts/LICENSE.txt` | `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a` |

Bezug: die woff2-URLs aus der Antwort der Google-Fonts-API auf
`https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap`.
Von den sieben angebotenen Subsets sind nur **latin** und **latin-ext**
mitgeliefert: `latin` deckt `U+0000-00FF` ab und enthält damit alle Umlaute und
ß, `latin-ext` die übrigen mitteleuropäischen Zeichen (etwa für tschechische
oder polnische Namen). Zwei Dateien genügen, weil Inter als Variable Font
bereits die Schnitte 400–800 enthält.

Die `unicode-range`-Angaben in `inter.css` sind aus der API-Antwort übernommen.
Sie sind **nicht kosmetisch**: ohne sie lädt der Browser beide Dateien, mit
ihnen nur die zum Text passende.

**Lizenz: SIL Open Font License 1.1** (`LICENSE.txt`). Self-Hosting und
Weitergabe sind ausdrücklich vorgesehen; die Schrift darf nur nicht für sich
allein verkauft werden.

## Warum `fonts/inter.css` eine eigene Datei ist

Die Betriebsanweisung (`ba_print.html`) und die QR-Seite (`print_qr.html`)
erben **nicht** von `base.html` und laden `style.css` **nicht**, referenzieren
Inter aber. Läge das `@font-face` in `style.css`, hätten beide keine Schrift.
Eine eigene kleine Datei vermeidet die Dopplung — sie wird von `base.html` und
den beiden Druckseiten geladen.

`location_print.html` braucht sie nicht: diese Seite nutzt die Systemschrift.

## Aktualisieren

```bash
# Font Awesome
B="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0"
curl -sS -o static/vendor/font-awesome/css/all.min.css "$B/css/all.min.css"
for f in fa-solid-900 fa-regular-400 fa-brands-400 fa-v4compatibility; do
  curl -sS -o "static/vendor/font-awesome/webfonts/$f.woff2" "$B/webfonts/$f.woff2"
done

# Inter (woff2-URLs aus der API-Antwort entnehmen)
curl -sS -A "Mozilla/5.0" "https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap"
```

Danach die Hashes hier erneuern und in `CHANGELOG.md` notieren. Die Assets
werden **nicht** über `APP_VERSION` versioniert — `style.css` schon. Wenn sich
Pfade ändern, die Version mitziehen, sonst halten Browser alte Dateien im Cache.

## Nebenbei vermerkt

* `style.css` referenziert in der Monospace-Kette `'JetBrains Mono'`, das
  **nirgends geladen** wird. Es fällt still auf Consolas bzw. Courier zurück.
  Bestehender Zustand, bewusst nicht geändert — es wird nichts nachgeladen.
* `ba_print.html` lud vorher `fonts.googleapis.com/css2?family=Arial` — einen
  Aufruf nach einer Schrift, die es bei Google Fonts **nicht gibt**. Die Seite
  nutzt ohnehin die Systemschrift. Der Aufruf wurde ersatzlos entfernt.
* `gestis.dguv.de` wird weiterhin verlinkt (`add.html`, `edit.html`,
  `view.html`). Das sind reine `<a href>`-Verweise — sie lösen **erst beim
  Klick** eine Verbindung aus und übertragen beim Seitenaufruf nichts.
