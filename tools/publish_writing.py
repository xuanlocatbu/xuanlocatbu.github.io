#!/usr/bin/env python3
"""Encrypt a writing with a passcode and publish it to writings/.

Usage:
  .venv/bin/python tools/publish_writing.py _drafts/my-essay.txt   # encrypt one draft (asks for a passcode)
  .venv/bin/python tools/publish_writing.py --rebuild              # only refresh the list on writings/index.html

Draft format (plain text, saved in _drafts/, which is never committed):

  Title: My essay
  Date: 2026-10-06
  Summary: Optional one-line teaser

  First paragraph...

  Second paragraph...

The title, date and summary are PUBLIC (they appear on the Writings list).
Only the body is encrypted. The output file is named after the draft,
so re-running on the same draft replaces the published version.
"""
import argparse
import base64
import getpass
import hashlib
import html
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent.parent
WRITINGS = ROOT / "writings"
INDEX = WRITINGS / "index.html"
ITERATIONS = 600_000
AUTHOR = "Xuan-Loc Huynh"

LIST_START = "<!-- WRITINGS:START -->"
LIST_END = "<!-- WRITINGS:END -->"


def parse_draft(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").lstrip("﻿")
    header, _, body = text.partition("\n\n")
    meta = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            sys.exit(f"Bad header line in {path}: {line!r}\n(Expected 'Key: value', then a blank line, then the body.)")
        meta[key.strip().lower()] = value.strip()
    if not meta.get("title"):
        sys.exit(f"{path} needs a 'Title:' line at the top.")
    if not body.strip():
        sys.exit(f"{path} has no body text after the header.")
    meta.setdefault("date", date.today().isoformat())
    meta.setdefault("summary", "")
    return meta, body


def body_to_html(body):
    paragraphs = re.split(r"\n\s*\n", body.strip())
    return "\n".join(
        "<p>" + html.escape(p.strip()).replace("\n", "<br>\n") + "</p>" for p in paragraphs
    )


def encrypt(plaintext, passcode):
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", passcode.encode("utf-8"), salt, ITERATIONS, 32)
    ciphertext = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"salt": b64(salt), "iv": b64(iv), "ct": b64(ciphertext), "iter": ITERATIONS}


def pretty_date(iso):
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d:%B} {d.day}, {d.year}"


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex">
  <title>{{TITLE}} — {{AUTHOR}}</title>
  <meta name="writing-title" content="{{TITLE}}">
  <meta name="writing-date" content="{{DATE}}">
  <meta name="writing-summary" content="{{SUMMARY}}">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <header class="site-header">
    <nav class="container nav">
      <ul class="nav-links">
        <li><a href="../index.html#about">About</a></li>
        <li><a href="../index.html#projects">Projects</a></li>
        <li><a href="index.html" aria-current="page">Writings</a></li>
        <li><a href="../index.html#contact">Contact</a></li>
      </ul>
    </nav>
  </header>

  <main class="section container">
    <a class="back-link" href="index.html">← All writings</a>
    <h1 class="writing-title">{{TITLE}}</h1>
    <p class="writing-meta">{{PRETTY_DATE}}</p>

    <form id="unlock" class="lock">
      <p><i class="fa-solid fa-lock"></i> This writing is protected. Enter the passcode to read it.</p>
      <div class="lock-row">
        <input id="passcode" type="password" placeholder="Passcode" autocomplete="off" required aria-label="Passcode">
        <button class="btn" type="submit">Unlock</button>
      </div>
      <p id="lock-error" class="lock-error" hidden>Incorrect passcode. Please try again.</p>
    </form>

    <article id="content" class="prose" hidden></article>
  </main>

  <footer class="site-footer">
    <div class="container">
      <p>&copy; <span id="year"></span> {{AUTHOR}}</p>
    </div>
  </footer>

  <script id="payload" type="application/json">{{PAYLOAD}}</script>
  <script>
    document.getElementById("year").textContent = new Date().getFullYear();

    const payload = JSON.parse(document.getElementById("payload").textContent);
    const bytes = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
    const form = document.getElementById("unlock");
    const input = document.getElementById("passcode");
    const error = document.getElementById("lock-error");
    const button = form.querySelector("button");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      error.hidden = true;
      button.disabled = true;
      button.textContent = "Unlocking…";
      try {
        const baseKey = await crypto.subtle.importKey(
          "raw", new TextEncoder().encode(input.value), "PBKDF2", false, ["deriveKey"]);
        const key = await crypto.subtle.deriveKey(
          { name: "PBKDF2", salt: bytes(payload.salt), iterations: payload.iter, hash: "SHA-256" },
          baseKey, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
        const plain = await crypto.subtle.decrypt(
          { name: "AES-GCM", iv: bytes(payload.iv) }, key, bytes(payload.ct));
        const content = document.getElementById("content");
        content.innerHTML = new TextDecoder().decode(plain);
        content.hidden = false;
        form.hidden = true;
      } catch {
        error.hidden = false;
        input.select();
      } finally {
        button.disabled = false;
        button.textContent = "Unlock";
      }
    });
  </script>
