# AGENTS.md

## Project

Home Assistant integration for libraries using **Koha** — direct REST API access, no VideLibri.

Target entities: `sensor.library_loans`, `sensor.library_next_due`, `calendar.library`, `binary_sensor.library_due_today`.

## Structure

```
custom_components/koha/
  __init__.py       HA integration setup
  manifest.json     HA manifest (domain: koha, iot_class: cloud_polling)
  const.py          DOMAIN, CONF_*, SCAN_INTERVAL_SECONDS (3600)
  config_flow.py    UI-based setup (url, userid, password)
  client.py         KohaClient (async login + HTML scraping via stdlib)
  sensor.py         sensor.library_loans, sensor.library_next_due
  binary_sensor.py  binary_sensor.library_due_today
  calendar.py       calendar.library
  strings.json      Config flow translations
```

The component is bundled — no pip installs needed. `KohaClient` uses stdlib `html.parser` for scraping and aiohttp for HTTP (provided by HA).

## Deploy

Copy the `custom_components/koha/` directory into your HA `config/custom_components/`, restart HA, then add via **Settings → Devices & Services → Add Integration** → search "Koha".

HA prefixes entity IDs with the config entry title (e.g. config title "Bücherei" → `sensor.bucherei_library_loans`).

## Sensor attributes

`sensor.<prefix>_library_loans` has attribute `checkouts` — a list of dicts with `title`, `author`, `due_date`, `barcode`, `overdue`, `due_today`, `renewals_used`, `renewals_max`. Also has `overdue_count` and `due_today_count`.

## Dashboard display: template sensor workaround

The HA code editor wraps long YAML lines, breaking multi-line markdown templates. Instead of putting table logic in a card, create a **Template Sensor** helper (Settings → Helpers → Create → Template → Template a sensor):

**State template:**
```
{% set loans = state_attr('sensor.bucherei_library_loans', 'checkouts') %}{% if loans | length == 0 %}Keine Ausleihen{% else %}{% for l in loans %}{% if l.overdue %}⚠️ {% endif %}{{ l.title }} – fällig {{ l.due_date }} ({{ l.renewals_used }}/{{ l.renewals_max }}){% if not loop.last %}
{% endif %}{% endfor %}{% endif %}
```

**Card** (two lines, can't wrap):
```yaml
type: markdown
content: "{{ states('sensor.bucherei_ausleihen_text') | replace('\n', '  \n') }}"
```

## Test instance

- URL: <https://sb-geesthacht.lmscloud.net>
- Koha REST API: `GET /api/v1/` returns public OpenAPI doc
- `checkout` type: `due_date`, `checkout_date`, `renewals_count`, `auto_renew`, `item`, `patron`

## Auth (verified from source)

Koha auth chain (`Koha::REST::V1::Auth::authenticate_api_request`):

1. **Bearer (OAuth2)** — checked first; returns 404 when `RESTOAuth2ClientCredentials` syspref is off
2. **Basic Auth** — checked second; blocked by `RESTBasicAuth` syspref (disabled on test instance → `"Basic authentication disabled"`)
3. **Cookie** — fallback when no `Authorization` header present; reads `CGISESSID` cookie from the request

Cookie auth is universally available — it uses the standard Koha OPAC session cookie. No syspref gates it.

### Cookie auth flow

1. `POST /cgi-bin/koha/opac-user.pl` with `userid` + `password` (standard HTML form)
2. Extract `CGISESSID` cookie from response
3. Send it with every REST API call (`Cookie: CGISESSID=<value>`)

## Important: no public REST endpoint for patron's own checkouts

`GET /api/v1/checkouts` requires `circulate_remaining_permissions` — a staff permission that regular patrons lack. There is no public REST API endpoint that returns a patron's own loans.

### The working approach: OPAC HTML scraping

The OPAC account page (`/cgi-bin/koha/opac-user.pl` after login) renders all checkout data server-side in an HTML `<table id="checkoutst">`. Parse it to extract titles, due dates, renewal info, and barcodes.

A working stdlib-only test script is at `test_auth.py`.

## Research log (historical)

The following is the original research log from `AGENT.md` (now merged). It documents the step-by-step investigation that led to the auth findings above.

---

**Projekt:** Entwicklung einer Home-Assistant-Integration für Bibliotheken, die das Bibliothekssystem **Koha** verwenden. Ziel ist es, **ohne VideLibri** direkt auf die Koha-REST-API zuzugreifen.

### REST API

Die Koha REST API ist aktiv. `GET /api/v1/` liefert das OpenAPI-Dokument mit Definitionen für `checkout`, `checkouts`, `hold`, `holds`. Der Datentyp `checkout` besitzt `due_date`, `checkout_date`, `renewals_count`, `auto_renew`, `item`, `patron`.

### Checkouts-Endpunkt

`GET /api/v1/checkouts` existiert. Ohne Authentifizierung: `401 { "error": "Authentication failure." }`

### Basic Authentication Test

```bash
curl --user "<cardnumber>:<password>" https://sb-geesthacht.lmscloud.net/api/v1/checkouts
```
Antwort: `401 { "error": "Basic authentication disabled" }` — Basic Auth ist serverseitig deaktiviert.

### OAuth Test

`GET /api/v1/oauth` → `404 Not Found`. Keine Hinweise auf aktiviertes OAuth.

### Authentifizierungsverfahren (ursprüngliche Hypothese)

Mit hoher Wahrscheinlichkeit verwendet diese Koha-Installation ausschließlich die normale OPAC-Session:
1. Login mittels Bibliotheksnummer + Passwort
2. Session-Cookie erhalten
3. Cookie für REST API verwenden

Die Koha-Dokumentation erwähnt Cookie-basierte Authentifizierung.

### Nächste Schritte (ursprünglich geplant)

1. Analyse des OPAC-Logins (POST URL, Formularfelder, CSRF-Token, Session-Cookie)
2. Login mit Python reproduzieren (`requests.Session()`)
3. Nach erfolgreichem Login: `GET /api/v1/checkouts` unter Verwendung des Session-Cookies
4. JSON analysieren (`due_date`, `item.title`, `renewals_count`, `auto_renew`)
5. Python-Bibliothek erstellen (`KohaClient` mit `login()`, `get_checkouts()`, `get_holds()`)
6. Home-Assistant-Integration mit Entitäten: `sensor.library_loans`, `sensor.library_next_due`, `calendar.library`, `binary_sensor.library_due_today`

### Nicht verwenden

VideLibri soll **nicht** verwendet werden. Die Integration soll direkt gegen die Koha-REST-API arbeiten.

### Bekannte Informationen

- Bibliothek: https://sb-geesthacht.lmscloud.net
- Software: Koha (LMSCloud)
- REST API: https://sb-geesthacht.lmscloud.net/api/v1/
- OpenAPI ist öffentlich erreichbar

### Offene Fragen (zum Zeitpunkt der Forschung)

- Wie erfolgt die OPAC-Authentifizierung?
- Akzeptiert die REST API das OPAC-Session-Cookie?
- Ist ein CSRF-Token erforderlich?
- Welche API-Endpunkte sind für normale Bibliotheksbenutzer freigeschaltet?
