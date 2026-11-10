"""Fetch one page of FireAnt news and discussions and save it to SQLite.

    python examples/fireant.py            # MSR, ./fireant_posts.db
    python examples/fireant.py FPT /tmp/fireant.db

Requires network access. Run again to update previously saved posts.
"""
import json
import sqlite3
import sys

from vn_market_data import FireAntSource, SourceUnavailable


def main():
    symbol = sys.argv[1].strip().upper() if len(sys.argv) > 1 else "MSR"
    path = sys.argv[2] if len(sys.argv) > 2 else "fireant_posts.db"
    source = FireAntSource()
    try:
        news = source.get_news(symbol)
        discussions = source.get_discussions(symbol)
    except SourceUnavailable as exc:
        print(f"FireAnt unavailable: {exc}", file=sys.stderr)
        return 1

    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS fireant_posts (
            post_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            category TEXT NOT NULL,
            data TEXT NOT NULL,
            fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (post_id, symbol, category)
        )""")
        for category, posts in (("news", news), ("discussion", discussions)):
            db.executemany("""INSERT INTO fireant_posts (post_id, symbol, category, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(post_id, symbol, category) DO UPDATE SET
                    data = excluded.data, fetched_at = CURRENT_TIMESTAMP""",
                [(post["postID"], symbol, category, json.dumps(post, ensure_ascii=False))
                 for post in posts])

    print(f"{symbol}: saved {len(news)} news items and {len(discussions)} discussions to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
