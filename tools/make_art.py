#!/usr/bin/env python3
"""Gera as ilustrações vetoriais originais usadas pelo site.

IMPORTANTE (ver docs/MASCOTE_NOTAS.md):
- Os pacotes de referência NÃO incluem arquivo original do mascote; ele aparece apenas dentro
  de capturas de tela. Por isso as poses abaixo são ilustrações vetoriais NOVAS, desenhadas a
  partir das características observadas (boné laranja com topo branco, cabelo cacheado
  castanho, sorriso largo, camiseta preta com emblema "K"). Não são cópias nem recortes.
- As ilustrações de produtos são DEMONSTRATIVAS (não são fotografias aprovadas da KNAZH).

Uso: python tools/make_art.py   (gera em knazh/static/img/{mascote,produtos,ui})
Só é necessário para regenerar as artes; o site NÃO depende deste script em execução.
"""
from __future__ import annotations

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "knazh" / "static" / "img"

ORANGE = "#FF6B1A"
ORANGE_DARK = "#D9500B"
YELLOW = "#FFB323"
CHARCOAL = "#171717"
CREAM = "#FFF5E8"
SKIN = "#F8B98B"
SKIN_SHADE = "#E99B6A"
HAIR = "#6B2A12"
OUT = "#1B1B1B"


def svg(w: int, h: int, body: str, title: str, defs: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{title}"><title>{title}</title><defs>{defs}</defs>{body}</svg>\n'
    )


# --------------------------------------------------------------------------- mascote
def _brownie_prop(x: int, y: int, scale: float = 1.0) -> str:
    return (
        f'<g transform="translate({x} {y}) scale({scale})">'
        f'<path d="M0 30 L26 6 L130 6 L106 30 Z" fill="#5A2A14" stroke="{OUT}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M0 30 L106 30 L106 86 L0 86 Z" fill="#3A1A0C" stroke="{OUT}" stroke-width="5" stroke-linejoin="round"/>'
        f'<path d="M106 30 L130 6 L130 62 L106 86 Z" fill="#2C1409" stroke="{OUT}" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M14 24 Q40 12 62 22 T104 14" fill="none" stroke="#B0602A" stroke-width="7" stroke-linecap="round"/>'
        '<path d="M30 28 Q52 20 78 26" fill="none" stroke="#8A4420" stroke-width="5" stroke-linecap="round"/>'
        '<circle cx="40" cy="18" r="4" fill="#E8B26A"/><circle cx="82" cy="14" r="4" fill="#E8B26A"/>'
        "</g>"
    )


