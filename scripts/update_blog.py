#!/usr/bin/env python3
"""Refresh the latest-posts list in README.md from the tegarprayuda.com RSS feed.

Rewrites only the lines between the BLOG:START and BLOG:END markers. Leaves
README.md untouched when the feed cannot be read or has no posts, so a site
outage never blanks the section.

    python scripts/update_blog.py                   # fetch the live feed
    python scripts/update_blog.py --feed feed.xml   # use a saved copy
"""
import argparse
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEED_URL = "https://tegarprayuda.com/feed"
README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
START, END = "<!-- BLOG:START -->", "<!-- BLOG:END -->"
COUNT = 3


def read_feed(path):
    if path:
        with open(path, "rb") as fh:
            return fh.read()
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "TegarTheGreat-profile-readme"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def escape_md(text):
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("|", "\\|")


def render(items):
    lines = []
    for item in items:
        title = escape_md(" ".join(item.findtext("title", "").split()))
        link = item.findtext("link", "").strip()
        category = item.findtext("category", "").strip()
        date = parsedate_to_datetime(item.findtext("pubDate")).strftime("%d %b %Y")
        meta = " · ".join(filter(None, [category, date]))
        lines.append(f"- **[{title}]({link})**  \n  <sub>{meta}</sub>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", help="read the RSS from a file instead of the network")
    args = parser.parse_args()

    try:
        root = ET.fromstring(read_feed(args.feed))
    except Exception as exc:  # network error, bad XML: keep the current list
        print(f"Could not read the feed ({exc}); README left as is.")
        return 0
    items = root.findall("./channel/item")
    items.sort(key=lambda i: parsedate_to_datetime(i.findtext("pubDate")), reverse=True)
    if not items:
        print("Feed has no posts; README left as is.")
        return 0

    with open(README, encoding="utf-8") as fh:
        readme = fh.read()
    if START not in readme or END not in readme:
        print("BLOG markers not found in README.md", file=sys.stderr)
        return 1
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    updated = f"{head}{START}\n{render(items[:COUNT])}\n{END}{tail}"
    if updated != readme:
        with open(README, "w", encoding="utf-8") as fh:
            fh.write(updated)
        print(f"Updated with {min(COUNT, len(items))} posts.")
    else:
        print("Already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
