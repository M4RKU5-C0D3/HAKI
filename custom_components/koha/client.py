from __future__ import annotations

import re
from datetime import datetime, date
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientSession


class KohaAuthError(Exception):
    pass


class KohaParseError(Exception):
    pass


class Checkout:
    __slots__ = (
        "title",
        "author",
        "due_date",
        "barcode",
        "renewals_used",
        "renewals_max",
        "item_id",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for s in self.__slots__:
            if not hasattr(self, s):
                setattr(self, s, None)

    @property
    def is_overdue(self) -> bool:
        if self.due_date is None:
            return False
        due = self.due_date.date() if isinstance(self.due_date, datetime) else self.due_date
        return due < date.today()

    @property
    def is_due_today(self) -> bool:
        if self.due_date is None:
            return False
        due = self.due_date.date() if isinstance(self.due_date, datetime) else self.due_date
        return due == date.today()


class CheckoutTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.checkouts: list[dict[str, Any]] = []
        self._in_table = False
        self._in_row = False
        self._in_td = False
        self._td_class = ""
        self._td_text = ""
        self._current: dict[str, Any] = {}
        self._title_span = False
        self._in_label = False
        self._td_data_order = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and a.get("id") == "checkoutst":
            self._in_table = True
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._current = {}
        if tag == "td" and self._in_row:
            self._in_td = True
            self._td_class = a.get("class", "")
            self._td_data_order = a.get("data-order", "")
            self._td_text = ""
        if tag == "span" and self._in_td and "biblio-title" in self._td_class:
            self._title_span = True
        if tag == "span" and self._in_td and a.get("class") == "tdlabel":
            self._in_label = True
        if tag == "a" and self._in_td and "renew" in self._td_class:
            href = a.get("href", "")
            m = re.search(r'[?&]item=(\d+)', href)
            if m:
                self._current["item_id"] = int(m.group(1))

    def handle_endtag(self, tag):
        if not self._in_table:
            return
        if tag == "table":
            self._in_table = False
            return
        if tag == "tr" and self._in_row:
            self._in_row = False
            if self._current.get("title") or self._current.get("barcode"):
                self.checkouts.append(self._current)
            self._current = {}
            return
        if tag == "td" and self._in_td:
            self._in_td = False
            text = self._td_text.strip()
            cls = self._td_class
            if "title" in cls:
                self._current["title"] = text
            elif "author" in cls:
                self._current["author"] = text
            elif "date_due" in cls:
                raw = self._td_data_order
                if raw:
                    try:
                        self._current["due_date"] = datetime.strptime(raw[:10], "%Y-%m-%d").date()
                    except ValueError:
                        self._current["due_date"] = text
                else:
                    self._current["due_date"] = text
            elif "barcode" in cls:
                self._current["barcode"] = text
            elif "renew" in cls:
                m = re.search(r"(\d+)\s*v[oö]n\s*(\d+)", text, re.IGNORECASE)
                if m:
                    total = int(m.group(2))
                    remaining = int(m.group(1))
                    self._current["renewals_max"] = total
                    self._current["renewals_used"] = total - remaining
            self._td_text = ""
            self._td_class = ""
            self._td_data_order = ""
            return
        if tag == "span" and self._title_span:
            self._title_span = False
        if tag == "span" and self._in_label:
            self._in_label = False

    def handle_data(self, data):
        if self._title_span:
            self._td_text += data
        elif self._in_td and not self._title_span and not self._in_label:
            self._td_text += data


class KohaClient:
    def __init__(self, session: ClientSession, url: str, userid: str, password: str):
        self._session = session
        self._url = url.rstrip("/")
        self._userid = userid
        self._password = password

    async def login(self) -> None:
        resp = await self._session.post(
            f"{self._url}/cgi-bin/koha/opac-user.pl",
            data={"userid": self._userid, "password": self._password},
            allow_redirects=True,
        )
        if resp.status != 200:
            raise KohaAuthError(f"Login returned HTTP {resp.status}")
        cgisessid = resp.cookies.get("CGISESSID")
        if not cgisessid:
            raise KohaAuthError("No CGISESSID cookie received — login failed")

    async def get_checkouts(self) -> list[Checkout]:
        resp = await self._session.get(
            f"{self._url}/cgi-bin/koha/opac-user.pl",
            allow_redirects=True,
        )
        if resp.status != 200:
            raise KohaParseError(f"OPAC page returned HTTP {resp.status}")
        html = await resp.text()
        parser = CheckoutTableParser()
        parser.feed(html)
        return [Checkout(**c) for c in parser.checkouts]
