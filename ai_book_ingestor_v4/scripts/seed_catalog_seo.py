from __future__ import annotations

from typing import Any

from book_ingestor.api.catalog_seo import CatalogDuplicateError, slugify_ar, slugify_en
from book_ingestor.api.job_store import JobStore
from book_ingestor.config import settings


def _html(parts: list[str]) -> str:
    return "".join(parts)


def country_seo(code: str) -> dict[str, str]:
    if code == "SA":
        return {
            "seo_title_en": "Saudi Arabia | AI Education Platform — Books, Grades & Subjects",
            "seo_title_ar": "السعودية | منصة التعليم بالذكاء الاصطناعي — كتب، صفوف ومواد",
            "seo_meta_description_en": (
                "Learn Saudi Arabia on the AI education platform: public, private, international and Tahfeez. "
                "Smart lessons, textbooks and exam practice for every grade and subject."
            ),
            "seo_meta_description_ar": (
                "تعلّم مناهج السعودية على منصة التعليم بالذكاء الاصطناعي: العام، الأهلي، الدولي والتحفيظ. "
                "دروس ذكية وكتب وتمارين لكل صف ومادة."
            ),
            "seo_keywords_en": (
                "AI education platform Saudi Arabia, education platform KSA, "
                "Saudi curriculum AI, Saudi textbooks, Ministry of Education Saudi, "
                "online learning Saudi Arabia"
            ),
            "seo_keywords_ar": (
                "منصة التعليم بالذكاء الاصطناعي السعودية, منصة التعليم السعودية, "
                "مناهج السعودية, كتب مدرسية سعودية, وزارة التعليم, تعليم أونلاين السعودية"
            ),
            "seo_description_en": _html(
                [
                    "<h2>Saudi Arabia on the AI education platform</h2>",
                    "<p>This <strong>education platform</strong> uses <strong>artificial intelligence</strong> to organise Saudi Arabia learning by system, grade and subject — so students find the right book and practice faster.</p>",
                    "<h2>What you can study</h2>",
                    "<p>Open <strong>public education</strong>, private national schools, international programmes, or Quran memorization. Each page is written for search in English and Arabic.</p>",
                    "<p>Official ministry updates: "
                    '<a href="https://www.moe.gov.sa/" rel="noopener noreferrer">Saudi Ministry of Education</a>.</p>',
                ]
            ),
            "seo_description_ar": _html(
                [
                    "<h2>السعودية على منصة التعليم بالذكاء الاصطناعي</h2>",
                    "<p>هذه <strong>منصة التعليم</strong> تعتمد <strong>الذكاء الاصطناعي</strong> لتنظيم مناهج السعودية حسب النظام والصف والمادة، ليصل الطالب إلى الكتاب والتمرين المناسب بسرعة.</p>",
                    "<h2>ماذا ستدرس؟</h2>",
                    "<p>تصفّح <strong>التعليم العام</strong>، والتعليم الأهلي، والتعليم الدولي، وتحفيظ القرآن. كل صفحة مُحسَّنة للبحث بالعربية والإنجليزية.</p>",
                    "<p>التحديثات الرسمية: "
                    '<a href="https://www.moe.gov.sa/" rel="noopener noreferrer">وزارة التعليم السعودية</a>.</p>',
                ]
            ),
            "slug_en": "saudi-arabia",
            "slug_ar": "السعودية",
        }
    return {
        "seo_title_en": "Jordan | AI Education Platform — Tawjihi, Grades & Subjects",
        "seo_title_ar": "الأردن | منصة التعليم بالذكاء الاصطناعي — توجيهي، صفوف ومواد",
        "seo_meta_description_en": (
            "Learn Jordan on the AI education platform: public, private, international and UNRWA. "
            "Smart lessons, textbooks and Tawjihi practice for every grade and subject."
        ),
        "seo_meta_description_ar": (
            "تعلّم مناهج الأردن على منصة التعليم بالذكاء الاصطناعي: الحكومي، الخاص، الدولي والأونروا. "
            "دروس ذكية وكتب وتمارين توجيهي لكل صف ومادة."
        ),
        "seo_keywords_en": (
            "AI education platform Jordan, education platform Jordan, "
            "Jordan curriculum AI, Tawjihi, UNRWA schools, online learning Jordan"
        ),
        "seo_keywords_ar": (
            "منصة التعليم بالذكاء الاصطناعي الأردن, منصة التعليم الأردن, "
            "مناهج الأردن, التوجيهي, مدارس الأونروا, تعليم أونلاين الأردن"
        ),
        "seo_description_en": _html(
            [
                "<h2>Jordan on the AI education platform</h2>",
                "<p>The <strong>AI education platform</strong> covers Jordan from kindergarten to secondary, including <strong>Tawjihi</strong>, with bilingual pages for every system, grade and subject.</p>",
                "<h2>Education systems</h2>",
                "<p>Study public schools, private national schools, international programmes, or <strong>UNRWA</strong> basic education — all inside one <strong>education platform</strong>.</p>",
                "<p>Official curriculum: "
                '<a href="https://moe.gov.jo/" rel="noopener noreferrer">Jordan Ministry of Education</a>.</p>',
            ]
        ),
        "seo_description_ar": _html(
            [
                "<h2>الأردن على منصة التعليم بالذكاء الاصطناعي</h2>",
                "<p>تغطي <strong>منصة التعليم بالذكاء الاصطناعي</strong> الأردن من رياض الأطفال حتى الثانوي بما فيه <strong>التوجيهي</strong>، مع صفحات ثنائية اللغة لكل نظام وصف ومادة.</p>",
                "<h2>أنظمة التعليم</h2>",
                "<p>ادرس التعليم الحكومي، أو الخاص، أو الدولي، أو <strong>مدارس الأونروا</strong> — كلها داخل <strong>منصة التعليم</strong> واحدة.</p>",
                "<p>المنهاج الرسمي: "
                '<a href="https://moe.gov.jo/" rel="noopener noreferrer">وزارة التربية والتعليم</a>.</p>',
            ]
        ),
        "slug_en": "jordan",
        "slug_ar": "الاردن",
    }


