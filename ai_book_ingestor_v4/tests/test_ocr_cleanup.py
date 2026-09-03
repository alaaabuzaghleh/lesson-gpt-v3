from book_ingestor.hierarchy import HierarchyResolver, infer_structure_headings
from book_ingestor.ocr_cleanup import choose_page_text
from book_ingestor.schemas import PageExtraction


def test_mineru_text_is_used_as_is():
    mineru = "$1 4 0 0 ( 1 0 0 )$\nالفصل 5 العلاقات والدوال النسبية"
    pdf = "أجد المضاعف المشترك الأصغر لكثيرات الحدود"
    text, source = choose_page_text(mineru, pdf)
    assert source == "mineru"
    assert text == mineru


def test_pdf_only_when_mineru_is_empty():
    text, source = choose_page_text("  ", "نص الطبقة")
    assert source == "pdf"
    assert "نص الطبقة" in text


def test_infer_chapter_and_lesson():
    text = "الفصل 5 العلاقات والدوال النسبية\nالدرس 1-2 تبسيط العبارات النسبية"
    found = infer_structure_headings(text)
    assert found["chapter"]
    assert "5" in found["chapter"]
    assert found["lesson"]
    assert "1" in found["lesson"]


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
