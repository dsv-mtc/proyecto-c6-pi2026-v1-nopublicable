from __future__ import annotations

from pathlib import Path
import html
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
OUT_HTML = ROOT / "index.html"


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def parse_title() -> tuple[str, str, str]:
    path = CONTENT_DIR / "Titulo.txt"
    if not path.exists():
        return "", "", ""
    lines = [line.strip() for line in read_text(path).splitlines() if line.strip()]
    header = lines[0] if len(lines) > 0 else ""
    title = lines[1] if len(lines) > 1 else ""
    subtitle = lines[2] if len(lines) > 2 else ""
    return header, title, subtitle


def parse_body() -> list[str]:
    path = CONTENT_DIR / "Cuerpo.txt"
    if not path.exists():
        return []
    return [line.strip() for line in read_text(path).splitlines() if line.strip()]


def parse_sections() -> list[dict]:
    sections = []
    base_dir = CONTENT_DIR / "Despegables"
    if not base_dir.exists():
        return sections
    for path in base_dir.glob("Des*.txt"):
        match = re.match(r"^Des(\d+)-(.+)\.txt$", path.name)
        if not match:
            continue
        order = int(match.group(1))
        raw_title = match.group(2).strip()
        items = []
        for line in read_text(path).splitlines():
            line = line.strip()
            if not line:
                continue
            link_match = re.match(r"^(.*?)\s*<([^>]+)>\s*$", line)
            if link_match:
                text = link_match.group(1).strip()
                url = link_match.group(2).strip()
                items.append({"text": text, "url": url})
            else:
                items.append({"text": line, "url": ""})
        sections.append({"order": order, "title": raw_title, "items": items})
    return sorted(sections, key=lambda s: s["order"])


def parse_buttons() -> list[dict]:
    groups = []
    base_dir = CONTENT_DIR / "Botones"
    if not base_dir.exists():
        return groups
    for group_dir in base_dir.iterdir():
        if not group_dir.is_dir():
            continue
        group_title = group_dir.name
        footer_text = ""
        footer_path = group_dir / "Pie.txt"
        if footer_path.exists():
            footer_lines = [
                line.strip() for line in read_text(footer_path).splitlines() if line.strip()
            ]
            footer_text = " ".join(footer_lines)
        buttons = []
        for path in group_dir.glob("*.txt"):
            if path.name.lower() == "pie.txt":
                continue
            match = re.match(r"^(\d+)\.(.+)\.txt$", path.name)
            if not match:
                continue
            order = int(match.group(1))
            title = match.group(2).strip()
            lines = [line.strip() for line in read_text(path).splitlines() if line.strip()]
            buttons.append(
                {
                    "order": order,
                    "title": title,
                    "text": " ".join(lines),
                }
            )
        if buttons:
            groups.append(
                {
                    "title": group_title,
                    "buttons": sorted(buttons, key=lambda b: b["order"]),
                    "footer": footer_text,
                }
            )
    return groups


def parse_beneficiarios() -> dict | None:
    path = CONTENT_DIR / "BENEFICIARIOS.txt"
    if not path.exists():
        return None
    lines = [line.strip() for line in read_text(path).splitlines() if line.strip()]
    if not lines:
        return None
    button_line = ""
    if len(lines) > 2:
        button_line = lines[-1]
        lines = lines[:-1]
    return {
        "title": "BENEFICIARIOS",
        "lead": lines[0],
        "lines": lines[1:],
        "button": button_line,
    }


def parse_registro() -> dict | None:
    matches = sorted(CONTENT_DIR.glob("REGISTRO*.txt"))
    if not matches:
        return None
    path = matches[0]
    lines = [line.strip() for line in read_text(path).splitlines() if line.strip()]
    if not lines:
        return None
    return {
        "title": path.stem,
        "lines": lines[:1],
        "buttons": lines[1:],
    }


def parse_contacto() -> list[str]:
    path = CONTENT_DIR / "Contacto.txt"
    if not path.exists():
        return []
    return [line.strip() for line in read_text(path).splitlines() if line.strip()]


