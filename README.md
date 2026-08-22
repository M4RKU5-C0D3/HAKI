# Home Assistant Koha Integration

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAKI)
[![GitHub release](https://img.shields.io/github/v/release/M4RKU5-C0D3/HAKI?style=for-the-badge)](https://github.com/M4RKU5-C0D3/HAKI/releases)
[![Validate](https://img.shields.io/github/actions/workflow/status/M4RKU5-C0D3/HAKI/validate.yml?branch=master&style=for-the-badge&label=Validate)](https://github.com/M4RKU5-C0D3/HAKI/actions/workflows/validate.yml)

Home Assistant custom component for libraries running the **Koha** library system. It connects directly to the Koha OPAC by logging in with your library credentials and scraping your account page.

## Why this exists

Koha's public REST API (`/api/v1/`) does **not** expose a patron's own loans: `GET /api/v1/checkouts` requires the staff permission `circulate_remaining_permissions`, which regular patrons don't have. Cookie auth (the OPAC session) works, but there's simply no public endpoint for your own checkouts.

So the integration uses the OPAC account page (`/cgi-bin/koha/opac-user.pl`) after login, parses the checkout table server-side rendered in `<table id="checkoutst">`, and exposes the data as native Home Assistant entities.

## Requirements

- A Koha library with OPAC access
- Your library card number and password
- Home Assistant with network access to the library OPAC

## Installation

### Via HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=M4RKU5-C0D3&repository=HAKI&category=integration)

1. In HACS go to **HACS → ⋮ → Custom repositories**
2. Add the repository URL `https://github.com/M4RKU5-C0D3/HAKI` with category **Integration**
3. Click **Download** on "Koha Library"
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** → search **"Koha"** and enter your library URL, card number, and password

### Manually

1. Copy the `custom_components/koha/` directory into your HA `config/custom_components/koha/`
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** → search **"Koha"** and enter your library URL, card number, and password

Entity IDs are prefixed with your config entry title — e.g. a config titled "Bücherei" produces `sensor.bucherei_library_loans`.

## Provided entities

All entities belong to the "Koha Library" device and update hourly (polling, `iot_class: cloud_polling`).

| Entity | Type | State | Purpose |
|---|---|---|---|
| `sensor.library_loans` | Sensor | Number | Number of currently checked-out items |
| `sensor.library_next_due` | Sensor | Date | Earliest due date across all loans |
| `binary_sensor.library_due_today` | Binary sensor | on/off | On when at least one item is due today |
| `calendar.library` | Calendar | — | One event per loan due date |

### `sensor.library_loans` attributes

Attribute `checkouts` is a list of dicts, one per loan:

| Key | Type | Description |
|---|---|---|
| `title` | str | Item title |
| `author` | str | Item author |
| `due_date` | str | Due date, German format, e.g. `22.08.2026` |
| `barcode` | str | Item barcode |
| `overdue` | bool | Due date is in the past |
| `due_today` | bool | Due date is today |
| `renewals_used` | int | Renewals already used |
| `renewals_max` | int | Maximum allowed renewals |
| `renewals_left` | int | Renewals remaining (`renewals_max - renewals_used`) |

Additional attributes:

- `overdue_count` — number of overdue items
- `due_today_count` — number of items due today

## Flex Table

For a tabular display of all loans, use the community card **flex-table-card** (install via HACS → Frontend). It expands the `checkouts` attribute into one row per loan:

```yaml
type: custom:flex-table-card
title: Alle Ausleihen
entities:
  include: sensor.bucherei_library_loans
columns:
  - name: Titel
    data: checkouts.title
  - name: Fällig
    data: checkouts.due_date
  - name: Verlängerungen
    data: checkouts.renewals_used
```

## Disclaimer

This is a personal project. It scrapes the public OPAC that every patron uses — it does not access any staff interfaces. Credentials are only used to log you into your own library account.

## Vibe coding

This project was built with AI assistance via [opencode](https://opencode.ai) using the model `big-pickle`. All code was reviewed and released by a human maintainer.
