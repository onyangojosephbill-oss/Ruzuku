#!/usr/bin/env python3
"""Refresh data/grants.json from the feeds listed in data/sources.json.

Uses only the Python standard library. Entries you wrote by hand ("auto": false)
are never changed. Entries found by this script are marked "auto": true so the
site can show that nobody has checked them yet.

Usage:
    python scripts/update_grants.py              # update data/grants.json
    python scripts/update_grants.py --dry-run    # show what would change
"""
import argparse
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = "RuzukuUpdater/1.0 (research grant directory)"
MAX_AGE_NO_DEADLINE_DAYS = 120   # items with no deadline are dropped after this long
KEEP_AFTER_DEADLINE_DAYS = 90    # auto entries stay visible as "closed" this long
MAX_AUTO_ENTRIES = 300

GRANT_WORDS = re.compile(
    r"\b(grants?|fellowships?|call for (?:proposals?|applications?|expressions? of interest)|"
    r"research funding|funding (?:call|opportunit\w+|alert)|seed fund\w*|research awards?|"
    r"calls? for research|small grants?)\b", re.I)
NOISE_TITLE = re.compile(
    r"\b(jobs?|vacanc\w+|internships?|recruitment|hiring|webinar|tender|consultan\w+|"
    r"admissions?|scholarships? for (?:undergraduate|bachelor)|call for reviewers|call for posters?)\b", re.I)
REGION = re.compile(
    r"\b(africa\w*|kenya\w*|east africa|sub-saharan|developing countries|low- and middle-income|"
    r"lmics?|global south|all nationalities|worldwide|international applicants)\b", re.I)

CATEGORIES = {
    "humanities": r"social science|humanit|sociolog|anthropolog|histor(?:y|ical)|cultur|governance|gender|"
                  r"education|peace|migration|community|poverty|law\b|legal|economic|psycholog|policy|"
                  r"youth|livelihood|informal settlement",
    "health": r"health|vaccin|disease|medic|clinical|malaria|hiv\b|tubercul|biolog|genom|epidemi|"
              r"nutrition|biotech|pharma|cancer|maternal|mental",
    "physical": r"physics|chemistry|engineering|energy|mathematic|computer|artificial intelligence|\bai\b|"
                r"materials|space|digital|data science|technology|innovation|mineral|robotic",
    "environment": r"climate|environment|agricultur|food|water|biodiversity|forest|ecolog|conservation|"
                   r"drought|flood|disaster|adaptation|sustainab|resilience|livestock|fisher",
}

MONTH = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
         r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
DMY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MONTH + r"\.?,?\s+(\d{4})", re.I)
MDY = re.compile(MONTH + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I)
ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
CUE = re.compile(
    r"(deadline|closing date|closes?|apply by|applications? (?:close|are due|due)|due (?:date|by|on)|"
    r"submit\w* by|submission date|last date)", re.I)
MONTH_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

MONEY_PREFIX = re.compile(
    r"((?:up to|maximum of|max\.?|worth|of)\s+)?"
    r"((?:USD|US\$|EUR|GBP|CHF|KES|KSh|Ksh|€|£|\$)\s?\d[\d,.]*(?:\s?(?:million|billion|m|k)\b)?)", re.I)
MONEY_SUFFIX = re.compile(
    r"((?:up to|maximum of|worth|of)\s+)?(\d[\d,.]*(?:\s?(?:million|k))?\s?(?:USD|EUR|GBP|CHF|KES))\b", re.I)


def log(msg):
    print(msg, flush=True)


