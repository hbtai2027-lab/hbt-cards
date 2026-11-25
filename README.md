# HBT digital business cards

Each person gets their own page and their own QR code, all hosted from **one** GitHub account and **one** repository.

```
https://YOUR-GITHUB-USERNAME.github.io/hbt-cards/dinesh-mani/
https://YOUR-GITHUB-USERNAME.github.io/hbt-cards/next-person/
```

## One-time setup (GitHub Pages)

1. Create a **public** repository named `hbt-cards` in your GitHub account.
2. Upload everything in this folder (Add file → Upload files).
3. Settings → Pages → Source: **Deploy from a branch**, Branch: `main`, folder `/ (root)` → Save.
4. Wait 1–2 minutes. Your pages are live at `https://YOUR-GITHUB-USERNAME.github.io/hbt-cards/<slug>/`.

## Adding a person

1. In `people.json`, set `base_url` to your real address (once), then copy the Dinesh block and change the details. Put their photo in `photos/` and set `"photo": "photos/<slug>.jpg"` (leave it out to show initials instead). The `slug` becomes the web address, e.g. `"slug": "priya-kumar"`.
2. Run `python build.py` (needs `pip install pillow opencv-python`).
3. Upload the new `<slug>/` folder and `qr/<slug>.png` to the repo.

The script checks that every QR scans back to the right link before it finishes.

## Notes

- Changing someone's phone number or text later doesn't need a new QR: edit `people.json`, rebuild, re-upload their `index.html`. The QR only holds the link.
- Renaming the repo or your GitHub username changes the link, so every QR would need regenerating. Pick them once.
- GitHub Pages on a free account requires a public repo, so these pages are public — fine for business-card info.
