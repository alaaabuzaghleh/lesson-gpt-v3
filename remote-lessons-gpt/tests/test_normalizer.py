from remote_lessons_gpt.normalizer import (
    looks_like_visual_arabic,
    normalize_general,
    restore_arabic_logical_order,
)


def test_arabic_normalization():
    assert normalize_general("القُوَّةُ") == "القوة"
    assert normalize_general("إختبار ١٢٣") == "اختبار 123"


def test_restore_reversed_arabic_ocr():
    assert restore_arabic_logical_order("ميلعتلا ةرازو") == "وزارة التعليم"
    assert restore_arabic_logical_order("تاراسملا ماظن") == "نظام المسارات"
    assert restore_arabic_logical_order("تايضايرلا") == "الرياضيات"


def test_restore_arabic_leaves_logical_text_unchanged():
    logical = "وزارة التعليم"
    assert restore_arabic_logical_order(logical) == logical
    assert restore_arabic_logical_order("الوحدة الأولى") == "الوحدة الأولى"
    assert restore_arabic_logical_order("مثلا") == "مثلا"


def test_restore_arabic_forces_remaining_lines_on_visual_page():
    restored = restore_arabic_logical_order("ميلعتلا ةرازو\nالبقتسم")
    assert restored == "وزارة التعليم\nمستقبلا"
    assert restore_arabic_logical_order("Grade 8 تايضايرلا") == "Grade 8 الرياضيات"
    html = "<table><tr><td>ميلعتلا ةرازو</td></tr></table>"
    assert restore_arabic_logical_order(html) == "<table><tr><td>وزارة التعليم</td></tr></table>"
    assert restore_arabic_logical_order("$$F = ma$$") == "$$F = ma$$"


def test_restore_math_sentence_visual_order():
    visual = "لحلا ناف،وه نيددعلل ربكالا كرتشملا مساقلا نا امب"
    restored = restore_arabic_logical_order(visual)
    assert "القاسم المشترك" in restored
    assert restored.startswith("بما")
    assert "الحل" in restored
    assert looks_like_visual_arabic(visual)


def test_looks_like_visual_arabic():
    assert looks_like_visual_arabic("ميلعتلا ةرازو")
    assert not looks_like_visual_arabic("وزارة التعليم")