</body>
</html>
"""


def render_page(meta, payload):
    esc = lambda s: html.escape(s, quote=True)
    return (
        PAGE.replace("{{TITLE}}", esc(meta["title"]))
        .replace("{{DATE}}", esc(meta["date"]))
        .replace("{{PRETTY_DATE}}", esc(pretty_date(meta["date"])))
        .replace("{{SUMMARY}}", esc(meta["summary"]))
        .replace("{{AUTHOR}}", AUTHOR)
        .replace("{{PAYLOAD}}", json.dumps(payload))
    )


def read_meta(page, name):
    m = re.search(rf'<meta name="{name}" content="([^"]*)">', page)
    return m.group(1) if m else ""


def rebuild_index():
    entries = []
    for path in WRITINGS.glob("*.html"):
        if path.name == "index.html":
            continue
        page = path.read_text(encoding="utf-8")
        title = read_meta(page, "writing-title")
        if not title:
            continue
        entries.append((read_meta(page, "writing-date"), title, read_meta(page, "writing-summary"), path.name))
    entries.sort(reverse=True)

    if entries:
        items = []
        for iso, title, summary, filename in entries:
            # Values were HTML-escaped when the page was written, so they are safe to reuse as-is.
            summary_html = f"\n            <p>{summary}</p>" if summary else ""
            items.append(
                f"""        <li>
          <a class="card writing-card" href="{filename}">
            <h3>{title}</h3>
            <p class="writing-meta"><i class="fa-solid fa-lock"></i> {html.escape(pretty_date(html.unescape(iso)))}</p>{summary_html}
          </a>
        </li>"""
            )
        block = '<ul class="writing-list">\n' + "\n".join(items) + "\n      </ul>"
    else:
        block = '<p class="empty">No writings yet — check back soon.</p>'

    index = INDEX.read_text(encoding="utf-8")
    start, end = index.index(LIST_START) + len(LIST_START), index.index(LIST_END)
    INDEX.write_text(index[:start] + "\n      " + block + "\n      " + index[end:], encoding="utf-8")
    return len(entries)


def ask_passcode():
    first = getpass.getpass("Passcode for this writing: ")
    if not first:
        sys.exit("Passcode can't be empty.")
    if getpass.getpass("Type it again: ") != first:
        sys.exit("Passcodes didn't match. Nothing was published.")
    return first


def main():
    parser = argparse.ArgumentParser(description="Encrypt and publish a writing.")
    parser.add_argument("draft", nargs="?", type=Path, help="path to a draft .txt file")
    parser.add_argument("--rebuild", action="store_true", help="only refresh the list on writings/index.html")
    parser.add_argument("--passcode", help="passcode (otherwise you'll be asked; avoids showing it on screen)")
    args = parser.parse_args()

    if args.draft:
        meta, body = parse_draft(args.draft)
        passcode = args.passcode or ask_passcode()
        out = WRITINGS / (re.sub(r"[^a-z0-9-]+", "-", args.draft.stem.lower()).strip("-") + ".html")
        out.write_text(render_page(meta, encrypt(body_to_html(body), passcode)), encoding="utf-8")
        print(f"Published {out.relative_to(ROOT)}")
    elif not args.rebuild:
        parser.error("give a draft file, or --rebuild")

    count = rebuild_index()
    print(f"Writings list updated ({count} writing{'s' if count != 1 else ''}).")


if __name__ == "__main__":
    main()
