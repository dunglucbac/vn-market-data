"""FireAnt market turnover, ticker news, community posts and replies.

The API returns total and put-through value in VND, newest first. Its price
adjustment semantics are not established, so this source does not serve candles.
"""
import json
import math
import re
from datetime import date

import httpx

from vn_market_data.sources.base import DataSource, SourceUnavailable
from vn_market_data.sources.http import get_capped, post_capped

_BASE = "https://api.fireant.vn"
_PAGE_SIZE = 20
_MAX_PAGES = 1000
_TIMEOUT = 15.0


class FireAntSource(DataSource):
    name = "fireant"

    def get_market_turnover(self, index: str, start: str, end: str) -> list[dict]:
        index = index.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", index):
            raise ValueError("invalid index symbol")
        try:
            lo, hi = date.fromisoformat(start), date.fromisoformat(end)
        except (TypeError, ValueError):
            raise ValueError("start and end must be ISO dates") from None
        if lo > hi:
            return []
        try:
            token = self._anonymous_token()
            rows = []
            seen = set()
            for page in range(_MAX_PAGES):
                status, body = get_capped(
                    f"{_BASE}/symbols/{index}/historical-quotes",
                    params={"startDate": start, "endDate": end, "offset": page * _PAGE_SIZE,
                            "limit": _PAGE_SIZE},
                    headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT,
                    what="fireant market turnover")
                if status != 200:
                    raise SourceUnavailable(f"fireant market turnover: HTTP {status}")
                try:
                    data = json.loads(body)
                    if not isinstance(data, list) or len(data) > _PAGE_SIZE:
                        raise ValueError
                    for row in data:
                        day = date.fromisoformat(row["date"][:10])
                        total, put, volume = (float(row[k]) for k in
                                              ("totalValue", "putthroughValue", "totalVolume"))
                        if (row["symbol"].upper() != index or not lo <= day <= hi or
                                day in seen or not all(math.isfinite(x) and x >= 0
                                                       for x in (total, put, volume)) or put > total):
                            raise ValueError
                        seen.add(day)
                        rows.append({"date": day.isoformat(), "value": total,
                                     "matched": total - put, "put_through": put,
                                     "volume": volume})
                except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                    raise SourceUnavailable("fireant market turnover: invalid response") from None
                if len(data) < _PAGE_SIZE:
                    return sorted(rows, key=lambda row: row["date"])
            raise SourceUnavailable("fireant market turnover: pagination limit reached")
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"fireant network error: {e}") from None

    def _anonymous_token(self) -> str:
        try:
            status, body = post_capped(f"{_BASE}/authentication/anonymous-login", json={},
                                       timeout=_TIMEOUT, what="fireant login")
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"fireant login network error: {e}") from None
        if status != 200:
            raise SourceUnavailable(f"fireant login: HTTP {status}")
        try:
            payload = json.loads(body)
            token = payload.get("accessToken") if isinstance(payload, dict) else None
        except ValueError:
            token = None
        if not isinstance(token, str) or not token:
            raise SourceUnavailable("fireant login: missing access token")
        return token

    def get_news(self, symbol: str, *, offset: int = 0, limit: int = 20) -> list[dict]:
        """One page of FireAnt news about a symbol, in the provider's original shape."""
        return self._symbol_posts(symbol, 1, offset, limit)

    def get_discussions(self, symbol: str, *, offset: int = 0, limit: int = 20) -> list[dict]:
        """One page of FireAnt community posts about a symbol."""
        return self._symbol_posts(symbol, 0, offset, limit)

    def get_replies(self, post_id: int, *, offset: int = 0, limit: int = 20) -> list[dict]:
        """One page of replies to a FireAnt post."""
        if type(post_id) is not int or post_id <= 0:
            raise ValueError("post_id must be a positive integer")
        return self._posts_page(f"/posts/{post_id}/replies", offset, limit)

    def _symbol_posts(self, symbol, kind, offset, limit):
        symbol = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", symbol):
            raise ValueError("invalid symbol")
        return self._posts_page(f"/symbols/{symbol}/posts", offset, limit, kind=kind)

    def _posts_page(self, path, offset, limit, *, kind=None):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("offset must be nonnegative and limit must be between 1 and 20")
        token = self._anonymous_token()
        params = {"offset": offset, "limit": limit}
        if kind is not None:
            params["type"] = kind
        try:
            status, body = get_capped(f"{_BASE}{path}", params=params,
                                      headers={"Authorization": f"Bearer {token}"},
                                      timeout=_TIMEOUT, what="fireant posts")
        except httpx.HTTPError as e:
            raise SourceUnavailable(f"fireant posts network error: {e}") from None
        if status != 200:
            raise SourceUnavailable(f"fireant posts: HTTP {status}")
        try:
            posts = json.loads(body)
            if (not isinstance(posts, list) or len(posts) > limit or
                    any(not isinstance(post, dict) or type(post.get("postID")) is not int
                        for post in posts)):
                raise ValueError
        except (ValueError, TypeError):
            raise SourceUnavailable("fireant posts: invalid response") from None
        return posts