SYSTEMS: dict[str, list[dict[str, Any]]] = {
    "SA": [
        {
            "name": "Public Education",
            "name_ar": "التعليم العام",
            "slug_en": "public-education",
            "slug_ar": "التعليم-العام",
            "kind": "public",
            "seo_title_en": "Saudi Public Education | Ministry of Education Curriculum",
            "seo_title_ar": "التعليم العام في السعودية | منهج وزارة التعليم",
            "seo_meta_description_en": (
                "Saudi public education (Ministry of Education): kindergarten, elementary, intermediate "
                "and secondary grades with textbooks and exam-style practice."
            ),
            "seo_meta_description_ar": (
                "التعليم العام في السعودية وفق وزارة التعليم: رياض الأطفال، الابتدائي، المتوسط "
                "والثانوي مع كتب وتمارين شبيهة بالاختبارات."
            ),
            "seo_keywords_en": "Saudi public education, KSA Ministry of Education, elementary Saudi, secondary Saudi",
            "seo_keywords_ar": "التعليم العام السعودية, وزارة التعليم, ابتدائي السعودية, ثانوي السعودية",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "Saudi Ministry of Education",
            "link_label_ar": "وزارة التعليم السعودية",
        },
        {
            "name": "Private National Education",
            "name_ar": "التعليم الأهلي",
            "slug_en": "private-national",
            "slug_ar": "التعليم-الاهلي",
            "kind": "private",
            "seo_title_en": "Saudi Private National Schools | أهلي Curriculum Books",
            "seo_title_ar": "التعليم الأهلي في السعودية | كتب المنهج الوطني",
            "seo_meta_description_en": (
                "Private national (أهلي) schools in Saudi Arabia follow the ministry framework with extra "
                "support materials by grade."
            ),
            "seo_meta_description_ar": (
                "المدارس الأهلية في السعودية تتبع إطار وزارة التعليم مع مواد دعم إضافية لكل صف."
            ),
            "seo_keywords_en": "Saudi private schools, ahli schools KSA, national curriculum private Saudi",
            "seo_keywords_ar": "مدارس أهلية السعودية, التعليم الأهلي, منهج وطني أهلي",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "Ministry of Education private education",
            "link_label_ar": "التعليم الأهلي عبر وزارة التعليم",
        },
        {
            "name": "International Education",
            "name_ar": "التعليم الدولي",
            "slug_en": "international",
            "slug_ar": "التعليم-الدولي",
            "kind": "international",
            "seo_title_en": "International Schools in Saudi Arabia | British, American & IB",
            "seo_title_ar": "التعليم الدولي في السعودية | بريطاني وأمريكي وIB",
            "seo_meta_description_en": (
                "International education in Saudi Arabia: British, American and IB-style grades with "
                "bilingual resources and exam practice."
            ),
            "seo_meta_description_ar": (
                "التعليم الدولي في السعودية: المسارات البريطانية والأمريكية وIB مع موارد ثنائية اللغة وتمارين."
            ),
            "seo_keywords_en": "international schools Saudi Arabia, IB KSA, British curriculum Saudi, American curriculum Saudi",
            "seo_keywords_ar": "مدارس دولية السعودية, IB السعودية, منهج بريطاني, منهج أمريكي",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "Education in the Kingdom",
            "link_label_ar": "التعليم في المملكة",
        },
        {
            "name": "Quran Memorization",
            "name_ar": "تحفيظ القرآن الكريم",
            "slug_en": "quran-memorization",
            "slug_ar": "تحفيظ-القران",
            "kind": "quran",
            "seo_title_en": "Quran Memorization Schools in Saudi Arabia | Tahfeez Track",
            "seo_title_ar": "مدارس تحفيظ القرآن في السعودية | مسار التحفيظ",
            "seo_meta_description_en": (
                "Tahfeez / Quran memorization education in Saudi Arabia with ministry-aligned grades, "
                "Islamic studies and core school subjects."
            ),
            "seo_meta_description_ar": (
                "تعليم تحفيظ القرآن في السعودية مع صفوف متوافقة مع الوزارة، ودراسات إسلامية ومواد أساسية."
            ),
            "seo_keywords_en": "Tahfeez Saudi Arabia, Quran memorization schools KSA, Islamic education Saudi",
            "seo_keywords_ar": "تحفيظ القرآن السعودية, مدارس تحفيظ, تعليم إسلامي السعودية",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "Ministry of Education",
            "link_label_ar": "وزارة التعليم",
        },
    ],
    "JO": [
        {
            "name": "Public Education",
            "name_ar": "التعليم الحكومي",
            "slug_en": "public-education",
            "slug_ar": "التعليم-الحكومي",
            "kind": "public",
            "seo_title_en": "Jordan Public Education | Ministry of Education Curriculum",
            "seo_title_ar": "التعليم الحكومي في الأردن | منهج وزارة التربية",
            "seo_meta_description_en": (
                "Jordan public schools from kindergarten to Grade 12, including Tawjihi years, with "
                "textbooks and searchable lessons."
            ),
            "seo_meta_description_ar": (
                "المدارس الحكومية في الأردن من رياض الأطفال حتى الصف الثاني عشر بما فيها سنوات التوجيهي، "
                "مع كتب ودروس قابلة للبحث."
            ),
            "seo_keywords_en": "Jordan public schools, Ministry of Education Jordan, Tawjihi curriculum",
            "seo_keywords_ar": "مدارس حكومية الأردن, وزارة التربية, منهاج التوجيهي",
            "link": "https://moe.gov.jo/",
            "link_label_en": "Jordan Ministry of Education",
            "link_label_ar": "وزارة التربية والتعليم الأردنية",
        },
        {
            "name": "Private Education",
            "name_ar": "التعليم الخاص",
            "slug_en": "private-education",
            "slug_ar": "التعليم-الخاص",
            "kind": "private",
            "seo_title_en": "Jordan Private Schools | National Curriculum Support",
            "seo_title_ar": "التعليم الخاص في الأردن | دعم المنهاج الوطني",
            "seo_meta_description_en": (
                "Private schools in Jordan teaching the national curriculum with extra practice by grade."
            ),
            "seo_meta_description_ar": (
                "المدارس الخاصة في الأردن التي تدرّس المنهاج الوطني مع تمارين إضافية لكل صف."
            ),
            "seo_keywords_en": "Jordan private schools, private national curriculum Jordan",
            "seo_keywords_ar": "مدارس خاصة الأردن, منهاج وطني خاص",
            "link": "https://moe.gov.jo/",
            "link_label_en": "Ministry of Education",
            "link_label_ar": "وزارة التربية والتعليم",
        },
        {
            "name": "International Education",
            "name_ar": "التعليم الدولي",
            "slug_en": "international",
            "slug_ar": "التعليم-الدولي",
            "kind": "international",
            "seo_title_en": "International Schools in Jordan | IGCSE, SAT & IB",
            "seo_title_ar": "التعليم الدولي في الأردن | IGCSE وSAT وIB",
            "seo_meta_description_en": (
                "International education in Jordan: British, American and IB pathways with bilingual grade pages."
            ),
            "seo_meta_description_ar": (
                "التعليم الدولي في الأردن: المسارات البريطانية والأمريكية وIB مع صفحات صف ثنائية اللغة."
            ),
            "seo_keywords_en": "international schools Jordan, IGCSE Jordan, IB Amman, American curriculum Jordan",
            "seo_keywords_ar": "مدارس دولية الأردن, IGCSE الأردن, IB عمّان, منهج أمريكي الأردن",
            "link": "https://moe.gov.jo/",
            "link_label_en": "Education in Jordan",
            "link_label_ar": "التعليم في الأردن",
        },
        {
            "name": "UNRWA Education",
            "name_ar": "مدارس الأونروا",
            "slug_en": "unrwa",
            "slug_ar": "الاونروا",
            "kind": "unrwa",
            "seo_title_en": "UNRWA Schools in Jordan | Basic Education Grades 1–10",
            "seo_title_ar": "مدارس الأونروا في الأردن | التعليم الأساسي 1–10",
            "seo_meta_description_en": (
                "UNRWA basic education in Jordan for Grades 1–10 with Arabic-medium textbooks and exam practice."
            ),
            "seo_meta_description_ar": (
                "التعليم الأساسي في مدارس الأونروا بالأردن للصفوف 1–10 مع كتب عربية وتمارين اختبارات."
            ),
            "seo_keywords_en": "UNRWA Jordan schools, UNRWA curriculum, Palestinian education Jordan",
            "seo_keywords_ar": "مدارس الأونروا الأردن, منهاج الأونروا, تعليم أساسي أونروا",
            "link": "https://www.unrwa.org/what-we-do/education",
            "link_label_en": "UNRWA Education",
            "link_label_ar": "تعليم الأونروا",
        },
    ],
}