def mascot(expression: str = "happy", prop: str = "none") -> str:
    """Retorna o <svg> do mascote. expression: happy | sad | curious; prop: none | brownie | magnifier | sign404 | bag."""
    W, H = 400, 430
    parts: list[str] = []

    # decorações discretas (corações e faíscas) — apenas na expressão alegre
    if expression == "happy":
        parts.append(
            f'<path d="M72 78c-8-9-22 1-14 12 5 6 14 11 14 11s9-5 14-11c8-11-6-21-14-12z" fill="{ORANGE}" stroke="{OUT}" stroke-width="3" transform="scale(.7) translate(20 40)"/>'
            f'<path d="M338 70l14-18M350 96l22-6M346 124l20 6" stroke="{YELLOW}" stroke-width="9" stroke-linecap="round"/>'
        )

    # cabelo (atrás da cabeça)
    for cx, cy, r in [(98, 205, 34), (88, 245, 30), (304, 205, 34), (314, 245, 30), (110, 160, 30), (292, 160, 30)]:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{HAIR}" stroke="{OUT}" stroke-width="5"/>')

    # corpo (camiseta preta) e emblema K
    parts.append(
        f'<path d="M48 430 C48 346 118 316 200 316 C282 316 352 346 352 430 Z" fill="{CHARCOAL}" stroke="{OUT}" stroke-width="6"/>'
        f'<circle cx="262" cy="378" r="17" fill="{YELLOW}" stroke="{OUT}" stroke-width="3"/>'
        f'<path d="M256 369v18M256 378l12-9M258 378l11 9" fill="none" stroke="{ORANGE}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    # pescoço e cabeça
    parts.append(f'<rect x="170" y="268" width="60" height="54" rx="22" fill="{SKIN_SHADE}" stroke="{OUT}" stroke-width="5"/>')
    parts.append(f'<ellipse cx="200" cy="200" rx="108" ry="100" fill="{SKIN}" stroke="{OUT}" stroke-width="6"/>')

    # boné: calota laranja com topo branco, aba e botão
    parts.append(
        f'<path d="M92 186 C88 108 140 62 200 62 C262 62 312 108 308 186 Z" fill="{ORANGE}" stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
        f'<path d="M132 96 C150 70 250 70 268 96 C240 84 160 84 132 96 Z" fill="#FFFFFF" stroke="{OUT}" stroke-width="4" stroke-linejoin="round"/>'
        f'<circle cx="200" cy="64" r="9" fill="#FFFFFF" stroke="{OUT}" stroke-width="4"/>'
        f'<path d="M82 192 C120 150 280 150 318 192 C300 210 100 210 82 192 Z" fill="{ORANGE_DARK}" stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
    )

    # olhos / sobrancelhas / boca por expressão
    if expression == "happy":
        parts.append(
            f'<path d="M144 232 Q162 208 180 232" fill="none" stroke="{OUT}" stroke-width="8" stroke-linecap="round"/>'
            f'<path d="M220 232 Q238 208 256 232" fill="none" stroke="{OUT}" stroke-width="8" stroke-linecap="round"/>'
        )
        mouth = (
            f'<path d="M150 262 Q200 258 250 262 Q246 320 200 322 Q154 320 150 262 Z" fill="#7A1212" stroke="{OUT}" stroke-width="5" stroke-linejoin="round"/>'
            '<path d="M154 266 Q200 262 246 266 Q244 282 200 282 Q156 282 154 266 Z" fill="#FFFFFF"/>'
            '<path d="M172 308 Q200 292 228 308 Q214 322 200 322 Q186 322 172 308 Z" fill="#E8626B"/>'
        )
    elif expression == "sad":
        parts.append(
            f'<circle cx="162" cy="234" r="11" fill="#FFFFFF" stroke="{OUT}" stroke-width="4"/><circle cx="164" cy="238" r="6" fill="{OUT}"/>'
            f'<circle cx="238" cy="234" r="11" fill="#FFFFFF" stroke="{OUT}" stroke-width="4"/><circle cx="236" cy="238" r="6" fill="{OUT}"/>'
            f'<path d="M140 214 L180 224M260 214 L220 224" stroke="{OUT}" stroke-width="7" stroke-linecap="round"/>'
            '<path d="M174 258c-3 10-2 18 2 22" stroke="#7DC4F0" stroke-width="6" stroke-linecap="round" fill="none"/>'
        )
        mouth = f'<path d="M172 296 Q200 270 228 296" fill="none" stroke="{OUT}" stroke-width="7" stroke-linecap="round"/>'
    else:  # curious
        parts.append(
            f'<circle cx="162" cy="232" r="13" fill="#FFFFFF" stroke="{OUT}" stroke-width="4"/><circle cx="168" cy="234" r="7" fill="{OUT}"/>'
            f'<circle cx="238" cy="232" r="13" fill="#FFFFFF" stroke="{OUT}" stroke-width="4"/><circle cx="244" cy="234" r="7" fill="{OUT}"/>'
            f'<path d="M144 206 Q162 196 182 208" fill="none" stroke="{OUT}" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M222 212 L258 206" fill="none" stroke="{OUT}" stroke-width="7" stroke-linecap="round"/>'
        )
        mouth = f'<path d="M178 288 Q200 298 224 284" fill="none" stroke="{OUT}" stroke-width="7" stroke-linecap="round"/>'
    parts.append(f'<ellipse cx="132" cy="268" rx="18" ry="11" fill="#F47C7C" opacity=".55"/><ellipse cx="268" cy="268" rx="18" ry="11" fill="#F47C7C" opacity=".55"/>')
    parts.append(mouth)

    # adereços (por cima do corpo)
    hand = lambda x, y: f'<circle cx="{x}" cy="{y}" r="22" fill="{SKIN}" stroke="{OUT}" stroke-width="5"/>'
    if prop == "brownie":
        parts.append(_brownie_prop(150, 328, 0.95) + hand(150, 396) + hand(268, 396))
    elif prop == "magnifier":
        parts.append(
            f'<circle cx="86" cy="330" r="48" fill="#E9F6FF" fill-opacity=".55" stroke="{OUT}" stroke-width="8"/>'
            f'<path d="M120 366 L158 404" stroke="{OUT}" stroke-width="14" stroke-linecap="round"/>'
            f'<path d="M120 366 L158 404" stroke="{ORANGE}" stroke-width="6" stroke-linecap="round"/>' + hand(150, 396)
        )
    elif prop == "sign404":
        parts.append(
            f'<rect x="96" y="318" width="208" height="104" rx="12" fill="#FFFFFF" stroke="{OUT}" stroke-width="6"/>'
            f'<text x="200" y="394" text-anchor="middle" font-family="Arial Rounded MT Bold, Arial, Helvetica, sans-serif" font-weight="900" font-size="72" fill="{OUT}">404</text>'
            + hand(104, 410) + hand(296, 410)
        )
    elif prop == "bag":
        parts.append(
            f'<path d="M110 340 H290 L300 428 H100 Z" fill="#E0A15B" stroke="{OUT}" stroke-width="6" stroke-linejoin="round"/>'
            f'<path d="M150 340 C150 312 250 312 250 340" fill="none" stroke="{OUT}" stroke-width="6"/>'
            f'<circle cx="200" cy="384" r="22" fill="{YELLOW}" stroke="{OUT}" stroke-width="4"/>'
            f'<path d="M192 372v24M192 384l14-12M194 384l13 12" fill="none" stroke="{ORANGE}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
            + hand(104, 404) + hand(296, 404)
        )
    titles = {
        ("happy", "brownie"): "Mascote da KNAZH sorrindo e segurando um brownie (ilustração)",
        ("happy", "none"): "Mascote da KNAZH sorrindo (ilustração)",
        ("happy", "bag"): "Mascote da KNAZH segurando uma sacola de pedido (ilustração)",
        ("curious", "magnifier"): "Mascote da KNAZH procurando com uma lupa (ilustração)",
        ("sad", "none"): "Mascote da KNAZH preocupado (ilustração)",
        ("sad", "sign404"): "Mascote da KNAZH segurando uma placa 404 (ilustração)",
    }
    return svg(W, H, "".join(parts), titles.get((expression, prop), "Mascote da KNAZH (ilustração)"))


# --------------------------------------------------------------------------- produtos (demo)
def _bg(seed: int) -> tuple[str, str]:
    rnd = random.Random(seed)
    defs = (
        '<radialGradient id="g" cx="50%" cy="45%" r="75%"><stop offset="0" stop-color="#FFB323"/>'
        '<stop offset=".55" stop-color="#F0781E"/><stop offset="1" stop-color="#B4410C"/></radialGradient>'
    )
    bokeh = "".join(
        f'<circle cx="{rnd.randint(0, 640)}" cy="{rnd.randint(0, 480)}" r="{rnd.randint(14, 46)}" fill="#FFE2A8" opacity="{rnd.choice([.10, .14, .18])}"/>'
        for _ in range(9)
    )
    return defs, f'<rect width="640" height="480" fill="url(#g)"/>{bokeh}<ellipse cx="320" cy="400" rx="230" ry="26" fill="#000" opacity=".18"/>'


def _scatter(seed: int, n: int, x0: int, x1: int, y0: int, y1: int, colors: list[str], r=(3, 6)) -> str:
    rnd = random.Random(seed)
    return "".join(
        f'<circle cx="{rnd.randint(x0, x1)}" cy="{rnd.randint(y0, y1)}" r="{rnd.randint(*r)}" fill="{rnd.choice(colors)}"/>' for _ in range(n)
    )


def product_brownie(name: str, seed: int, top: str, drizzle: str, dots: list[str], extra: str = "") -> str:
    defs, bg = _bg(seed)
    body = bg + (
        f'<path d="M150 230 L230 150 L510 150 L430 230 Z" fill="{top}" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M150 230 L430 230 L430 350 L150 350 Z" fill="#3A1A0C" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M430 230 L510 150 L510 270 L430 350 Z" fill="#2A1209" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M160 262 H420 M160 300 H420" stroke="#4D2612" stroke-width="3" opacity=".6"/>'
        f'<path d="M185 215 Q230 175 280 205 T370 185 T470 168" fill="none" stroke="{drizzle}" stroke-width="12" stroke-linecap="round"/>'
        f'<path d="M205 192 Q260 215 320 180 T440 205" fill="none" stroke="{drizzle}" stroke-width="9" stroke-linecap="round" opacity=".9"/>'
        + _scatter(seed, 26, 190, 480, 165, 222, dots)
        + extra
    )
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs)


