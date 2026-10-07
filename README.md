# xuanlocatbu.github.io

Personal website of Xuan-Loc Huynh — https://xuanlocatbu.github.io

## Publishing a writing (passcode-protected)

1. Write a plain text file in `_drafts/` (this folder is never committed), e.g. `_drafts/my-essay.txt`:

   ```
   Title: My essay
   Date: 2026-10-06
   Summary: Optional one-line teaser

   First paragraph...

   Second paragraph...
   ```

   The title, date and summary are public; only the body is encrypted.

2. Encrypt it (you'll be asked for a passcode):

   ```
   .venv/bin/python tools/publish_writing.py _drafts/my-essay.txt
   ```

3. Commit and push:

   ```
   git add . && git commit -m "Add writing: My essay" && git push
   ```

To update a writing, edit the draft and run step 2 again. To remove one, delete
`writings/<name>.html` and run `.venv/bin/python tools/publish_writing.py --rebuild`.

First-time setup on a new computer:

```
python3 -m venv .venv && .venv/bin/pip install cryptography
```