def system_seo(country_en: str, country_ar: str, system: dict[str, Any]) -> dict[str, str]:
    s_en, s_ar = system["name"], system["name_ar"]
    desc_en, desc_ar = (
        _html(
            [
                f"<h2>{s_en} in {country_en} | AI education platform</h2>",
                f"<p>Study <strong>{s_en}</strong> on the <strong>AI education platform</strong> for {country_en}. "
                "Open any grade to get textbooks, smart lesson search and exam practice.</p>",
                "<h2>How this education platform helps</h2>",
                f"<p>Pages are bilingual. Students and parents can search {s_en.lower()} content by grade and subject without leaving the platform.</p>",
                f'<p>Official reference: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_en"]}</a>.</p>',
            ]
        ),
        _html(
            [
                f"<h2>{s_ar} في {country_ar} | منصة التعليم بالذكاء الاصطناعي</h2>",
                f"<p>ادرس <strong>{s_ar}</strong> على <strong>منصة التعليم بالذكاء الاصطناعي</strong> في {country_ar}. "
                "افتح أي صف لتحصل على الكتب والبحث الذكي في الدروس وتمارين الاختبارات.</p>",
                "<h2>كيف تساعدك منصة التعليم؟</h2>",
                f"<p>الصفحات بالعربية والإنجليزية. يمكن للطالب وولي الأمر البحث في محتوى {s_ar} حسب الصف والمادة دون مغادرة المنصة.</p>",
                f'<p>المرجع الرسمي: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_ar"]}</a>.</p>',
            ]
        ),
    )
    return {
        "seo_title_en": f"{s_en} {country_en} | AI Education Platform",
        "seo_title_ar": f"{s_ar} {country_ar} | منصة التعليم بالذكاء الاصطناعي",
        "seo_meta_description_en": (
            f"{s_en} in {country_en} on the AI education platform: grades, subjects, textbooks "
            "and smart practice in Arabic and English."
        ),
        "seo_meta_description_ar": (
            f"{s_ar} في {country_ar} على منصة التعليم بالذكاء الاصطناعي: صفوف ومواد وكتب "
            "وتمارين ذكية بالعربية والإنجليزية."
        ),
        "seo_keywords_en": (
            f"AI education platform {s_en} {country_en}, education platform {country_en}, "
            f"{s_en} {country_en}, {s_en} textbooks, online learning {s_en}"
        ),
        "seo_keywords_ar": (
            f"منصة التعليم بالذكاء الاصطناعي {s_ar} {country_ar}, منصة التعليم {country_ar}, "
            f"{s_ar} {country_ar}, كتب {s_ar}, تعليم أونلاين {s_ar}"
        ),
        "seo_description_en": desc_en,
        "seo_description_ar": desc_ar,
        "slug_en": slugify_en(system["slug_en"]),
        "slug_ar": slugify_ar(system["slug_ar"]),
    }


