#!/usr/bin/env python3
"""Add (or replace) one episode in feed.xml and push to GitHub Pages.

usage:
  python3 scripts/add_episode.py --file briefing.mp3 --id 2026-11-02-pm \
      --title '[저녁] 11/2(월) ...' --desc '...' --seconds 431 \
      [--pubdate '2026-11-02T20:58:00+09:00'] [--no-push] [--remove]

- copies the mp3 to episodes/<id>.mp3
- puts the <item> at the top of feed.xml (same guid -> replaced)
- keeps only the newest MAX_ITEMS items in the feed (mp3 files are never deleted)
- git add -A / commit / push to main (on failure: pull --rebase, retry once)
--remove drops the item with that id from the feed (file kept) and pushes.
Exit code: 0 ok, 2 push failed (feed committed locally), 1 other error.
"""
import argparse
import email.utils
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

BASE_URL = "https://jnnkyng.github.io/vb-feed-7k2m/"
MAX_ITEMS = 60
KST = timezone(timedelta(hours=9))
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(am|pm)$")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(ROOT, "feed.xml")


def it(tag):
    return "{%s}%s" % (ITUNES, tag)


def new_feed():
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    for tag, text in [
        ("title", "Valley 브리핑"),
        ("link", BASE_URL),
        ("language", "ko"),
        ("description", "매일 아침 08:30·저녁 20:50 KST 자동 생성되는 한국어 투자 브리핑. 분석·관찰이며 투자 권유가 아님"),
    ]:
        ET.SubElement(ch, tag).text = text
    ET.SubElement(ch, "{%s}link" % ATOM, {"href": BASE_URL + "feed.xml", "rel": "self", "type": "application/rss+xml"})
    ET.SubElement(ch, it("author")).text = "Claude"
    ET.SubElement(ch, it("summary")).text = ch.find("description").text
    ET.SubElement(ch, it("image"), {"href": BASE_URL + "cover.png"})
    ET.SubElement(ch, it("explicit")).text = "false"
    ET.SubElement(ch, it("type")).text = "episodic"
    cat = ET.SubElement(ch, it("category"), {"text": "Business"})
    ET.SubElement(cat, it("category"), {"text": "Investing"})
    return ET.ElementTree(rss)


def load_feed():
    if os.path.exists(FEED):
        return ET.parse(FEED)
    return new_feed()


def git(*args, check=True):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), (r.stderr or r.stdout).strip()[-400:]))
    return r


def push(msg):
    if not git("config", "user.email", check=False).stdout.strip():
        git("config", "user.email", "claude-feed-bot@users.noreply.github.com")
        git("config", "user.name", "Valley feed bot")
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("nothing to commit")
        return True
    git("commit", "-q", "-m", msg)
    for attempt in (1, 2):
        r = git("push", "origin", "HEAD:main", check=False)
        if r.returncode == 0:
            print("pushed (attempt %d)" % attempt)
            return True
        print("push failed: " + (r.stderr or r.stdout).strip()[-300:], file=sys.stderr)
        if attempt == 1:
            pr = git("pull", "--rebase", "origin", "main", check=False)
            if pr.returncode != 0:
                git("rebase", "--abort", check=False)
                print("pull --rebase failed: " + (pr.stderr or pr.stdout).strip()[-300:], file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--file")
    ap.add_argument("--title")
    ap.add_argument("--desc", default="")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--pubdate", help="ISO 8601 with offset; default = now KST")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    ep_id = a.id.strip()
    if not ID_RE.match(ep_id) and not ep_id.startswith("test-"):
        sys.exit("bad --id %r (want YYYY-MM-DD-am|pm)" % ep_id)

    tree = load_feed()
    ch = tree.getroot().find("channel")
    guid_of = lambda item: (item.findtext("guid") or "").strip()
    for item in [i for i in ch.findall("item") if guid_of(i) in (ep_id, ep_id + ".mp3")]:
        ch.remove(item)

    if not a.remove:
        if not (a.file and a.title and a.seconds is not None):
            sys.exit("--file, --title, --seconds are required")
        os.makedirs(os.path.join(ROOT, "episodes"), exist_ok=True)
        dest = os.path.join(ROOT, "episodes", ep_id + ".mp3")
        if os.path.abspath(a.file) != os.path.abspath(dest):
            shutil.copyfile(a.file, dest)
        size = os.path.getsize(dest)
        pub = datetime.fromisoformat(a.pubdate) if a.pubdate else datetime.now(KST)
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=KST)
        pub = pub.astimezone(KST)

        item = ET.Element("item")
        ET.SubElement(item, "title").text = a.title
        ET.SubElement(item, "description").text = a.desc
        ET.SubElement(item, it("summary")).text = a.desc
        ET.SubElement(item, "pubDate").text = email.utils.format_datetime(pub)
        ET.SubElement(item, "enclosure", {"url": BASE_URL + "episodes/" + ep_id + ".mp3",
                                           "length": str(size), "type": "audio/mpeg"})
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = ep_id
        ET.SubElement(item, it("duration")).text = str(int(round(a.seconds)))
        ET.SubElement(item, it("explicit")).text = "false"
        ET.SubElement(item, it("episodeType")).text = "full"

        # insert before the first existing item (= top of the list)
        kids = list(ch)
        first = next((i for i, k in enumerate(kids) if k.tag == "item"), len(kids))
        ch.insert(first, item)

    # newest MAX_ITEMS by pubDate
    items = ch.findall("item")
    key = lambda i: email.utils.parsedate_to_datetime(i.findtext("pubDate"))
    items_sorted = sorted(items, key=key, reverse=True)
    for i in items:
        ch.remove(i)
    for i in items_sorted[:MAX_ITEMS]:
        ch.append(i)
    ch.find("lastBuildDate") is None and ET.SubElement(ch, "lastBuildDate")
    lbd = ch.find("lastBuildDate")
    ch.remove(lbd)
    lbd.text = email.utils.format_datetime(datetime.now(KST))
    ch.insert(4, lbd)

    ET.indent(tree, "  ")
    tree.write(FEED, encoding="utf-8", xml_declaration=True)
    print("feed.xml: %d items" % len(ch.findall("item")))

    if a.no_push:
        return 0
    ok = push(("remove episode " if a.remove else "episode ") + ep_id)
    if not ok:
        print("FEED_PUSH_FAILED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
