"""Build HBT digital business cards.

For every person in people.json this creates:
  <slug>/index.html   - the page the QR code opens
  <slug>/<slug>.vcf   - "Save contact" file
  qr/<slug>.png       - blue QR code with the HBT logo in the centre

Usage:  python build.py
Needs:  Python 3, Pillow, opencv-python  (pip install pillow opencv-python)
"""
import base64, html, json, os, shutil
from urllib.parse import quote
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
QR_BLUE = (8, 73, 138)          # module colour, matches the sample QR
MODULE_PX = 52                   # size of one QR square in the PNG
QUIET = 2                        # white border, in modules


def qr_matrix(text):
    p = cv2.QRCodeEncoder.Params()
    p.correction_level = cv2.QRCODE_ENCODER_CORRECT_LEVEL_H   # 30% recovery -> room for the logo
    img = cv2.QRCodeEncoder.create(p).encode(text)
    m = img == 0
    rows, cols = np.where(m)
    return m[rows.min():rows.max() + 1, cols.min():cols.max() + 1]


def make_qr(url, out_path, frac=0.30):
    m = qr_matrix(url)
    n = m.shape[0]
    size = (n + 2 * QUIET) * MODULE_PX
    im = Image.new("RGB", (size, size), "white")
    d = ImageDraw.Draw(im)
    for r in range(n):
        for c in range(n):
            if m[r, c]:
                x, y = (c + QUIET) * MODULE_PX, (r + QUIET) * MODULE_PX
                d.rectangle([x, y, x + MODULE_PX - 1, y + MODULE_PX - 1], fill=QR_BLUE)
    # white box in the centre, snapped to whole modules (~ 9% of the code area)
    box_mod = int(n * frac) | 1                      # odd number of modules so it centres
    start = (n - box_mod) // 2
    x0 = (start + QUIET) * MODULE_PX
    x1 = x0 + box_mod * MODULE_PX
    d.rectangle([x0, x0, x1 - 1, x1 - 1], fill="white")
    logo = Image.open(os.path.join(ROOT, "assets", "hbt-logo.png")).convert("RGBA")
    pad = MODULE_PX
    avail = box_mod * MODULE_PX - 2 * pad
    scale = min(avail / logo.width, avail / logo.height)
    logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.LANCZOS)
    im.paste(logo, (x0 + (x1 - x0 - logo.width) // 2, x0 + (x1 - x0 - logo.height) // 2), logo)
    im.save(out_path)
    # verify it scans: two independent readers, at print size and at phone-camera size
    img = cv2.imread(out_path)
    small = cv2.resize(img, (300, 300), interpolation=cv2.INTER_AREA)
    wechat = cv2.wechat_qrcode_WeChatQRCode()
    ok = (url in wechat.detectAndDecode(img)[0] and url in wechat.detectAndDecode(small)[0]
          and cv2.QRCodeDetector().detectAndDecode(small)[0] == url)
    if not ok:
        if frac > 0.20:                      # logo too big for this code: shrink and retry
            return make_qr(url, out_path, round(frac - 0.02, 2))
        raise SystemExit(f"QR check failed for {out_path}")
    return n


def fold(line):
    """vCard lines must be folded at 75 characters."""
    out = [line[:75]]
    line = line[75:]
    while line:
        out.append(" " + line[:74])
        line = line[74:]
    return "\r\n".join(out)


def vcard(p, company, url, photo_path=None):
    first, _, last = p["name"].partition(" ")
    lines = [
        "BEGIN:VCARD", "VERSION:3.0",
        f"N:{last};{first};;;", f"FN:{p['name']}",
        f"ORG:{company}", f"TITLE:{p['designation']}",
        f"EMAIL;TYPE=WORK:{p['email']}",
        f"URL:{url}",
    ]
    if p.get("phone"):
        lines.insert(6, f"TEL;TYPE=CELL:{p['phone']}")
    if p.get("linkedin"):
        lines.append(f"X-SOCIALPROFILE;TYPE=linkedin:{p['linkedin']}")
    if photo_path:
        b64 = base64.b64encode(open(photo_path, "rb").read()).decode()
        lines.append(fold(f"PHOTO;ENCODING=b;TYPE=JPEG:{b64}"))
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


ICONS = {
    "phone": '<path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/>',
    "chat": '<path d="M12 2a10 10 0 0 0-8.66 15l-1.3 4.76 4.88-1.28A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.15l-.3-.18-2.9.76.78-2.83-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.25-.12-1.46-.72-1.69-.8s-.39-.12-.55.12-.63.8-.78.96-.29.19-.54.06a6.7 6.7 0 0 1-3.34-2.92c-.25-.43.25-.4.72-1.34a.45.45 0 0 0-.02-.43c-.06-.12-.55-1.33-.76-1.82s-.4-.41-.55-.42h-.47a.9.9 0 0 0-.65.3 2.74 2.74 0 0 0-.85 2.04 4.76 4.76 0 0 0 1 2.53 10.9 10.9 0 0 0 4.17 3.68c1.55.67 2.16.73 2.93.61a2.5 2.5 0 0 0 1.65-1.16 2 2 0 0 0 .14-1.16c-.06-.1-.22-.16-.47-.28z"/>',
    "mail": '<path d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm1 2.4V17h16V7.4l-8 5.3zM5.2 7 12 11.5 18.8 7z"/>',
    "in": '<path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.5h4V21H3zM9.5 9.5h3.8v1.6h.06a4.2 4.2 0 0 1 3.76-2.06C21.1 9.04 22 11.6 22 15v6h-4v-5.3c0-1.27-.02-2.9-1.77-2.9s-2.04 1.38-2.04 2.8V21h-4z"/>',
    "cal": '<path d="M7 2h2v2h6V2h2v2h3a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3zm12 8H5v9h14zM5 6v2h14V6zm2 6h4v4H7z"/>',
    "web": '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 6h-2.95a15.7 15.7 0 0 0-1.38-3.56A8.03 8.03 0 0 1 18.9 8zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82A13.6 13.6 0 0 1 12 4.04zM4.26 14a8.2 8.2 0 0 1 0-4h3.38a16.5 16.5 0 0 0 0 4zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.99 7.99 0 0 1 5.08 16zM8.03 8H5.08a7.99 7.99 0 0 1 4.33-3.56A15.7 15.7 0 0 0 8.03 8zM12 19.96A14 14 0 0 1 10.09 16h3.82A14 14 0 0 1 12 19.96zM14.34 14H9.66a14.7 14.7 0 0 1 0-4h4.68a14.7 14.7 0 0 1 0 4zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95a8.03 8.03 0 0 1-4.33 3.56zM16.36 14a16.5 16.5 0 0 0 0-4h3.38a8.2 8.2 0 0 1 0 4z"/>',
    "org": '<path d="M3 21V3h12v4h6v14zm2-2h2v-2H5zm0-4h2v-2H5zm0-4h2V9H5zm0-4h2V5H5zm4 12h2v-2H9zm0-4h2v-2H9zm0-4h2V9H9zm0-4h2V5H9zm4 12h6V9h-6v2h2v2h-2v2h2v2h-2z"/>',
    "save": '<path d="M12 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8zm0 10c4.4 0 8 1.8 8 4v3H4v-3c0-2.2 3.6-4 8-4zm7-10h2v2h2v2h-2v2h-2V7h-2V5h2z"/>',
}


def icon(name):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


def page(p, company, has_photo):
    e = lambda s: html.escape(s, quote=True)
    initials = "".join(w[0] for w in p["name"].split()[:2]).upper()
    first = p["name"].split()[0]
    wa_text = f"Hi {first}, I got your contact from your HBT digital card."
    links = []
    if p.get("phone"):
        links.append(("phone", "Call", p["phone_display"], f"tel:{p['phone']}"))
    if p.get("whatsapp"):
        links.append(("chat", "WhatsApp", "Send a message", f"https://wa.me/{p['whatsapp']}?text={quote(wa_text)}"))
    links.append(("mail", "Email", p["email"], f"mailto:{p['email']}?subject={quote('Hello from your HBT digital card')}"))
    if p.get("linkedin"):
        links.append(("in", "LinkedIn", "View profile", p["linkedin"]))
    if p.get("booking") and not p.get("cta"):     # the call-to-action box already has "Book a call"
        links.append(("cal", "Book a meeting", "Pick a time in my calendar", p["booking"]))
    for x in p.get("extra_links", []):
        links.append((x["icon"], x["label"], x["sub"], x["url"]))
    rows = "\n".join(
        f'''        <a class="row" href="{e(href)}"{' target="_blank" rel="noopener"' if href.startswith("http") else ''}>
          <span class="ic">{icon(ic)}</span><span class="tx"><b>{e(label)}</b><small>{e(sub)}</small></span><span class="go" aria-hidden="true">›</span>
        </a>''' for ic, label, sub, href in links)
    avatar = (f'<img class="avatar" src="photo.jpg" alt="Photo of {e(p["name"])}" width="120" height="120">'
              if has_photo else f'<div class="avatar initials" aria-hidden="true">{e(initials)}</div>')

    cta_html = ""
    if p.get("cta"):
        c = p["cta"]
        mail = f"mailto:{p['email']}?subject={quote(c['subject'])}&body={quote(c['body'])}"
        second = ""
        if p.get("booking"):
            second = f'<a class="cta-2" href="{e(p["booking"])}" target="_blank" rel="noopener">{icon("cal")}Book a call</a>'
        elif p.get("whatsapp"):
            second = f'<a class="cta-2" href="https://wa.me/{e(p["whatsapp"])}?text={quote(wa_text)}" target="_blank" rel="noopener">{icon("chat")}WhatsApp me</a>'
        cta_html = f'''
      <section class="cta" aria-label="{e(c['title'])}">
        <h2>{e(c['title'])}</h2>
        <p>{e(c['text'])}</p>
        <div class="cta-btns"><a class="cta-1" href="{e(mail)}">{icon("mail")}{e(c['button'])}</a>{second}</div>
      </section>'''

    hl_html = ""
    if p.get("highlights"):
        hl_html = '<ul class="hl">' + "".join(f"<li><b>{e(h[0])}</b><span>{e(h[1])}</span></li>" for h in p["highlights"]) + "</ul>"

    sv_html = ""
    if p.get("services"):
        items = "".join(f"<li><b>{e(s[0])}</b><span>{e(s[1])}</span></li>" for s in p["services"])
        note = f'<p class="sv-note">{e(p["services_note"])}</p>' if p.get("services_note") else ""
        sv_html = f'''
      <section class="sv">
        <h2>{e(p.get("services_title", "What we do"))}</h2>
        <ul>{items}</ul>
        {note}
      </section>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1e376d">
<title>{e(p['name'])} · {e(p['designation'])} · {e(company)}</title>
<meta name="description" content="{e(p['tagline'])}">
<meta property="og:title" content="{e(p['name'])} — {e(p['designation'])}, {e(company)}">
<meta property="og:description" content="{e(p['tagline'])}">
{'<meta property="og:image" content="photo.jpg">' if has_photo else ''}
<link rel="icon" href="../assets/hbt-logo.png">
<style>
  :root {{ --navy:#1e376d; --blue:#08498a; --yellow:#fcd005; --ink:#1b2333; --mute:#5d6678; --line:#e4e8f0; --bg:#eef1f6; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html {{ -webkit-text-size-adjust:100%; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--ink);
         min-height:100vh; display:flex; justify-content:center; align-items:flex-start; padding:20px 14px 36px; }}
  .card {{ width:100%; max-width:440px; background:#fff; border-radius:20px; overflow:hidden; box-shadow:0 10px 30px rgba(30,55,109,.12); }}
  .top {{ background:var(--navy); color:#fff; padding:22px 24px 70px; position:relative; }}
  .top::after {{ content:""; position:absolute; left:0; right:0; bottom:24px; height:8px; background:var(--yellow); }}
  .brand {{ display:flex; align-items:center; gap:12px; font-size:13px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; }}
  .brand img {{ width:44px; height:auto; background:#fff; border-radius:6px; padding:5px; }}
  .who {{ padding:0 24px; margin-top:-62px; position:relative; }}
  .avatar {{ width:120px; height:120px; border-radius:50%; border:5px solid #fff; object-fit:cover; display:block; background:#d8dee9;
            box-shadow:0 4px 14px rgba(30,55,109,.18); }}
  .initials {{ background:var(--blue); color:#fff; display:grid; place-items:center; font-size:38px; font-weight:700; }}
  h1 {{ font-size:clamp(24px,6vw,30px); margin-top:14px; color:var(--navy); line-height:1.15; }}
  .role {{ color:var(--blue); font-weight:600; margin-top:4px; font-size:16px; }}
  .tag {{ color:var(--mute); line-height:1.55; font-size:15px; margin-top:16px; padding-left:12px; border-left:3px solid var(--yellow); }}
  .hl {{ list-style:none; display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:18px; }}
  .hl li {{ background:#f4f6fb; border-radius:12px; padding:10px 8px; text-align:center; }}
  .hl b {{ display:block; color:var(--navy); font-size:18px; }}
  .hl span {{ display:block; color:var(--mute); font-size:11.5px; line-height:1.3; margin-top:2px; }}
  .scan {{ display:none; }}
  .actions {{ padding:22px 16px 20px; }}
  .cta {{ background:var(--navy); color:#fff; border-radius:16px; padding:20px 18px; margin-bottom:18px; position:relative; overflow:hidden; }}
  .cta::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:6px; background:var(--yellow); }}
  .cta h2 {{ font-size:19px; line-height:1.25; }}
  .cta p {{ color:#d5ddec; font-size:14px; line-height:1.5; margin-top:6px; }}
  .cta-btns {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }}
  .cta-btns a {{ flex:1 1 180px; display:flex; align-items:center; justify-content:center; gap:8px; padding:14px 16px; border-radius:12px;
                text-decoration:none; font-weight:700; font-size:15px; min-height:50px; }}
  .cta-btns svg {{ width:19px; height:19px; }}
  .cta-1 {{ background:var(--yellow); color:var(--navy); flex-grow:1.6 !important; white-space:nowrap; }}
  .cta-1 svg {{ fill:var(--navy); }}
  .cta-1:hover {{ background:#ffe04a; }}
  .cta-2 {{ background:transparent; color:#fff; border:1.5px solid rgba(255,255,255,.55); }}
  .cta-2 svg {{ fill:#fff; }}
  .cta-2:hover {{ background:rgba(255,255,255,.1); }}
  .links {{ display:grid; gap:10px; }}
  .row {{ display:flex; align-items:center; gap:14px; padding:12px 14px; min-height:64px; border:1px solid var(--line); border-radius:14px;
         text-decoration:none; color:inherit; transition:background .15s,border-color .15s,transform .15s; -webkit-tap-highlight-color:transparent; }}
  .row:hover {{ background:#f6f8fc; border-color:#c9d3e6; }}
  .row:active {{ transform:scale(.99); }}
  a:focus-visible {{ outline:3px solid var(--yellow); outline-offset:2px; }}
  .ic {{ width:42px; height:42px; flex:none; border-radius:11px; background:#e9eef7; display:grid; place-items:center; }}
  .ic svg {{ width:21px; height:21px; fill:var(--blue); }}
  .tx {{ display:flex; flex-direction:column; min-width:0; flex:1; }}
  .tx b {{ font-size:15px; }}
  .tx small {{ color:var(--mute); font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:1px; }}
  .go {{ color:#a3adc0; font-size:26px; line-height:1; }}
  .sv {{ margin-top:22px; }}
  .sv h2 {{ font-size:16px; color:var(--navy); margin-bottom:10px; }}
  .sv ul {{ list-style:none; display:grid; gap:8px; }}
  .sv li {{ border-left:3px solid var(--yellow); background:#f7f8fb; border-radius:0 10px 10px 0; padding:9px 12px; }}
  .sv li b {{ display:block; font-size:14px; }}
  .sv li span {{ display:block; color:var(--mute); font-size:12.5px; line-height:1.4; margin-top:1px; }}
  .sv-note {{ color:var(--mute); font-size:12.5px; line-height:1.5; margin-top:12px; }}
  .save {{ margin-top:16px; display:flex; justify-content:center; align-items:center; gap:10px; background:var(--blue); color:#fff;
          text-decoration:none; font-weight:600; font-size:16px; padding:16px; border-radius:14px; }}
  .save svg {{ width:20px; height:20px; fill:#fff; }}
  .save:hover {{ background:var(--navy); }}
  footer {{ text-align:center; color:var(--mute); font-size:12px; padding:0 0 18px; }}

  /* PC / tablet landscape: two columns */
  @media (min-width: 860px) {{
    body {{ align-items:center; padding:40px; }}
    .card {{ max-width:960px; display:grid; grid-template-columns:400px 1fr; grid-template-rows:auto 1fr auto; }}
    .top {{ grid-column:1 / -1; padding:24px 36px 76px; }}
    .who {{ padding:0 36px 32px; margin-top:-66px; }}
    .avatar {{ width:140px; height:140px; }}
    .actions {{ padding:30px 36px 32px; align-self:stretch; border-left:1px solid var(--line); }}
    .sv ul {{ grid-template-columns:1fr 1fr; }}
    .scan {{ display:flex; gap:16px; align-items:center; margin-top:28px; padding:14px; border:1px dashed #c9d3e6; border-radius:14px; }}
    .scan img {{ width:96px; height:96px; flex:none; }}
    .scan p {{ font-size:13px; color:var(--mute); line-height:1.45; }}
    .scan b {{ display:block; color:var(--ink); font-size:14px; margin-bottom:2px; }}
    footer {{ grid-column:1 / -1; padding-top:4px; }}
  }}
</style>
</head>
<body>
  <main class="card">
    <header class="top"><div class="brand"><img src="../assets/hbt-logo.png" alt="HBT logo"><span>{e(company)}</span></div></header>
    <section class="who">
      {avatar}
      <h1>{e(p['name'])}</h1>
      <div class="role">{e(p['designation'])}</div>
      <p class="tag">{e(p['tagline'])}</p>
      {hl_html}
    </section>
    <div class="actions">{cta_html}
      <nav class="links" aria-label="Contact options">
{rows}
      </nav>{sv_html}
      <a class="save" href="{e(p['slug'])}.vcf" download="{e(p['name'])}.vcf">{icon('save')}Save contact</a>
    </div>
    <footer>{e(company)}</footer>
  </main>
</body>
</html>
"""


def main():
    cfg = json.load(open(os.path.join(ROOT, "people.json"), encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    os.makedirs(os.path.join(ROOT, "qr"), exist_ok=True)
    for p in cfg["people"]:
        company = p.get("company", cfg["company"])
        url = f"{base}/{p['slug']}/"
        folder = os.path.join(ROOT, p["slug"])
        os.makedirs(folder, exist_ok=True)
        photo = os.path.join(ROOT, p["photo"]) if p.get("photo") else None
        if photo:
            img = Image.open(photo).convert("RGB")
            s = min(img.size)
            x0 = (img.width - s) // 2
            # portrait photos: keep the head in frame ("photo_top" = fraction of spare height above the crop)
            y0 = int((img.height - s) * p.get("photo_top", 0.5))
            img = img.crop((x0, y0, x0 + s, y0 + s))
            img.resize((400, 400), Image.LANCZOS).save(os.path.join(folder, "photo.jpg"), quality=88)
            small = os.path.join(folder, "_vcard.jpg")
            img.resize((240, 240), Image.LANCZOS).save(small, quality=82)
        qr_path = os.path.join(ROOT, "qr", f"{p['slug']}.png")
        n = make_qr(url, qr_path)
        old = os.path.join(folder, "qr.png")
        if os.path.exists(old):
            os.remove(old)
        open(os.path.join(folder, "index.html"), "w", encoding="utf-8").write(page(p, company, bool(photo)))
        open(os.path.join(folder, f"{p['slug']}.vcf"), "w", encoding="utf-8", newline="").write(
            vcard(p, company, url, small if photo else None))
        if photo:
            os.remove(small)
        print(f"{p['name']:<24} {url}  (QR {n}x{n}, scan check OK)")


if __name__ == "__main__":
    main()
