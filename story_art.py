from __future__ import annotations

import hashlib
import io
import json
import re
import textwrap
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
ART_DIR = ROOT / "assets" / "story-art"
SOURCE_DIR = ROOT / "assets" / "source-media"
CDN_BASE = "https://cdn.jsdelivr.net/gh/BoomForge/EdgeAI@main/assets/story-art"
SOURCE_CDN_BASE = "https://cdn.jsdelivr.net/gh/BoomForge/EdgeAI@main/assets/source-media"
USER_AGENT = "EdgeAI/1.0 (+https://edgeainews.blogspot.com/)"
TIMEOUT = 20

PALETTES = {
    "Models": ("#7e93ff", "#9a7cff"),
    "Tools": ("#5ec5b1", "#6f9cff"),
    "Agents": ("#58c8a5", "#b0d36f"),
    "Research": ("#d0a65d", "#8d79c9"),
    "Open Source": ("#67c08d", "#6b8ee8"),
    "Creative AI": ("#cc78a8", "#8176e7"),
    "Infrastructure": ("#72a2bd", "#7687a4"),
    "Breaking": ("#df826f", "#d8ae61"),
}


def _safe_key(value: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return value[:100] or "story"


def _category(labels: list[str] | None) -> str:
    labels = labels or []
    for name in PALETTES:
        if name in labels:
            return name
    return "Models"


def _lines(title: str) -> list[str]:
    title = re.sub(r"\s+", " ", title).strip()
    lines = textwrap.wrap(title, width=31, break_long_words=False, break_on_hyphens=False)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:27].rstrip() + "…"
    return lines or ["EdgeAI Report"]


def _font(size: int, bold: bool = False):
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _tokens(value: str) -> set[str]:
    stop = {"the", "a", "an", "and", "or", "for", "to", "of", "with", "in", "on", "ai", "model", "models", "announces", "releases", "launches"}
    return {t for t in re.findall(r"[a-z0-9]+", value.lower()) if len(t) > 2 and t not in stop}


def _clean_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _image_url_ok(url: str) -> bool:
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    lower = url.lower()
    bad = (
        "favicon", "avatar", "sprite", "emoji", "badge", "placeholder", "your-image",
        "example.com/image", "opengraph,%20twitter-cards", "opengraph%2c%20twitter-cards",
        "%3clink", "%3cimage", "<link", "<image", "logo-small", "icon-",
    )
    return not any(token in lower for token in bad)


def _queue_match(title: str, source: str) -> dict | None:
    title_tokens = _tokens(title)
    source_l = source.lower().strip()
    best = None
    best_score = 0.0
    for filename in ("queue_fast.json", "queue_deep.json"):
        data = _load_json(ROOT / filename, {"candidates": []})
        for item in data.get("candidates", []):
            item_source = str(item.get("source_name", "")).lower().strip()
            if source_l and item_source and source_l not in item_source and item_source not in source_l:
                continue
            item_tokens = _tokens(str(item.get("title", "")))
            if not item_tokens:
                continue
            overlap = len(title_tokens & item_tokens)
            score = overlap / max(1, len(title_tokens | item_tokens))
            if overlap >= 2 and score > best_score:
                best = item
                best_score = score
    return best


def _discover_image_urls(page_url: str, preferred: str = "") -> list[str]:
    out: list[str] = []
    if _image_url_ok(preferred):
        out.append(_clean_url(preferred))
    if not page_url:
        return out
    try:
        r = requests.get(
            page_url,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
        )
        r.raise_for_status()
        if "html" not in r.headers.get("content-type", "").lower():
            return out
        soup = BeautifulSoup(r.text, "html.parser")
        selectors = (
            ("meta", {"property": "og:image"}),
            ("meta", {"property": "og:image:secure_url"}),
            ("meta", {"name": "twitter:image"}),
            ("meta", {"property": "twitter:image"}),
            ("link", {"rel": "image_src"}),
        )
        for tag, attrs in selectors:
            node = soup.find(tag, attrs=attrs)
            if node:
                value = node.get("content") or node.get("href")
                if value:
                    out.append(urljoin(page_url, str(value)))
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw or '"image"' not in raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            stack = data if isinstance(data, list) else [data]
            for obj in stack:
                if not isinstance(obj, dict):
                    continue
                image = obj.get("image")
                values = []
                if isinstance(image, str):
                    values = [image]
                elif isinstance(image, list):
                    values = [x for x in image if isinstance(x, str)]
                elif isinstance(image, dict):
                    v = image.get("url") or image.get("contentUrl")
                    values = [v] if v else []
                out.extend(urljoin(page_url, str(v)) for v in values)
        for selector in ("article img", "main img", ".post img", ".article img"):
            for node in soup.select(selector)[:12]:
                value = node.get("src") or node.get("data-src") or node.get("data-lazy-src")
                if value:
                    out.append(urljoin(page_url, str(value)))
    except Exception as exc:
        print(f"SOURCE IMAGE PAGE WARNING: {page_url}: {exc}")

    clean: list[str] = []
    seen = set()
    for value in out:
        value = _clean_url(value)
        if value not in seen and _image_url_ok(value):
            seen.add(value)
            clean.append(value)
    return clean