def _strawberry(x: int, y: int, s: float = 1.0) -> str:
    return (
        f'<g transform="translate({x} {y}) scale({s})"><path d="M0 -22 C26 -22 30 6 0 30 C-30 6 -26 -22 0 -22Z" fill="#D8202F" stroke="#7A0E18" stroke-width="3"/>'
        '<path d="M-12 -22 L0 -34 L12 -22 L0 -16Z" fill="#3E8E3A"/><circle cx="-8" cy="-6" r="2" fill="#FFE8A0"/><circle cx="6" cy="0" r="2" fill="#FFE8A0"/><circle cx="-2" cy="12" r="2" fill="#FFE8A0"/></g>'
    )


def product_brownie_strawberry(name: str, seed: int) -> str:
    defs, bg = _bg(seed)
    body = bg + (
        '<path d="M150 230 L230 150 L510 150 L430 230 Z" fill="#F3E6D0" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M150 230 L430 230 L430 350 L150 350 Z" fill="#3A1A0C" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M430 230 L510 150 L510 270 L430 350 Z" fill="#2A1209" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M185 215 Q230 175 280 205 T370 185 T470 168" fill="none" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" opacity=".9"/>'
        + _strawberry(250, 178, 1.1) + _strawberry(340, 168, 1.0) + _strawberry(420, 182, 1.1)
    )
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs)