def sa_national_grades() -> list[dict[str, Any]]:
    grades = [
        {
            "name": "Kindergarten",
            "name_ar": "رياض الأطفال",
            "slug_en": "kindergarten",
            "slug_ar": "رياض-الاطفال",
            "sort_order": 0,
            "stage_en": "early years",
            "stage_ar": "مرحلة الطفولة المبكرة",
        }
    ]
    primary = [
        ("First Grade Primary", "الصف الأول الابتدائي", "grade-1-primary", "الاول-الابتدائي"),
        ("Second Grade Primary", "الصف الثاني الابتدائي", "grade-2-primary", "الثاني-الابتدائي"),
        ("Third Grade Primary", "الصف الثالث الابتدائي", "grade-3-primary", "الثالث-الابتدائي"),
        ("Fourth Grade Primary", "الصف الرابع الابتدائي", "grade-4-primary", "الرابع-الابتدائي"),
        ("Fifth Grade Primary", "الصف الخامس الابتدائي", "grade-5-primary", "الخامس-الابتدائي"),
        ("Sixth Grade Primary", "الصف السادس الابتدائي", "grade-6-primary", "السادس-الابتدائي"),
    ]
    for i, (en, ar, se, sa) in enumerate(primary, start=1):
        grades.append(
            {
                "name": en,
                "name_ar": ar,
                "slug_en": se,
                "slug_ar": sa,
                "sort_order": i,
                "stage_en": "primary",
                "stage_ar": "المرحلة الابتدائية",
            }
        )
    intermediate = [
        ("First Intermediate", "الصف الأول المتوسط", "grade-1-intermediate", "الاول-المتوسط"),
        ("Second Intermediate", "الصف الثاني المتوسط", "grade-2-intermediate", "الثاني-المتوسط"),
        ("Third Intermediate", "الصف الثالث المتوسط", "grade-3-intermediate", "الثالث-المتوسط"),
    ]
    for i, (en, ar, se, sa) in enumerate(intermediate, start=7):
        grades.append(
            {
                "name": en,
                "name_ar": ar,
                "slug_en": se,
                "slug_ar": sa,
                "sort_order": i,
                "stage_en": "intermediate",
                "stage_ar": "المرحلة المتوسطة",
            }
        )
    secondary = [
        ("First Secondary", "الصف الأول الثانوي", "grade-1-secondary", "الاول-الثانوي"),
        ("Second Secondary", "الصف الثاني الثانوي", "grade-2-secondary", "الثاني-الثانوي"),
        ("Third Secondary", "الصف الثالث الثانوي", "grade-3-secondary", "الثالث-الثانوي"),
    ]
    for i, (en, ar, se, sa) in enumerate(secondary, start=10):
        grades.append(
            {
                "name": en,
                "name_ar": ar,
                "slug_en": se,
                "slug_ar": sa,
                "sort_order": i,
                "stage_en": "secondary",
                "stage_ar": "المرحلة الثانوية",
            }
        )
    return grades


