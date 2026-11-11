"""
Visual and Unit Tests for Hindi Devanagari Font and Subtitle Rendering (Phase 6)
Verifies Unicode NFC normalization, grapheme cluster integrity, and actual frame rendering.
"""
import os
import pytest
from PIL import Image, ImageDraw
from video.fonts import (
    normalize_hindi,
    split_devanagari_graphemes,
    get_devanagari_font,
    is_devanagari,
)
from video.creator import _draw_normal_caption, _draw_shorts_caption, _wrap_text

TEST_HINDI_SENTENCE = "प्राचीन सभ्यता, महाराणा प्रताप, चंद्रगुप्त मौर्य, ऐतिहासिक युद्ध, भारत का गौरवशाली इतिहास।"


def test_is_devanagari_detection():
    assert is_devanagari("महाराणा प्रताप") is True
    assert is_devanagari("Ancient Rome") is False
    assert is_devanagari("Haldighati युद्ध") is True


def test_unicode_nfc_normalization():
    raw = "भारत"
    norm = normalize_hindi(raw)
    assert norm == "भारत"
    assert len(norm) == len(raw)


def test_devanagari_grapheme_clusters_preserve_conjuncts():
    # "प्रताप": 'प्र' must be a single cluster (प + halant + र), not separated
    clusters = split_devanagari_graphemes("प्रताप")
    assert clusters[0] == "प्र"
    assert clusters[1] == "ता"
    assert clusters[2] == "प"


def test_devanagari_font_loading():
    font = get_devanagari_font(36, bold=True)
    assert font is not None
    # Verify measuring text bbox works without error
    img = Image.new("RGBA", (100, 100))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), TEST_HINDI_SENTENCE, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    assert width > 100
    assert height > 20


def test_render_normal_longform_caption_frame(tmp_path):
    # Render into a 1920x1080 16:9 frame
    frame = Image.new("RGB", (1920, 1080), (20, 20, 30))
    result = _draw_normal_caption(frame, TEST_HINDI_SENTENCE)
    assert result.size == (1920, 1080)
    
    # Save test artifact frame
    out_path = os.path.join(tmp_path, "test_normal_caption.png")
    result.save(out_path)
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 1000


def test_render_shorts_caption_frame(tmp_path):
    # Render into a 1080x1920 9:16 vertical frame
    frame = Image.new("RGB", (1080, 1920), (15, 15, 25))
    result = _draw_shorts_caption(frame, TEST_HINDI_SENTENCE)
    assert result.size == (1080, 1920)
    
    out_path = os.path.join(tmp_path, "test_shorts_caption.png")
    result.save(out_path)
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 1000


def test_wrap_text_nfc_preserves_words():
    font = get_devanagari_font(40, bold=True)
    img = Image.new("RGBA", (100, 100))
    draw = ImageDraw.Draw(img)
    
    lines = _wrap_text(draw, TEST_HINDI_SENTENCE, font, max_width=400)
    assert len(lines) >= 2
    # Check that words are reassembled properly
    rejoined = " ".join(lines)
    assert "महाराणा प्रताप" in rejoined
    assert "चंद्रगुप्त मौर्य" in rejoined