def product_brigadeiro(name: str, seed: int, ball: str, sprinkle: list[str]) -> str:
    defs, bg = _bg(seed)
    rnd = random.Random(seed)
    balls = ""
    spots = [(250, 250), (320, 238), (390, 250), (285, 296), (355, 296), (320, 200), (260, 205), (380, 205), (215, 296), (425, 296)]
    for (x, y) in spots:
        balls += f'<circle cx="{x}" cy="{y}" r="36" fill="{ball}" stroke="#1B0C05" stroke-width="4"/>'
        for _ in range(16):
            a = rnd.uniform(0, 6.28)
            d = rnd.uniform(0, 30)
            px, py = x + d * 0.9 * __import__("math").cos(a), y + d * 0.9 * __import__("math").sin(a)
            balls += f'<rect x="{px:.0f}" y="{py:.0f}" width="9" height="3" rx="1.5" fill="{rnd.choice(sprinkle)}" transform="rotate({rnd.randint(0, 180)} {px:.0f} {py:.0f})"/>'
    body = bg + (
        '<path d="M170 290 Q320 400 470 290 Z" fill="#7A3B1B" stroke="#1B0C05" stroke-width="5"/>'
        '<ellipse cx="320" cy="290" rx="150" ry="26" fill="#9A4F26" stroke="#1B0C05" stroke-width="5"/>'
        + balls
    )
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs)