def _source_context(story_key: str, title: str, source: str) -> tuple[str, str]:
    state = _load_json(ROOT / "editor_state.json", {"stories": {}})
    story = state.get("stories", {}).get(story_key, {})
    preferred = str(story.get("source_image_url", ""))
    source_urls = story.get("source_urls") or []
    page_url = str(source_urls[-1]) if source_urls else ""
    if page_url or _image_url_ok(preferred):
        return page_url, preferred

    item = _queue_match(title, source)
    if not item:
        return "", ""
    return str(item.get("url", "")), str(item.get("image_url", ""))


def _mirror_source_image(story_key: str, title: str, source: str) -> str | None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    key = _safe_key(story_key)
    path = SOURCE_DIR / f"{key}.jpg"
    if path.exists() and path.stat().st_size > 5000:
        return f"{SOURCE_CDN_BASE}/{path.name}"

    page_url, preferred = _source_context(story_key, title, source)
    for image_url in _discover_image_urls(page_url, preferred):
        try:
            headers = {"User-Agent": USER_AGENT, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}
            if page_url:
                headers["Referer"] = page_url
            r = requests.get(image_url, timeout=TIMEOUT, headers=headers)
            r.raise_for_status()
            if len(r.content) < 5000:
                continue
            img = Image.open(io.BytesIO(r.content))
            img = ImageOps.exif_transpose(img)
            width, height = img.size
            if width < 500 or height < 250 or width * height < 180000:
                continue
            if max(width, height) > 1800:
                img.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
            if img.mode != "RGB":
                if "A" in img.getbands():
                    bg = Image.new("RGB", img.size, (12, 16, 22))
                    alpha = img.getchannel("A")
                    bg.paste(img.convert("RGB"), mask=alpha)
                    img = bg
                else:
                    img = img.convert("RGB")
            img.save(path, format="JPEG", quality=90, optimize=True, progressive=True)
            print(f"SOURCE IMAGE MIRRORED: {title} <- {image_url} ({width}x{height})")
            return f"{SOURCE_CDN_BASE}/{path.name}"
        except Exception as exc:
            print(f"SOURCE IMAGE CANDIDATE REJECTED: {image_url}: {exc}")
    return None


def _generate_editorial_fallback(story_key: str, title: str, source: str, labels: list[str] | None = None) -> str:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    key = _safe_key(story_key)
    path = ART_DIR / f"{key}.png"

    width, height = 1200, 675
    category = _category(labels)
    c1, c2 = PALETTES[category]
    c1_rgb, c2_rgb = _rgb(c1), _rgb(c2)

    img = Image.new("RGB", (width, height), (10, 14, 20))
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(height):
        p = y / max(1, height - 1)
        base = (int(11 + 10 * p), int(15 + 10 * p), int(22 + 12 * p))
        draw.line((0, y, width, y), fill=(*base, 255))
    for x in range(0, width, 44):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 8), width=1)
    for y in range(0, height, 44):
        draw.line((0, y, width, y), fill=(255, 255, 255, 8), width=1)

    digest = hashlib.sha256((story_key + title).encode("utf-8")).hexdigest()
    nums = [int(digest[i:i+8], 16) for i in (0, 8, 16)]
    for i, n in enumerate(nums):
        cx = 760 + (n % 330)
        cy = 100 + ((n // 13) % 470)
        r = 90 + ((n // 101) % 150)
        col = c1_rgb if i % 2 == 0 else c2_rgb
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(*col, 70 + i * 18), width=2)

    draw.line([(690, 555), (805, 455), (918, 488), (1132, 344)], fill=(*c1_rgb, 150), width=3, joint="curve")
    draw.line([(715, 590), (845, 495), (958, 522), (1168, 406)], fill=(223, 231, 242, 45), width=2, joint="curve")
    draw.rounded_rectangle((72, 64, 198, 100), radius=7, fill=(*c1_rgb, 255))
    draw.text((87, 72), "EDGEAI", font=_font(17, True), fill=(12, 17, 24, 255))
    draw.text((72, 132), category.upper(), font=_font(16, True), fill=(*c1_rgb, 255))

    title_font = _font(48, True)
    lines = _lines(title)
    y = 255 - (len(lines) - 1) * 35
    for line in lines:
        draw.text((72, y), line, font=title_font, fill=(244, 247, 251, 255))
        y += 62

    draw.line((72, 540, 558, 540), fill=(255, 255, 255, 38), width=1)
    source_text = re.sub(r"\s+", " ", source or "EdgeAI").strip()[:60].upper()
    draw.text((72, 566), f"SOURCE / {source_text}", font=_font(17), fill=(170, 181, 195, 255))
    draw.text((72, 608), "BLEEDING-EDGE AI WITHOUT THE NOISE", font=_font(14), fill=(125, 137, 152, 255))
    draw.text((930, 608), "SIGNAL / VERIFY / REPORT", font=_font(14), fill=(116, 128, 145, 255))
    img.save(path, format="PNG", optimize=True)
    return f"{CDN_BASE}/{path.name}"


def ensure_story_art(story_key: str, title: str, source: str, labels: list[str] | None = None) -> str:
    """Return a mirrored real source image when available; generate EdgeAI art only as a last resort."""
    mirrored = _mirror_source_image(story_key, title, source)
    if mirrored:
        return mirrored
    print(f"SOURCE IMAGE FALLBACK: {title} -> EdgeAI editorial artwork")
    return _generate_editorial_fallback(story_key, title, source, labels)
