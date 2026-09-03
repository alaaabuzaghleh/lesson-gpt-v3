from book_ingestor.hierarchy import HierarchyResolver, infer_structure_headings
from book_ingestor.ocr_cleanup import choose_page_text, repair_arabic_ocr
from book_ingestor.schemas import PageExtraction


def test_mineru_text_is_used_when_present():
    mineru = "$1 4 0 0 ( 1 0 0 )$\nالفصل 5 العلاقات والدوال النسبية"
    pdf = "أجد المضاعف المشترك الأصغر لكثيرات الحدود"
    text, source = choose_page_text(mineru, pdf)
    assert source == "mineru"
    assert "الفصل 5" in text


def test_pdf_only_when_mineru_is_empty():
    text, source = choose_page_text("  ", "نص الطبقة")
    assert source == "pdf"
    assert "نص الطبقة" in text


def test_repair_common_arabic_ocr_errors():
    raw = (
        "عدت خرائط هذا املقرر مبا يف ذلك الحدود الظاهرة فيها الغراض التعليم "
        "وااليضاح فقط( )ا"
    )
    extra = " والن�شر املركز املسارات ستركزفي"
    fixed = repair_arabic_ocr(raw)
    extra_fixed = repair_arabic_ocr(extra)
    assert "المقرر" in fixed
    assert "بما" in fixed
    assert "في ذلك" in fixed
    assert "لاغراض" in fixed
    assert "والايضاح" in fixed
    assert "والنشر" in extra_fixed
    assert "المركز" in extra_fixed
    assert "المسارات" in extra_fixed
    assert "ستركز في" in extra_fixed
    assert "�" not in extra_fixed
    assert fixed.startswith("(أعدت")
    assert fixed.endswith(")")
    assert "املركز" not in extra_fixed
    assert "يف" not in fixed.split()


def test_infer_chapter_and_lesson():
    text = "الفصل 5 العلاقات والدوال النسبية\nالدرس 1-2 تبسيط العبارات النسبية"
    found = infer_structure_headings(text)
    assert found["chapter"]
    assert "5" in found["chapter"]
    assert found["lesson"]
    assert "1" in found["lesson"]


def test_hierarchy_ignores_sentence_chapter_and_lesson():
    found = infer_structure_headings(
        "فصل ُ بعد أن تراجع أفكار الدرس مستفيدا م\nدرس ي، ومقترحاتكم محل اهتمامنا"
    )
    assert found["chapter"] is None
    assert found["lesson"] is None


def test_hierarchy_stays_on_later_pages():
    resolver = HierarchyResolver()
    resolver.apply_page(
        PageExtraction(
            pdf_page_number=4,
            explicit_chapter_title="الفصل 5",
            explicit_lesson_title="الدرس 1-2",
            blocks=[],
        )
    )
    later = resolver.apply_ocr_text("مثال: بسط العبارة التالية")
    assert later.chapter_title == "الفصل 5"
    assert later.lesson_title == "الدرس 1-2"
    assert later.chapter_id
    assert later.lesson_id
    noisy = resolver.apply_ocr_text("تمثيلات متعددة", content_type="unit_title")
    assert noisy.chapter_title == "الفصل 5"
    assert noisy.lesson_title == "الدرس 1-2"
