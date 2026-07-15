from PIL import Image

from tools.render_brand import image_to_braille


def test_full_two_by_four_block_becomes_full_braille_cell() -> None:
    image = Image.new("RGBA", (2, 4), (253, 103, 152, 255))
    glyphs, colors = image_to_braille(image)
    assert glyphs == ("⣿",)
    assert colors == ("p",)


def test_fully_transparent_image_is_empty() -> None:
    image = Image.new("RGBA", (2, 4), (0, 0, 0, 0))
    glyphs, colors = image_to_braille(image)
    assert glyphs == ()
    assert colors == ()


def test_dark_pixels_use_foreground_color() -> None:
    image = Image.new("RGBA", (2, 4), (0, 0, 0, 255))
    glyphs, colors = image_to_braille(image)
    assert glyphs == ("⣿",)
    assert colors == ("f",)


def test_two_dark_pixels_preserve_the_flower_center_mark() -> None:
    image = Image.new("RGBA", (2, 4), (253, 103, 152, 255))
    image.putpixel((0, 0), (0, 0, 0, 255))
    image.putpixel((1, 0), (0, 0, 0, 255))
    glyphs, colors = image_to_braille(image)
    assert glyphs == ("⣿",)
    assert colors == ("f",)


def test_generated_art_has_matching_maps() -> None:
    from zakura_tui.generated_brand import (
        COMPACT_COLORS,
        COMPACT_GLYPHS,
        FULL_COLORS,
        FULL_GLYPHS,
    )

    assert len(FULL_GLYPHS) <= 10
    assert len(COMPACT_GLYPHS) <= 8
    assert [len(line) for line in FULL_GLYPHS] == [
        len(line) for line in FULL_COLORS
    ]
    assert [len(line) for line in COMPACT_GLYPHS] == [
        len(line) for line in COMPACT_COLORS
    ]
    flower_colors = "".join(line[:10] for line in FULL_COLORS)
    assert "p" in flower_colors
    assert "f" in flower_colors