def jo_national_grades(*, include_kg: bool = True, max_grade: int = 12) -> list[dict[str, Any]]:
    grades: list[dict[str, Any]] = []
    if include_kg:
        grades.append(
            {
                "name": "Kindergarten",
                "name_ar": "رياض الأطفال",
                "slug_en": "kindergarten",
                "slug_ar": "رياض-الاطفال",
                "sort_order": 0,
                "stage_en": "early years",
                "stage_ar": "رياض الأطفال",
            }
        )
    ar_ordinals = {
        1: "الأول",
        2: "الثاني",
        3: "الثالث",
        4: "الرابع",
        5: "الخامس",
        6: "السادس",
        7: "السابع",
        8: "الثامن",
        9: "التاسع",
        10: "العاشر",
        11: "الحادي عشر",
        12: "الثاني عشر",
    }
    for n in range(1, max_grade + 1):
        if n <= 6:
            stage_en, stage_ar = "basic (lower)", "الأساسي الدنيا"
        elif n <= 10:
            stage_en, stage_ar = "basic (upper)", "الأساسي العليا"
        else:
            stage_en, stage_ar = "secondary / Tawjihi", "الثانوي / التوجيهي"
        grades.append(
            {
                "name": f"Grade {n}",
                "name_ar": f"الصف {ar_ordinals[n]}",
                "slug_en": f"grade-{n}",
                "slug_ar": f"الصف-{n}",
                "sort_order": n,
                "stage_en": stage_en,
                "stage_ar": stage_ar,
            }
        )
    return grades


def international_grades() -> list[dict[str, Any]]:
    grades = [
        {
            "name": "KG1",
            "name_ar": "KG1 التمهيدي",
            "slug_en": "kg1",
            "slug_ar": "تمهيدي-kg1",
            "sort_order": 0,
            "stage_en": "early years",
            "stage_ar": "السنوات الأولى",
        },
        {
            "name": "KG2",
            "name_ar": "KG2 الروضة",
            "slug_en": "kg2",
            "slug_ar": "روضة-kg2",
            "sort_order": 1,
            "stage_en": "early years",
            "stage_ar": "السنوات الأولى",
        },
    ]
    for n in range(1, 13):
        if n <= 5:
            stage_en, stage_ar = "elementary", "الابتدائي الدولي"
        elif n <= 8:
            stage_en, stage_ar = "middle school", "المتوسط الدولي"
        else:
            stage_en, stage_ar = "high school", "الثانوي الدولي"
        grades.append(
            {
                "name": f"Grade {n}",
                "name_ar": f"Grade {n}",
                "slug_en": f"grade-{n}",
                "slug_ar": f"الصف-{n}",
                "sort_order": n + 1,
                "stage_en": stage_en,
                "stage_ar": stage_ar,
            }
        )
    return grades


def grades_for(code: str, kind: str) -> list[dict[str, Any]]:
    if kind == "international":
        return international_grades()
    if code == "SA":
        return sa_national_grades()
    if kind == "unrwa":
        return jo_national_grades(include_kg=False, max_grade=10)
    return jo_national_grades()


def grade_seo(
    *,
    country_en: str,
    country_ar: str,
    system: dict[str, Any],
    grade: dict[str, Any],
) -> dict[str, str]:
    g_en, g_ar = grade["name"], grade["name_ar"]
    s_en, s_ar = system["name"], system["name_ar"]
    return {
        "seo_title_en": f"{g_en} {country_en} | {s_en} | AI Education Platform",
        "seo_title_ar": f"{g_ar} {country_ar} | {s_ar} | منصة التعليم بالذكاء الاصطناعي",
        "seo_meta_description_en": (
            f"Learn {g_en} ({s_en}, {country_en}) on the AI education platform. "
            f"{grade['stage_en'].title()} textbooks, subjects and smart exam practice."
        ),
        "seo_meta_description_ar": (
            f"تعلّم {g_ar} ({s_ar}، {country_ar}) على منصة التعليم بالذكاء الاصطناعي. "
            f"كتب {grade['stage_ar']} ومواد وتمارين ذكية للاختبارات."
        ),
        "seo_keywords_en": (
            f"AI education platform {g_en} {country_en}, education platform {g_en}, "
            f"{g_en} {s_en}, {g_en} textbooks {country_en}, {grade['stage_en']} {country_en}"
        ),
        "seo_keywords_ar": (
            f"منصة التعليم بالذكاء الاصطناعي {g_ar} {country_ar}, منصة التعليم {g_ar}, "
            f"{g_ar} {s_ar}, كتب {g_ar} {country_ar}, {grade['stage_ar']}"
        ),
        "seo_description_en": _html(
            [
                f"<h2>{g_en} on the AI education platform — {country_en}</h2>",
                f"<p>This <strong>education platform</strong> page is for <strong>{g_en}</strong> in "
                f"<strong>{s_en}</strong> ({grade['stage_en']}). Use AI search to open subjects, textbooks and practice questions.</p>",
                "<h2>What to study</h2>",
                "<p>Typical subjects include <strong>Arabic, English, mathematics and science</strong>, plus Islamic or social studies when the track requires them.</p>",
                f'<p>Official guidance: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_en"]}</a>.</p>',
            ]
        ),
        "seo_description_ar": _html(
            [
                f"<h2>{g_ar} على منصة التعليم بالذكاء الاصطناعي — {country_ar}</h2>",
                f"<p>هذه الصفحة في <strong>منصة التعليم</strong> مخصصة لـ<strong>{g_ar}</strong> ضمن "
                f"<strong>{s_ar}</strong> ({grade['stage_ar']}). استخدم البحث بالذكاء الاصطناعي لفتح المواد والكتب وتمارين الاختبارات.</p>",
                "<h2>ماذا تدرس؟</h2>",
                "<p>تشمل المواد عادة <strong>العربية والإنجليزية والرياضيات والعلوم</strong>، إضافة إلى التربية الإسلامية أو الاجتماعية حسب المسار.</p>",
                f'<p>الإرشاد الرسمي: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_ar"]}</a>.</p>',
            ]
        ),
        "slug_en": grade["slug_en"],
        "slug_ar": grade["slug_ar"],
    }