def product_cup(name: str, seed: int, layers: list[str], top: str, swirl: bool = True, topping: str = "") -> str:
    defs, bg = _bg(seed)
    ly = ""
    y = 365
    h = 150 / len(layers)
    clip = '<clipPath id="cup"><path d="M215 215 L425 215 L400 372 Q320 392 240 372 Z"/></clipPath>'
    for i, c in enumerate(layers):
        ly += f'<rect x="200" y="{y - h * (i + 1):.0f}" width="240" height="{h + 2:.0f}" fill="{c}"/>'
    swirl_svg = (
        f'<path d="M205 220 Q320 150 435 220 Q420 190 380 180 Q350 130 320 118 Q290 130 262 180 Q222 190 205 220Z" fill="{top}" stroke="#1B0C05" stroke-width="4" stroke-linejoin="round"/>'
        f'<path d="M262 180 Q320 160 380 180" fill="none" stroke="#FFFFFF" stroke-width="4" opacity=".25"/>'
        if swirl
        else f'<ellipse cx="320" cy="214" rx="108" ry="22" fill="{top}" stroke="#1B0C05" stroke-width="4"/>'
    )
    body = bg + (
        f'<g clip-path="url(#cup)">{ly}</g>'
        '<path d="M215 215 L425 215 L400 372 Q320 392 240 372 Z" fill="#FFFFFF" fill-opacity=".14" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M236 236 L246 350" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" opacity=".45"/>'
        + swirl_svg + topping
    )
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs + clip)


def product_cookie(name: str, seed: int) -> str:
    defs, bg = _bg(seed)
    rnd = random.Random(seed)

    def cookie(cx, cy, r):
        s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#D9A25A" stroke="#1B0C05" stroke-width="5"/><circle cx="{cx}" cy="{cy}" r="{r - 12}" fill="#E5B570" opacity=".6"/>'
        for _ in range(11):
            a, d = rnd.uniform(0, 6.28), rnd.uniform(0, r - 20)
            px, py = cx + d * __import__("math").cos(a), cy + d * __import__("math").sin(a)
            s += f'<path d="M{px:.0f} {py - 8:.0f} L{px + 9:.0f} {py + 6:.0f} L{px - 9:.0f} {py + 6:.0f}Z" fill="#3B1B0D"/>'
        return s

    body = bg + cookie(280, 300, 105) + cookie(390, 250, 105) + cookie(320, 195, 100)
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs)


def product_cake_slice(name: str, seed: int) -> str:
    defs, bg = _bg(seed)
    body = bg + (
        '<path d="M170 330 L470 330 L470 250 L170 250 Z" fill="#4A2412" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M170 250 L470 250 L470 225 L170 225 Z" fill="#F3E6D0" stroke="#1B0C05" stroke-width="4"/>'
        '<path d="M170 225 L470 225 L470 150 L170 150 Z" fill="#4A2412" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        '<path d="M160 150 Q320 100 480 150 L470 176 Q440 200 410 176 Q380 210 350 178 Q320 214 290 178 Q256 206 228 176 Q196 196 170 176 Z" fill="#2B1209" stroke="#1B0C05" stroke-width="5" stroke-linejoin="round"/>'
        + _scatter(seed, 18, 200, 440, 130, 170, ["#F3E6D0", "#E8B26A", "#FFB323"], (3, 5))
    )
    return svg(640, 480, body, f"Ilustração demonstrativa: {name}", defs)


