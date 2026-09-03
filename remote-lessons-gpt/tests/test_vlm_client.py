import io

import pytest
from PIL import Image

from remote_lessons_gpt.vlm_client import VLMError, _extract_json, encode_image_for_vlm


def test_extract_json_rejects_empty_response():
    with pytest.raises(VLMError, match="empty response"):
        _extract_json("")


def test_extract_json_rejects_non_json():
    with pytest.raises(VLMError, match="non-JSON"):
        _extract_json("the page is a cover")


def test_extract_json_parses_fenced_object():
    assert _extract_json('```json\n{"title": "كتاب"}\n```') == {"title": "كتاب"}


def test_encode_image_for_vlm_downscales_large_pages():
    image = Image.new("RGB", (2400, 3200), color=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data_url, encoded = encode_image_for_vlm(buffer.getvalue(), max_side=1280)
    assert data_url.startswith("data:image/jpeg;base64,")
    assert encoded
    with Image.open(io.BytesIO(__import__("base64").b64decode(encoded))) as resized:
        assert max(resized.size) <= 1280