SUBJECT_CORE = [
    ("Arabic", "اللغة العربية", "arabic", "اللغة-العربية", "reading, grammar and composition", "القراءة والقواعد والتعبير"),
    ("English", "اللغة الإنجليزية", "english", "اللغة-الانجليزية", "vocabulary, reading and writing", "المفردات والقراءة والكتابة"),
    ("Mathematics", "الرياضيات", "mathematics", "الرياضيات", "numbers, problem solving and exam drills", "الأعداد وحل المسائل وتمارين الاختبارات"),
    ("Science", "العلوم", "science", "العلوم", "life, earth and physical science", "علوم الحياة والأرض والفيزياء المبسطة"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "Quran, hadith and values", "القرآن والحديث والقيم"),
    ("Social Studies", "الدراسات الاجتماعية", "social-studies", "الدراسات-الاجتماعية", "history, geography and civics", "التاريخ والجغرافيا والتربية الوطنية"),
]

SUBJECT_EARLY = [
    ("Arabic", "اللغة العربية", "arabic", "اللغة-العربية", "letters, sounds and stories", "الحروف والأصوات والقصص"),
    ("English", "اللغة الإنجليزية", "english", "اللغة-الانجليزية", "phonics and simple vocabulary", "الصوتيات والمفردات البسيطة"),
    ("Mathematics", "الرياضيات", "mathematics", "الرياضيات", "counting, shapes and patterns", "العد والأشكال والأنماط"),
    ("Discovery Science", "العلوم الاستكشافية", "discovery-science", "العلوم-الاستكشافية", "senses, nature and simple experiments", "الحواس والطبيعة والتجارب البسيطة"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "short surahs and good manners", "قصار السور وحسن الخلق"),
]

SUBJECT_SECONDARY = [
    ("Arabic", "اللغة العربية", "arabic", "اللغة-العربية", "literature, rhetoric and exam essays", "الأدب والبلاغة ومقالات الاختبار"),
    ("English", "اللغة الإنجليزية", "english", "اللغة-الانجليزية", "comprehension, grammar and writing", "الاستيعاب والقواعد والكتابة"),
    ("Mathematics", "الرياضيات", "mathematics", "الرياضيات", "algebra, geometry and exam papers", "الجبر والهندسة ونماذج الاختبارات"),
    ("Physics", "الفيزياء", "physics", "الفيزياء", "mechanics, waves and electricity", "الميكانيكا والموجات والكهرباء"),
    ("Chemistry", "الكيمياء", "chemistry", "الكيمياء", "reactions, formulas and lab ideas", "التفاعلات والمعادلات وأفكار المختبر"),
    ("Biology", "الأحياء", "biology", "الاحياء", "cells, human body and ecology", "الخلايا وجسم الإنسان والبيئة"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "tafsir, fiqh and ethics", "التفسير والفقه والأخلاق"),
    ("Social Studies", "الدراسات الاجتماعية", "social-studies", "الدراسات-الاجتماعية", "history, geography and national studies", "التاريخ والجغرافيا والدراسات الوطنية"),
]

SUBJECT_INTERNATIONAL = [
    ("English", "English", "english", "الانجليزية", "language arts and literature", "فنون اللغة والأدب"),
    ("Mathematics", "Mathematics", "mathematics", "الرياضيات", "numeracy through exam-board style practice", "العدد وحل المسائل بأسلوب الاختبارات الدولية"),
    ("Science", "Science", "science", "العلوم", "combined or coordinated science", "العلوم المتكاملة"),
    ("Arabic", "اللغة العربية", "arabic", "العربية", "Arabic as a first or additional language", "العربية لغة أولى أو إضافية"),
    ("Social Studies", "Social Studies", "social-studies", "الدراسات-الاجتماعية", "humanities and global perspectives", "الإنسانيات والمنظور العالمي"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "faith studies where the school offers them", "التربية الإسلامية حيث تقدّمها المدرسة"),
]

SUBJECT_QURAN = [
    ("Quran Memorization", "القرآن الكريم", "quran", "القران-الكريم", "hifz, tajweed and revision", "الحفظ والتجويد والمراجعة"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "aqidah, fiqh and seerah", "العقيدة والفقه والسيرة"),
    ("Arabic", "اللغة العربية", "arabic", "اللغة-العربية", "nahw, sarf and comprehension", "النحو والصرف والاستيعاب"),
    ("English", "اللغة الإنجليزية", "english", "اللغة-الانجليزية", "school English alongside Tahfeez", "الإنجليزية المدرسية مع مسار التحفيظ"),
    ("Mathematics", "الرياضيات", "mathematics", "الرياضيات", "ministry-aligned math", "رياضيات وفق الوزارة"),
    ("Science", "العلوم", "science", "العلوم", "core science for Tahfeez students", "العلوم الأساسية لطلاب التحفيظ"),
]