# --------------------------------------------------------------------------- UI
def blob(color_a: str, color_b: str, flip: bool = False) -> str:
    """Duas manchas orgânicas FECHADAS (sem borda reta), para fundos decorativos."""
    t = ' transform="translate(600 0) scale(-1 1)"' if flip else ""
    body = (
        f'<g{t}><path d="M40 200C20 120 90 40 190 50C260 58 300 110 380 100C470 90 540 40 580 90C620 140 560 250 460 270'
        f'C340 295 250 240 170 270C100 290 55 260 40 200Z" fill="{color_a}"/>'
        f'<path d="M300 230C320 170 400 150 470 170C540 190 590 250 540 285C480 320 360 300 320 280C300 268 296 250 300 230Z" fill="{color_b}"/></g>'
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 320" width="600" height="320" aria-hidden="true">{body}</svg>\n')


def main() -> None:
    for sub in ("mascote", "produtos", "ui"):
        (IMG / sub).mkdir(parents=True, exist_ok=True)

    masc = {
        "mascote-feliz-brownie": ("happy", "brownie"),
        "mascote-feliz": ("happy", "none"),
        "mascote-sacola": ("happy", "bag"),
        "mascote-busca": ("curious", "magnifier"),
        "mascote-ops": ("sad", "none"),
        "mascote-404": ("sad", "sign404"),
    }
    for fname, (expr, prop) in masc.items():
        (IMG / "mascote" / f"{fname}.svg").write_text(mascot(expr, prop), encoding="utf-8")

    P = IMG / "produtos"
    arts = {
        "brownie-tradicional": product_brownie("Brownie Tradicional", 1, "#4A2412", "#C8782E", ["#E8B26A", "#8A4420"]),
        "brownie-oreo": product_brownie("Brownie com Oreo", 2, "#EFE4D2", "#FFFFFF", ["#2B1B12", "#3B2A20"]),
        "brownie-brigadeiro": product_brownie("Brownie com Brigadeiro", 3, "#3B1A0C", "#5A2A14", ["#B58A5E", "#6B3A1E", "#E9D5B0"]),
        "brownie-chocolate-branco": product_brownie_strawberry("Brownie de Chocolate Branco", 4),
        "brownie-doce-de-leite": product_brownie("Brownie com Doce de Leite", 5, "#B87A32", "#E3A653", ["#6B3A1E", "#D9B27A"]),
        "brownie-pacoca": product_brownie("Brownie de Paçoca", 6, "#4A2412", "#C99A5A", ["#D9B27A", "#B88848", "#E6C890"]),
        "brownie-pistache": product_brownie("Brownie de Pistache", 7, "#4A2412", "#8FA24B", ["#6F8A3A", "#A8BA62", "#D8E0A0"]),
        "brownie-chocolate-belga": product_brownie("Brownie com Chocolate Belga", 8, "#2E150A", "#6A3418", ["#8A5A38", "#B0825A", "#4A2412"]),
        "brigadeiro-gourmet": product_brigadeiro("Brigadeiro Gourmet", 9, "#3A1B0E", ["#E9D5B0", "#7A4A2A", "#C79A62"]),
        "brigadeiro-ninho": product_brigadeiro("Brigadeiro de Ninho", 10, "#F2E3C4", ["#FFFFFF", "#E8C98A", "#F8E8C8"]),
        "brigadeiro-tradicional": product_brigadeiro("Brigadeiro Tradicional", 11, "#2E150A", ["#1B0C05", "#5A3A26", "#8A6A52"]),
        "bolo-no-pote": product_cup("Bolo no Pote", 12, ["#F3E6D0", "#4A2412", "#E8626B", "#F3E6D0", "#4A2412"], "#FFF4DE", True,
                                    _strawberry(290, 156, .9) + _strawberry(350, 150, .9)),
        "bolo-chocolate": product_cake_slice("Bolo de Chocolate", 13),
        "mousse-chocolate": product_cup("Mousse de Chocolate", 14, ["#F3E6D0", "#4A2412"], "#5A2A14", True),
        "mousse-maracuja": product_cup("Mousse de Maracujá", 15, ["#F3E6D0", "#F1C232"], "#F6D55C", True),
        "mousse-morango": product_cup("Mousse de Morango", 16, ["#F3E6D0", "#E8627A"], "#F29AAE", True),
        "cookie": product_cookie("Cookie", 17),
    }
    for name, content in arts.items():
        (P / f"{name}.svg").write_text(content, encoding="utf-8")

    (IMG / "ui" / "blob-laranja.svg").write_text(blob(YELLOW, ORANGE), encoding="utf-8")
    (IMG / "ui" / "blob-laranja-espelhado.svg").write_text(blob(YELLOW, ORANGE, True), encoding="utf-8")
    print("Artes geradas:", len(masc), "mascotes,", len(arts), "produtos demo, 2 blobs")


if __name__ == "__main__":
    main()