def parse_redes() -> list[dict]:
    path = CONTENT_DIR / "Redes.txt"
    if not path.exists():
        return []
    entries = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        name, url = split_full_link(line)
        if url and name:
            entries.append({"name": name, "url": url})
    return entries


def render_inline(text: str, allow_links: bool = True) -> str:
    out = []
    i = 0
    while i < len(text):
        if allow_links and text.startswith("<link:", i):
            match = re.match(r'<link:"([^"]+)"=([^>]+)>', text[i:])
            if match:
                link_text = render_inline(match.group(1), allow_links=False)
                url = esc(match.group(2).strip())
                out.append(
                    f"<a href=\"{url}\" target=\"_blank\" rel=\"noopener\">{link_text}</a>"
                )
                i += len(match.group(0))
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end != -1:
                inner = render_inline(text[i + 2 : end], allow_links=allow_links)
                out.append(f"<strong>{inner}</strong>")
                i = end + 2
                continue
        if text[i] == "*":
            end = text.find("*", i + 1)
            if end != -1:
                inner = render_inline(text[i + 1 : end], allow_links=allow_links)
                out.append(f"<strong>{inner}</strong>")
                i = end + 1
                continue
        out.append(esc(text[i]))
        i += 1
    return "".join(out)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", stripped.lower())


def render_footer_with_section_links(text: str, sections: list[dict]) -> str:
    if not text:
        return ""
    parts = re.split(r"(<[^>]+>)", text)
    rendered = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            label = part[1:-1].strip()
            target_id = ""
            needle = normalize_text(label)
            for sec in sections:
                if needle and needle in normalize_text(sec["title"]):
                    target_id = f"sec-{sec['order']:02d}"
                    break
            if target_id:
                rendered.append(
                    f"<a class=\"indicator-link\" href=\"#\" data-open=\"{target_id}\">"
                    f"{render_inline(label)}</a>"
                )
            else:
                rendered.append(render_inline(label))
        else:
            rendered.append(render_inline(part))
    return "".join(rendered)


def split_full_link(text: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)\s*<([^>]+)>\s*$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, None


def choose_main_image() -> str:
    png_path = ROOT / "assets" / "img" / "im_principal.png"
    jpg_path = ROOT / "assets" / "img" / "im_principal.jpg"
    if png_path.exists():
        return "assets/img/im_principal.png"
    if jpg_path.exists():
        return "assets/img/im_principal.jpg"
    return "assets/img/im_principal.png"