SUBJECT_UNRWA = [
    ("Arabic", "اللغة العربية", "arabic", "اللغة-العربية", "UNRWA Arabic literacy and literature", "العربية في منهاج الأونروا"),
    ("English", "اللغة الإنجليزية", "english", "اللغة-الانجليزية", "UNRWA English communication", "الإنجليزية في منهاج الأونروا"),
    ("Mathematics", "الرياضيات", "mathematics", "الرياضيات", "UNRWA mathematics", "رياضيات الأونروا"),
    ("Science", "العلوم", "science", "العلوم", "UNRWA science", "علوم الأونروا"),
    ("Social Studies", "الدراسات الاجتماعية", "social-studies", "الدراسات-الاجتماعية", "history and civics", "التاريخ والتربية الوطنية"),
    ("Islamic Education", "التربية الإسلامية", "islamic-education", "التربية-الاسلامية", "Islamic education", "التربية الإسلامية"),
]


def subjects_for(kind: str, stage_en: str) -> list[tuple[str, str, str, str, str, str]]:
    if kind == "quran":
        return SUBJECT_QURAN
    if kind == "unrwa":
        return SUBJECT_UNRWA
    if kind == "international":
        if stage_en == "high school":
            return SUBJECT_SECONDARY
        return SUBJECT_INTERNATIONAL
    if stage_en in {"early years", "رياض الأطفال"}:
        return SUBJECT_EARLY
    if stage_en in {"secondary", "secondary / Tawjihi"}:
        return SUBJECT_SECONDARY
    return SUBJECT_CORE


def subject_seo(
    *,
    country_en: str,
    country_ar: str,
    system: dict[str, Any],
    grade: dict[str, Any],
    subject: tuple[str, str, str, str, str, str],
) -> dict[str, str]:
    name, name_ar, slug_en, slug_ar, angle_en, angle_ar = subject
    g_en, g_ar = grade["name"], grade["name_ar"]
    s_en, s_ar = system["name"], system["name_ar"]
    return {
        "seo_title_en": f"{name} {g_en} {country_en} | AI Education Platform",
        "seo_title_ar": f"{name_ar} {g_ar} {country_ar} | منصة التعليم بالذكاء الاصطناعي",
        "seo_meta_description_en": (
            f"Learn {name} for {g_en} ({s_en}, {country_en}) on the AI education platform. "
            f"Smart lessons and practice covering {angle_en}."
        )[:320],
        "seo_meta_description_ar": (
            f"تعلّم {name_ar} لـ{g_ar} ({s_ar}، {country_ar}) على منصة التعليم بالذكاء الاصطناعي. "
            f"دروس وتمارين ذكية تغطي {angle_ar}."
        )[:320],
        "seo_keywords_en": (
            f"AI education platform {name} {g_en} {country_en}, education platform {name}, "
            f"{name} {g_en} {s_en}, {name} textbooks {country_en}"
        ),
        "seo_keywords_ar": (
            f"منصة التعليم بالذكاء الاصطناعي {name_ar} {g_ar} {country_ar}, منصة التعليم {name_ar}, "
            f"{name_ar} {g_ar} {s_ar}, كتب {name_ar} {country_ar}"
        ),
        "seo_description_en": _html(
            [
                f"<h2>{name} — {g_en}, {country_en}</h2>",
                f"<p>Learn <strong>{name}</strong> for <strong>{g_en}</strong> on the <strong>AI education platform</strong> "
                f"({s_en}). Lessons and questions focus on {angle_en}.</p>",
                "<h2>Study on the education platform</h2>",
                "<p>Open the book, search a lesson, then practise. Share the page in English or Arabic with your family.</p>",
                f'<p>More about this track: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_en"]}</a>.</p>',
            ]
        ),
        "seo_description_ar": _html(
            [
                f"<h2>{name_ar} — {g_ar}، {country_ar}</h2>",
                f"<p>تعلّم <strong>{name_ar}</strong> لـ<strong>{g_ar}</strong> على <strong>منصة التعليم بالذكاء الاصطناعي</strong> "
                f"({s_ar}). تركّز الدروس والأسئلة على {angle_ar}.</p>",
                "<h2>ادرس عبر منصة التعليم</h2>",
                "<p>افتح الكتاب، ابحث عن الدرس، ثم تدرّب. شارك الصفحة بالعربية أو الإنجليزية مع الأسرة.</p>",
                f'<p>المزيد عن هذا المسار: <a href="{system["link"]}" rel="noopener noreferrer">{system["link_label_ar"]}</a>.</p>',
            ]
        ),
        "slug_en": slug_en,
        "slug_ar": slug_ar,
    }


def _match(items: list[dict[str, Any]], *, name: str | None = None, slug: str | None = None, code: str | None = None) -> dict[str, Any] | None:
    for item in items:
        if code and (item.get("code") or "").upper() == code.upper():
            return item
        seo = item.get("seo") or {}
        if slug and seo.get("slug_en") == slug:
            return item
        if name and item.get("name", "").strip().lower() == name.strip().lower():
            return item
        if name and (item.get("name_ar") or "").strip() == name.strip():
            return item
    return None


