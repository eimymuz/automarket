"""Genera build/icon.png (512x512) para el instalador, sin dependencias externas.

    python build/make_icon.py

Cuadrado azul redondeado con la silueta de un auto en blanco (suavizado por supermuestreo).
"""
import struct
import zlib
from pathlib import Path

SIZE, SS = 512, 3  # tamaño final y factor de supermuestreo
BLUE, WHITE, DARK = (42, 120, 214), (255, 255, 255), (18, 22, 31)


def inside_round_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def inside_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def inside_cabin(x, y):
    # trapecio: techo de 190 a 322, base de 140 a 372, de y=150 a y=250
    if not 150 <= y <= 252:
        return False
    t = (y - 150) / 102
    left, right = 190 - 50 * t, 322 + 50 * t
    return left <= x <= right


def color_at(x, y):
    if not inside_round_rect(x, y, 16, 16, 496, 496, 108):
        return None  # transparente
    for cx in (166, 346):
        if inside_circle(x, y, cx, 340, 46):
            return BLUE if inside_circle(x, y, cx, 340, 18) else DARK
    # Ventanas: dentro de la cabina, separadas por un poste central de 12 px
    window = inside_cabin(x, y) and 168 <= y <= 240 and abs(x - 256) > 6
    if window and inside_round_rect(x, y, 182, 168, 330, 240, 12):
        t = (y - 168) / 72
        if 196 - 40 * t + 8 <= x <= 316 + 40 * t - 8:
            return BLUE
    if inside_cabin(x, y) or inside_round_rect(x, y, 86, 236, 426, 336, 40):
        return WHITE
    return BLUE


def main() -> None:
    rows = []
    n = SS * SS
    for py in range(SIZE):
        row = bytearray([0])
        for px in range(SIZE):
            r = g = b = a = 0
            for sy in range(SS):
                for sx in range(SS):
                    c = color_at(px + (sx + 0.5) / SS, py + (sy + 0.5) / SS)
                    if c:
                        r, g, b, a = r + c[0], g + c[1], b + c[2], a + 255
            hits = a // 255
            row += bytes([r // hits, g // hits, b // hits, a // n]) if hits else b"\0\0\0\0"
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
    out = Path(__file__).with_name("icon.png")
    out.write_bytes(png)
    print(f"Ícono generado: {out} ({len(png) // 1024} KB)")


if __name__ == "__main__":
    main()