def fetch(url):
    req = Request(url, headers={"User-Agent": UA,
                                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urlopen(req, timeout=30) as resp:
        return resp.read()


def local(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def parse_feed(raw):
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        rec = {"title": "", "link": "", "date": "", "text": ""}
        for ch in el:
            name = local(ch.tag)
            if name == "title":
                rec["title"] = (ch.text or "").strip()
            elif name == "link":
                href = ch.attrib.get("href")
                if href and ch.attrib.get("rel", "alternate") == "alternate":
                    rec["link"] = href.strip()
                elif ch.text and not rec["link"]:
                    rec["link"] = ch.text.strip()
            elif name in ("pubdate", "published", "updated", "date"):
                if not rec["date"]:
                    rec["date"] = (ch.text or "").strip()
            elif name in ("description", "summary", "content", "encoded"):
                if len(ch.text or "") > len(rec["text"]):
                    rec["text"] = ch.text or ""
        if rec["title"] and rec["link"]:
            items.append(rec)
    return items


def clean(markup):
    text = re.sub(r"<[^>]+>", " ", markup or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_pub(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.date()


def to_iso(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def find_deadline(text):
    """Return the first date that follows a cue word such as 'Deadline:' or 'apply by'."""
    for cue in CUE.finditer(text):
        window = text[cue.end(): cue.end() + 90]
        hits = []
        for m in DMY.finditer(window):
            hits.append((m.start(), to_iso(m.group(3), MONTH_NUM[m.group(2)[:3].lower()], m.group(1))))
        for m in MDY.finditer(window):
            hits.append((m.start(), to_iso(m.group(3), MONTH_NUM[m.group(1)[:3].lower()], m.group(2))))
        for m in ISO.finditer(window):
            hits.append((m.start(), to_iso(m.group(1), m.group(2), m.group(3))))
        hits = [h for h in hits if h[1]]
        if hits:
            return min(hits)[1]
    return None


def find_amount(text):
    for rx in (MONEY_PREFIX, MONEY_SUFFIX):
        m = rx.search(text)
        if m:
            amount = m.group(2).strip().rstrip(".,")
            lead = (m.group(1) or "").strip().lower()
            if lead.startswith(("up to", "maximum", "max")):
                return "Up to " + amount
            return amount
    return "Not stated in the announcement"


def classify(text):
    found = [c for c, rx in CATEGORIES.items() if re.search(rx, text, re.I)]
    return found[:3] or ["any"]


def norm_url(u):
    return re.sub(r"[?#].*$", "", (u or "").strip().lower()).rstrip("/")


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def build_entry(item, source, today, pub):
    body = clean(item["text"])
    title = clean(item["title"])
    blob = f"{title}. {body}"
    scope = "kenya" if re.search(r"\bkenya\w*\b", title, re.I) else source.get("scope", "international")
    deadline = find_deadline(blob)
    kind = "Fellowship" if re.search(r"fellowship", blob[:400], re.I) else "Research grant"
    summary = body[:240].rsplit(" ", 1)[0] + ("..." if len(body) > 240 else "") if body else title
    return {
        "id": hashlib.sha1(norm_url(item["link"]).encode()).hexdigest()[:10],
        "title": title,
        "funder": source["name"],
        "scope": scope,
        "cats": classify(blob),
        "type": kind,
        "deadline": deadline,
        "amount": find_amount(blob),
        "who": "Not stated in the announcement. Open the funder page for eligibility.",
        "summary": summary,
        "note": f"Found automatically on {today.isoformat()}. A person has not checked this entry, so confirm the details on the funder page.",
        "url": item["link"],
        "src": f"{source['name']} (auto-found)",
        "auto": True,
        "found": today.isoformat(),
    }


def keep_item(item, source):
    title = clean(item["title"])
    body = clean(item["text"])
    if NOISE_TITLE.search(title):
        return False
    if not GRANT_WORDS.search(title + " " + body[:400]):
        return False
    if source.get("require_region") and not REGION.search(title + " " + body):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--today", help="override today's date, YYYY-MM-DD (for testing)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    data_path = root / "data" / "grants.json"
    config = json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()

    store = json.loads(data_path.read_text(encoding="utf-8"))
    grants = store["grants"]
    seen_urls = {norm_url(g["url"]) for g in grants}
    seen_titles = {norm_title(g["title"]) for g in grants}
    ignore = {norm_url(u) for u in config.get("ignore_urls", [])}

    added, failed = [], 0
    for source in config["sources"]:
        name = source["name"]
        try:
            items = parse_feed(fetch(source["url"]))
        except (HTTPError, URLError, ET.ParseError, TimeoutError, OSError) as exc:
            failed += 1
            log(f"[skip] {name}: could not read {source['url']} ({exc})")
            continue
        kept = 0
        for item in items:
            url_key, title_key = norm_url(item["link"]), norm_title(item["title"])
            if url_key in ignore or url_key in seen_urls or title_key in seen_titles:
                continue
            if not keep_item(item, source):
                continue
            pub = parse_pub(item["date"])
            entry = build_entry(item, source, today, pub)
            if entry["deadline"]:
                if date.fromisoformat(entry["deadline"]) < today:
                    continue  # already closed when found
            elif pub and (today - pub).days > MAX_AGE_NO_DEADLINE_DAYS:
                continue
            grants.append(entry)
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            added.append(entry)
            kept += 1
        log(f"[ok]   {name}: {len(items)} items read, {kept} new entries")

    # Tidy old auto-found entries. Hand-written entries are never removed.
    def stale(g):
        if not g.get("auto"):
            return False
        if g.get("deadline"):
            return date.fromisoformat(g["deadline"]) < today - timedelta(days=KEEP_AFTER_DEADLINE_DAYS)
        found = date.fromisoformat(g.get("found", today.isoformat()))
        return (today - found).days > MAX_AGE_NO_DEADLINE_DAYS

    before = len(grants)
    grants[:] = [g for g in grants if not stale(g)]
    removed = before - len(grants)

    auto = [g for g in grants if g.get("auto")]
    if len(auto) > MAX_AUTO_ENTRIES:
        auto.sort(key=lambda g: g.get("found", ""), reverse=True)
        drop = {g["id"] for g in auto[MAX_AUTO_ENTRIES:]}
        grants[:] = [g for g in grants if g["id"] not in drop]

    log(f"Added {len(added)}, removed {removed} old auto-found entries, {len(grants)} in total.")
    if failed == len(config["sources"]):
        print("::warning::Ruzuku could not read any feed. The site was left unchanged. Check data/sources.json.")
        return 0
    if added or removed:
        store["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.dry_run:
        log("Dry run: nothing written.")
        return 0
    data_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