def upsert_country(store: JobStore, *, name: str, name_ar: str, code: str) -> dict[str, Any]:
    seo = country_seo(code)
    existing = _match(store.list_countries(), code=code, slug=seo["slug_en"], name=name)
    if existing:
        updated = store.update_country(
            existing["id"],
            name=name,
            name_ar=name_ar,
            code=code,
            seo=seo,
        )
        return updated or existing
    try:
        return store.create_country(name=name, name_ar=name_ar, code=code, seo=seo)
    except CatalogDuplicateError:
        existing = _match(store.list_countries(), name=name) or _match(store.list_countries(), name=name_ar)
        if not existing:
            raise
        return store.update_country(existing["id"], name=name, name_ar=name_ar, code=code, seo=seo) or existing


def upsert_system(store: JobStore, country: dict[str, Any], system: dict[str, Any]) -> dict[str, Any]:
    seo = system_seo(country["name"], country["name_ar"], system)
    existing = _match(
        store.list_education_systems(country_id=country["id"]),
        slug=seo["slug_en"],
        name=system["name"],
    )
    if existing:
        return (
            store.update_education_system(
                existing["id"],
                name=system["name"],
                name_ar=system["name_ar"],
                seo=seo,
            )
            or existing
        )
    try:
        return store.create_education_system(
            country_id=country["id"],
            name=system["name"],
            name_ar=system["name_ar"],
            seo=seo,
        )
    except CatalogDuplicateError:
        existing = _match(store.list_education_systems(country_id=country["id"]), name=system["name"])
        if not existing:
            raise
        return store.update_education_system(existing["id"], name=system["name"], name_ar=system["name_ar"], seo=seo) or existing


def upsert_grade(store: JobStore, country: dict[str, Any], system_row: dict[str, Any], system: dict[str, Any], grade: dict[str, Any]) -> dict[str, Any]:
    seo = grade_seo(
        country_en=country["name"],
        country_ar=country["name_ar"],
        system=system,
        grade=grade,
    )
    existing = _match(
        store.list_grades(education_system_id=system_row["id"]),
        slug=seo["slug_en"],
        name=grade["name"],
    )
    if existing:
        return (
            store.update_grade(
                existing["id"],
                name=grade["name"],
                name_ar=grade["name_ar"],
                sort_order=grade["sort_order"],
                seo=seo,
            )
            or existing
        )
    try:
        return store.create_grade(
            education_system_id=system_row["id"],
            name=grade["name"],
            name_ar=grade["name_ar"],
            sort_order=grade["sort_order"],
            seo=seo,
        )
    except CatalogDuplicateError:
        existing = _match(store.list_grades(education_system_id=system_row["id"]), name=grade["name"])
        if not existing:
            raise
        return (
            store.update_grade(
                existing["id"],
                name=grade["name"],
                name_ar=grade["name_ar"],
                sort_order=grade["sort_order"],
                seo=seo,
            )
            or existing
        )


def upsert_subject(
    store: JobStore,
    country: dict[str, Any],
    system_row: dict[str, Any],
    system: dict[str, Any],
    grade_row: dict[str, Any],
    grade: dict[str, Any],
    subject: tuple[str, str, str, str, str, str],
) -> dict[str, Any]:
    name, name_ar, slug_en, slug_ar, _a, _b = subject
    seo = subject_seo(
        country_en=country["name"],
        country_ar=country["name_ar"],
        system=system,
        grade=grade,
        subject=subject,
    )
    existing = _match(
        store.list_subjects(grade_id=grade_row["id"]),
        slug=seo["slug_en"],
        name=name,
    )
    if existing:
        return store.update_subject(existing["id"], name=name, name_ar=name_ar, seo=seo) or existing
    try:
        return store.create_subject(grade_id=grade_row["id"], name=name, name_ar=name_ar, seo=seo)
    except CatalogDuplicateError:
        existing = _match(store.list_subjects(grade_id=grade_row["id"]), name=name)
        if not existing:
            raise
        return store.update_subject(existing["id"], name=name, name_ar=name_ar, seo=seo) or existing


def seed(store: JobStore | None = None) -> dict[str, int]:
    own_store = store is None
    store = store or JobStore(settings.database_url)
    created = {"countries": 0, "systems": 0, "grades": 0, "subjects": 0}
    try:
        countries = [
            ("Saudi Arabia", "السعودية", "SA"),
            ("Jordan", "الأردن", "JO"),
        ]
        for name, name_ar, code in countries:
            country = upsert_country(store, name=name, name_ar=name_ar, code=code)
            created["countries"] += 1
            for system in SYSTEMS[code]:
                system_row = upsert_system(store, country, system)
                created["systems"] += 1
                for grade in grades_for(code, system["kind"]):
                    grade_row = upsert_grade(store, country, system_row, system, grade)
                    created["grades"] += 1
                    for subject in subjects_for(system["kind"], grade["stage_en"]):
                        upsert_subject(store, country, system_row, system, grade_row, grade, subject)
                        created["subjects"] += 1
        return created
    finally:
        if own_store:
            store.close()


if __name__ == "__main__":
    counts = seed()
    print(
        f"Seeded catalog: {counts['countries']} countries, "
        f"{counts['systems']} systems, {counts['grades']} grades, "
        f"{counts['subjects']} subjects (created or updated)."
    )