def build_html() -> str:
    header, title, subtitle = parse_title()
    body_lines = parse_body()
    sections = parse_sections()
    buttons = parse_buttons()
    beneficiarios = parse_beneficiarios()
    registro = parse_registro()
    contacto_lines = parse_contacto()
    redes = parse_redes()
    hero_src = choose_main_image()

    body_html = "\n".join(f"<p>{esc(line)}</p>" for line in body_lines) or "<p></p>"

    beneficiarios_html = ""
    if beneficiarios:
        lead_html = render_inline(beneficiarios["lead"])
        extra_lines = "\n".join(
            f"<p>{render_inline(line)}</p>" for line in beneficiarios["lines"]
        )
        button_html = ""
        if beneficiarios.get("button"):
            button_text, button_url = split_full_link(beneficiarios["button"])
            button_label = render_inline(button_text)
            if button_url:
                button_html = (
                    f"<a class=\"beneficiarios-button\" href=\"{esc(button_url)}\" "
                    "target=\"_blank\" rel=\"noopener\">"
                    f"{button_label}</a>"
                )
        beneficiarios_html = (
            "<section class=\"beneficiarios\" data-animate=\"3\">"
            "<div class=\"beneficiarios-text\">"
            f"<p class=\"beneficiarios-title\">{esc(beneficiarios['title'])}</p>"
            f"<p class=\"beneficiarios-lead\">{lead_html}</p>"
            f"{extra_lines}"
            f"{button_html}"
            "</div>"
            "<div class=\"beneficiarios-map\">"
            "<img src=\"assets/img/mapa.png\" alt=\"Mapa\">"
            "</div>"
            "</section>"
        )

    registro_html = ""
    if registro:
        line_html = "\n".join(f"<p>{render_inline(line)}</p>" for line in registro["lines"])
        button_html = ""
        if registro.get("buttons"):
            registro_buttons = []
            for line in registro["buttons"]:
                button_text, button_url = split_full_link(line)
                button_label = render_inline(button_text)
                if button_url:
                    registro_buttons.append(
                        f"<a class=\"registro-button\" href=\"{esc(button_url)}\" "
                        "target=\"_blank\" rel=\"noopener\">"
                        f"{button_label}</a>"
                    )
            if registro_buttons:
                button_html = (
                    f"<div class=\"registro-buttons\">{''.join(registro_buttons)}</div>"
                )
        registro_html = (
            "<section class=\"registro-band\" data-animate=\"3\">"
            "<div class=\"registro\">"
            "<div class=\"registro-media\">"
            "<img src=\"assets/img/plataforma.png\" alt=\"Plataforma\">"
            "</div>"
            "<div class=\"registro-text\">"
            f"<p class=\"registro-title\">{esc(registro['title'])}</p>"
            f"{line_html}"
            f"{button_html}"
            "</div>"
            "</div>"
            "</section>"
        )

    contacto_html = ""
    if contacto_lines or redes:
        contacto_text = "\n".join(f"<p>{render_inline(line)}</p>" for line in contacto_lines)
        icons_html = ""
        if redes:
            icons = []
            for item in redes:
                icon_src = f"assets/img/iconos/{item['name']}"
                icons.append(
                    f"<a href=\"{esc(item['url'])}\" target=\"_blank\" rel=\"noopener\">"
                    f"<img src=\"{esc(icon_src)}\" alt=\"{esc(item['name'])}\">"
                    "</a>"
                )
            icons_html = f"<div class=\"redes-icons\">{''.join(icons)}</div>"
        contacto_html = (
            "<section class=\"contacto\" data-animate=\"3\">"
            f"{contacto_text}"
            f"{icons_html}"
            "</section>"
        )

    buttons_html = ""
    if buttons:
        groups_html = []
        for group in buttons:
            cards = []
            for button in group["buttons"]:
                icon_src = f"assets/img/iconos/indicador{button['order']}.png"
                title_html = render_inline(button["title"])
                text_html = render_inline(button["text"])
                cards.append(
                    "<div class=\"indicator-card\">"
                    f"<img class=\"indicator-icon\" src=\"{icon_src}\" alt=\"Icono\">"
                    f"<p class=\"indicator-title\">{title_html}</p>"
                    f"<p class=\"indicator-text\">{text_html}</p>"
                    "</div>"
                )
            cards_html = "\n".join(cards)
            group_title = esc(group["title"])
            footer_html = ""
            if group.get("footer"):
                footer_html = (
                    f"<p class=\"indicator-footer\">"
                    f"{render_footer_with_section_links(group['footer'], sections)}"
                    "</p>"
                )
            groups_html.append(
                "<div class=\"indicator-group\">"
                f"<h2 class=\"indicator-heading\">{group_title}</h2>"
                "<div class=\"indicator-row\">"
                f"{cards_html}"
                "</div>"
                f"{footer_html}"
                "</div>"
            )
        groups_block = "\n".join(groups_html)
        buttons_html = (
            "<section class=\"indicator-section\" data-animate=\"3\">"
            f"{groups_block}"
            "</section>"
        )

    accordion_items = []
    for idx, sec in enumerate(sections):
        sec_id = f"sec-{sec['order']:02d}"
        active_class = " is-active" if idx == 0 else ""
        aria_expanded = "true" if idx == 0 else "false"
        button_id = f"{sec_id}-btn"

        items = []
        for item in sec["items"]:
            text = esc(item["text"])
            url = item["url"].strip()
            if url:
                items.append(
                    f"<li><a href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">"
                    f"{text}</a></li>"
                )
            else:
                items.append(f"<li><span>{text}</span></li>")

        items_html = "\n".join(items) or "<li><span></span></li>"
        accordion_items.append(
            f"<div class=\"sec-item\">"
            f"<button id=\"{button_id}\" class=\"sec-btn{active_class}\" "
            f"aria-expanded=\"{aria_expanded}\" aria-controls=\"{sec_id}\" "
            f"data-target=\"{sec_id}\">"
            f"<span class=\"sec-title\">{esc(sec['title'])}</span>"
            f"<span class=\"sec-arrow\" aria-hidden=\"true\">></span>"
            f"</button>"
            f"<div id=\"{sec_id}\" class=\"sec-panel{active_class}\" "
            f"role=\"region\" aria-labelledby=\"{button_id}\" "
            f"aria-hidden=\"{str(idx != 0).lower()}\">"
            f"<ul>\n{items_html}\n</ul></div>"
            f"</div>"
        )

    accordion_block = "\n".join(accordion_items)

    return f"""<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">
  <meta http-equiv=\"Pragma\" content=\"no-cache\">
  <meta http-equiv=\"Expires\" content=\"0\">
  <title>{esc(title or header or 'Pagina')}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Marcellus&family=Work+Sans:wght@300;500;700&display=swap');

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: "Work Sans", "Segoe UI", sans-serif;
      min-height: 100vh;
    }}

    .page {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 48px 24px 0;
    }}

    .page-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
    }}

    .logo {{
      width: 120px;
      height: auto;
      object-fit: contain;
    }}

    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.32em;
      font-size: 12px;
      margin: 0 0 12px;
    }}

    h1 {{
      font-family: "Marcellus", "Georgia", serif;
      font-weight: 400;
      font-size: clamp(32px, 4vw, 52px);
      margin: 0 0 12px;
    }}

    .subtitle {{
      margin: 0;
      font-size: clamp(16px, 2.3vw, 22px);
      max-width: 560px;
      line-height: 1.5;
    }}

    .hero-band {{
      width: 100vw;
      margin-left: calc(50% - 50vw);
      margin-right: calc(50% - 50vw);
      margin-top: 36px;
      margin-bottom: 28px;
      background: url("assets/img/Fondos/principal.png") center/cover no-repeat;
      padding: 24px 0;
    }}

    .hero {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 24px;
      overflow: hidden;
      position: relative;
    }}

    .hero img {{
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
    }}

    .body-text {{
      padding: 24px 28px;
      line-height: 1.6;
      text-align: justify;
    }}

    .body-text p {{
      margin: 0 0 22px;
      font-size: 18px;
      line-height: 1.7;
    }}

    .section-divider {{
      height: 10px;
      background: #777777;
      width: 100%;
      margin: 16px 0 24px;
    }}

    .beneficiarios {{
      display: flex;
      gap: 28px;
      align-items: flex-start;
      margin-top: 32px;
    }}

    .beneficiarios-text {{
      flex: 1;
      min-width: 0;
    }}

    .beneficiarios-title {{
      margin: 0 0 10px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 22px;
      font-weight: 600;
    }}

    .beneficiarios-lead {{
      margin: 0 0 12px;
      font-size: 32px;
      font-weight: 700;
    }}

    .beneficiarios-text p {{
      margin: 0 0 16px;
      font-size: 18px;
      line-height: 1.7;
    }}

    .beneficiarios-text .beneficiarios-lead {{
      font-size: 40px;
    }}

    .beneficiarios-map {{
      flex: 1;
      min-width: 220px;
      max-width: 360px;
    }}

    .beneficiarios-map img {{
      width: 75%;
      height: auto;
      display: block;
      margin-right: auto;
    }}

    .beneficiarios-button {{
      display: inline-block;
      margin-top: 10px;
      padding: 10px 16px;
      border: 1px solid #b8c1cc;
      border-radius: 6px;
      font-size: 18px;
      font-weight: 600;
      background: #777777;
      color: #ffffff;
    }}

    .registro-band {{
      width: 100vw;
      margin-left: calc(50% - 50vw);
      margin-right: calc(50% - 50vw);
      margin-top: 32px;
      background: url("assets/img/Fondos/plataforma.png") center/cover no-repeat;
      padding: 24px 0;
    }}

    .registro {{
      display: flex;
      gap: 28px;
      align-items: stretch;
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 24px;
    }}

    .registro-media {{
      flex: 1;
      min-width: 330px;
      max-width: 540px;
      display: flex;
      justify-content: center;
      align-items: stretch;
    }}

    .registro-media img {{
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
      margin: auto;
    }}

    .registro-text {{
      flex: 1.2;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}

    .registro-title {{
      margin: 0 0 10px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 22px;
      font-weight: 600;
      color: #ffffff;
    }}

    .registro-text p {{
      margin: 0 0 16px;
      font-size: 18px;
      line-height: 1.7;
      color: #ffffff;
    }}

    .registro-button {{
      display: inline-block;
      margin-top: 10px;
      padding: 10px 16px;
      border: 1px solid #b8c1cc;
      border-radius: 6px;
      font-size: 18px;
      font-weight: 600;
      text-align: center;
      background: #ffffff;
      color: #ba3034;
    }}

    .registro-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }}

    .contacto {{
      margin-top: 54px;
      text-align: center;
      background: #575556;
      color: #ffffff;
      padding: 24px 16px;
      width: 100vw;
      margin-left: calc(50% - 50vw);
      margin-right: calc(50% - 50vw);
    }}

    .contacto p {{
      margin: 0 0 10px;
      font-size: 18px;
      line-height: 1.6;
      color: #ffffff;
    }}

    .redes-icons {{
      display: flex;
      justify-content: center;
      gap: 14px;
      margin-top: 12px;
      flex-wrap: wrap;
    }}

    .redes-icons img {{
      width: 36px;
      height: 36px;
      display: block;
      object-fit: contain;
    }}

    .indicator-section {{
      margin-top: 32px;
    }}

    .indicator-group {{
      margin-bottom: 24px;
    }}

    .indicator-heading {{
      margin: 0 0 14px;
      font-size: 22px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}

    .indicator-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 18px;
    }}

    .indicator-card {{
      aspect-ratio: 1 / 1;
      border: 1px solid #d7dbe2;
      border-radius: 16px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: 10px;
    }}

    .indicator-icon {{
      width: 64px;
      height: 64px;
      object-fit: contain;
    }}

    .indicator-title {{
      margin: 0;
      font-size: 20px;
      font-weight: 700;
    }}

    .indicator-text {{
      margin: 0;
      font-size: 16px;
      line-height: 1.5;
    }}

    .indicator-footer {{
      margin: 12px 0 0;
      font-size: 16px;
      line-height: 1.6;
    }}

    .indicator-link {{
      font-weight: 600;
    }}

    .sections {{
      margin-top: 36px;
    }}

    .accordion {{
      display: flex;
      flex-direction: column;
      gap: 14px;
      width: min(100%, 920px);
      margin: 0 auto;
    }}

    .sec-btn {{
      border: none;
      padding: 14px 22px;
      border-radius: 16px;
      font-size: 20px;
      font-weight: 600;
      cursor: pointer;
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      text-align: left;
      transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    }}

    .sec-btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 10px 24px rgba(15, 58, 74, 0.15);
    }}

    .sec-arrow {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      font-size: 18px;
      transition: transform 0.2s ease;
    }}

    .sec-btn.is-active .sec-arrow {{
      transform: rotate(90deg);
    }}

    .sec-panel {{
      display: none;
      padding: 24px;
      animation: fadeUp 0.4s ease;
    }}

    .sec-panel.is-active {{
      display: block;
    }}

    .sec-panel ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}

    .sec-panel li {{
      padding: 3px 8px;
      font-size: 18px;
      line-height: 1.7;
    }}

    .sec-panel a {{
      color: #1a5fb4;
      text-decoration: none;
      font-weight: 600;
    }}

    a {{
      text-decoration: none;
    }}


    [data-animate] {{
      opacity: 0;
      transform: translateY(14px);
      transition: opacity 0.6s ease, transform 0.6s ease;
    }}

    body.is-ready [data-animate] {{
      opacity: 1;
      transform: translateY(0);
    }}

    body.is-ready [data-animate="2"] {{
      transition-delay: 0.08s;
    }}

    body.is-ready [data-animate="3"] {{
      transition-delay: 0.16s;
    }}

    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (max-width: 800px) {{
      .page-header {{
        flex-direction: column;
        align-items: flex-start;
      }}

      .logo {{
        align-self: flex-end;
      }}

      .beneficiarios {{
        flex-direction: column;
      }}

      .registro {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <div class=\"page\">
    <header class=\"page-header\" data-animate=\"1\">
      <div>
        <p class=\"eyebrow\">{esc(header)}</p>
        <h1>{esc(title)}</h1>
        <p class=\"subtitle\">{esc(subtitle)}</p>
      </div>
      <a class=\"logo-link\" href=\"https://www.onsv.gob.pe/\" target=\"_blank\" rel=\"noopener\">
        <img class=\"logo\" src=\"assets/img/logos/logo-onsv.png\" alt=\"Logo ONSV\">
      </a>
    </header>

    <section class=\"hero-band\" data-animate=\"2\">
      <div class=\"hero\">
        <img src=\"{hero_src}\" alt=\"Imagen principal\">
      </div>
    </section>

    <section class=\"body-text\" data-animate=\"3\">
      {body_html}
    </section>

    <div class=\"section-divider\" aria-hidden=\"true\"></div>

    {beneficiarios_html}

    {buttons_html}

    {registro_html}

    <section class=\"sections\" data-animate=\"3\">
      <div class=\"accordion\">
        {accordion_block}
      </div>
    </section>

    {contacto_html}
  </div>

  <script>
    const buttons = Array.from(document.querySelectorAll('.sec-btn'));
    const panels = Array.from(document.querySelectorAll('.sec-panel'));

    function closeAll() {{
      panels.forEach(panel => {{
        panel.classList.remove('is-active');
        panel.setAttribute('aria-hidden', 'true');
      }});
      buttons.forEach(button => {{
        button.classList.remove('is-active');
        button.setAttribute('aria-expanded', 'false');
      }});
    }}

    function openById(targetId) {{
      const panel = document.getElementById(targetId);
      if (!panel) return;
      closeAll();
      panel.classList.add('is-active');
      panel.setAttribute('aria-hidden', 'false');
      const button = buttons.find(btn => btn.dataset.target === targetId);
      if (button) {{
        button.classList.add('is-active');
        button.setAttribute('aria-expanded', 'true');
      }}
      panel.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    buttons.forEach(button => {{
      button.addEventListener('click', () => {{
        const targetId = button.dataset.target;
        const panel = document.getElementById(targetId);
        const willOpen = !panel.classList.contains('is-active');
        closeAll();
        if (willOpen) {{
          panel.classList.add('is-active');
          panel.setAttribute('aria-hidden', 'false');
          button.classList.add('is-active');
          button.setAttribute('aria-expanded', 'true');
        }}
      }});
    }});

    document.querySelectorAll('[data-open]').forEach(link => {{
      link.addEventListener('click', event => {{
        const targetId = link.getAttribute('data-open');
        if (targetId) {{
          event.preventDefault();
          openById(targetId);
        }}
      }});
    }});

    window.addEventListener('load', () => {{
      document.body.classList.add('is-ready');
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    html_text = build_html()
    OUT_HTML.write_text(html_text, encoding="utf-8")
    print(f"Wrote {OUT_HTML}")


if __name__ == "__main__":
    main()
