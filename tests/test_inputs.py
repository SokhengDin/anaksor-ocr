import io

import numpy as np
import pytest
from PIL import Image

from anaksor.inputs import IMAGE_FORMATS, InputError, is_pdf, load_image


def encoded(fmt, size=(30, 20), **kw):
    b = io.BytesIO()
    Image.new("RGB", size, (200, 10, 10)).save(b, fmt, **kw)
    return b.getvalue()


@pytest.mark.parametrize("fmt", IMAGE_FORMATS)
def test_allowed_formats(fmt):
    img = load_image(encoded(fmt))
    assert img.mode == "RGB" and img.size == (30, 20)


@pytest.mark.parametrize("fmt", ["GIF", "PCX", "TGA", "ICO", "PPM", "SGI", "IM"])
def test_other_formats_never_reach_a_decoder(fmt):
    with pytest.raises(InputError, match="allowed formats"):
        load_image(encoded(fmt))


def test_phone_mpo_jpeg_opens():
    a = Image.new("RGB", (30, 20), "red")
    b = io.BytesIO()
    a.save(b, "MPO", save_all=True, append_images=[a])
    assert load_image(b.getvalue()).size == (30, 20)


def test_exif_rotation_and_downscale(tmp_path):
    img = Image.new("RGB", (40, 20), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # rotate 90 CW on display
    p = tmp_path / "r.jpg"
    img.save(p, exif=exif)
    assert load_image(p).size == (20, 40)
    assert max(load_image(p, max_px=10).size) == 10


def test_arrays_and_garbage():
    assert load_image(np.zeros((5, 6), np.uint8)).size == (6, 5)
    assert load_image(np.zeros((5, 6, 4), np.uint8)).size == (6, 5)
    with pytest.raises(InputError):
        load_image(b"not an image")
    with pytest.raises(TypeError):
        load_image(42)


def test_is_pdf(tmp_path):
    assert is_pdf(b"%PDF-1.7\n...") and not is_pdf(b"\x89PNG")
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    assert is_pdf(p) and not is_pdf(tmp_path / "missing.pdf")
