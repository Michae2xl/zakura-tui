from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image


DOTS = (
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)


def pixel_kind(pixel: tuple[int, int, int, int]) -> str:
    red, green, blue, alpha = pixel
    if alpha < 64:
        return " "
    if red > 180 and red > green * 1.4 and red > blue * 1.15:
        return "p"
    return "f"


def image_to_braille(
    image: Image.Image,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    rgba = image.convert("RGBA")
    glyph_lines: list[str] = []
    color_lines: list[str] = []
    for top in range(0, rgba.height, 4):
        glyph_row: list[str] = []
        color_row: list[str] = []
        for left in range(0, rgba.width, 2):
            bits = 0
            counts = {"p": 0, "f": 0}
            for dx, dy, bit in DOTS:
                if left + dx >= rgba.width or top + dy >= rgba.height:
                    continue
                kind = pixel_kind(rgba.getpixel((left + dx, top + dy)))
                if kind != " ":
                    bits |= bit
                    counts[kind] += 1
            glyph_row.append(chr(0x2800 + bits) if bits else " ")
            if not bits:
                color_row.append(" ")
            else:
                color_row.append("f" if counts["f"] >= 2 else "p")
        glyph_lines.append("".join(glyph_row).rstrip())
        color_lines.append("".join(color_row).rstrip())
    while glyph_lines and not glyph_lines[-1].strip():
        glyph_lines.pop()
        color_lines.pop()
    return tuple(glyph_lines), tuple(color_lines)


def render_svg(
    path: Path, width_cells: int
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    png = cairosvg.svg2png(url=str(path), output_width=width_cells * 2)
    image = Image.open(BytesIO(png)).convert("RGBA")
    return image_to_braille(image)


def combine(
    flower: tuple[tuple[str, ...], tuple[str, ...]],
    wordmark: tuple[tuple[str, ...], tuple[str, ...]],
    gap: int = 2,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    height = max(len(flower[0]), len(wordmark[0]))

    def center(lines: tuple[str, ...], width: int) -> list[str]:
        top = (height - len(lines)) // 2
        return [" " * width] * top + [line.ljust(width) for line in lines] + [
            " " * width
        ] * (height - top - len(lines))

    flower_width = max(map(len, flower[0]), default=0)
    wordmark_width = max(map(len, wordmark[0]), default=0)
    flower_glyphs = center(flower[0], flower_width)
    flower_colors = center(flower[1], flower_width)
    wordmark_glyphs = center(wordmark[0], wordmark_width)
    wordmark_colors = center(wordmark[1], wordmark_width)
    glyphs = tuple(
        f"{left}{' ' * gap}{right}".rstrip()
        for left, right in zip(flower_glyphs, wordmark_glyphs, strict=True)
    )
    colors = tuple(
        f"{left}{' ' * gap}{right}".rstrip()
        for left, right in zip(flower_colors, wordmark_colors, strict=True)
    )
    return glyphs, colors


ASCII_COMPACT = (
    "  .-.     ZZZ  A  K K U U RRR   A",
    " ( * )      Z A A KK  U U R R  A A",
    "  `-'      Z  AAA K K UUU R R  AAA",
)


def write_module(output: Path, flower: Path, wordmark: Path) -> None:
    full = combine(render_svg(flower, 10), render_svg(wordmark, 56))
    compact = combine(render_svg(flower, 8), render_svg(wordmark, 34))
    source = (
        '"""Generated Zakura terminal art. Do not edit by hand."""\n\n'
        f"FULL_GLYPHS = {full[0]!r}\n"
        f"FULL_COLORS = {full[1]!r}\n"
        f"COMPACT_GLYPHS = {compact[0]!r}\n"
        f"COMPACT_COLORS = {compact[1]!r}\n"
        f"ASCII_COMPACT = {ASCII_COMPACT!r}\n"
    )
    output.write_text(source, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flower", type=Path, required=True)
    parser.add_argument("--wordmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_module(args.output, args.flower, args.wordmark)


if __name__ == "__main__":
    main()
