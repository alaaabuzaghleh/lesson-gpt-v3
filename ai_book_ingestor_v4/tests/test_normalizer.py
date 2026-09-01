from book_ingestor.normalizer import normalize_general


def test_arabic_normalization():
    assert normalize_general("القُوَّةُ") == "القوة"
    assert normalize_general("إختبار ١٢٣") == "اختبار 123"
