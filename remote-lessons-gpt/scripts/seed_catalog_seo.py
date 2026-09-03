from __future__ import annotations

from typing import Any

from remote_lessons_gpt.api.catalog_seo import CatalogDuplicateError, slugify_ar, slugify_en
from remote_lessons_gpt.api.job_store import JobStore
from remote_lessons_gpt.config import settings


def _html(parts: list[str]) -> str:
    return "".join(parts)


def country_seo(code: str) -> dict[str, str]:
    del code
    return {
        "seo_title_en": "Saudi Arabia | AI Education Platform — Books, Grades & Subjects",
        "seo_title_ar": "السعودية | منصة التعليم بالذكاء الاصطناعي — كتب، صفوف ومواد",
        "seo_meta_description_en": (
            "Learn Saudi Arabia on the AI education platform: national, American international, "
            "British international and IB. Smart lessons, textbooks and exam practice for every grade."
        ),
        "seo_meta_description_ar": (
            "تعلّم مناهج السعودية على منصة التعليم بالذكاء الاصطناعي: النظام الوطني، النظام الدولي الامريكي، "
            "النظام الدولي البريطاني والبكالوريا الدولية. دروس ذكية وكتب وتمارين لكل صف ومادة."
        ),
        "seo_keywords_en": (
            "AI education platform Saudi Arabia, education platform KSA, "
            "Saudi national curriculum, American curriculum Saudi, British curriculum Saudi, "
            "IB Saudi Arabia, Saudi textbooks, Ministry of Education Saudi"
        ),
        "seo_keywords_ar": (
            "منصة التعليم بالذكاء الاصطناعي السعودية, منصة التعليم السعودية, "
            "النظام الوطني, النظام الدولي الامريكي, النظام الدولي البريطاني, البكالوريا الدولية, "
            "كتب مدرسية سعودية, وزارة التعليم"
        ),
        "seo_description_en": _html(
            [
                "<h2>Saudi Arabia on the AI education platform</h2>",
                "<p>This <strong>education platform</strong> uses <strong>artificial intelligence</strong> to organise Saudi Arabia learning by system, grade and subject — so students find the right book and practice faster.</p>",
                "<h2>What you can study</h2>",
                "<p>Open the <strong>national system</strong>, American international, British international, or International Baccalaureate. Each page is written for search in English and Arabic.</p>",
                "<p>Official ministry updates: "
                '<a href="https://www.moe.gov.sa/" rel="noopener noreferrer">Saudi Ministry of Education</a>.</p>',
            ]
        ),
        "seo_description_ar": _html(
            [
                "<h2>السعودية على منصة التعليم بالذكاء الاصطناعي</h2>",
                "<p>هذه <strong>منصة التعليم</strong> تعتمد <strong>الذكاء الاصطناعي</strong> لتنظيم مناهج السعودية حسب النظام والصف والمادة، ليصل الطالب إلى الكتاب والتمرين المناسب بسرعة.</p>",
                "<h2>ماذا ستدرس؟</h2>",
                "<p>تصفّح <strong>النظام الوطني</strong>، والنظام الدولي الامريكي، والنظام الدولي البريطاني، والبكالوريا الدولية. كل صفحة مُحسَّنة للبحث بالعربية والإنجليزية.</p>",
                "<p>التحديثات الرسمية: "
                '<a href="https://www.moe.gov.sa/" rel="noopener noreferrer">وزارة التعليم السعودية</a>.</p>',
            ]
        ),
        "slug_en": "saudi-arabia",
        "slug_ar": "السعودية",
    }


SYSTEMS: dict[str, list[dict[str, Any]]] = {
    "SA": [
        {
            "name": "National System",
            "name_ar": "النظام الوطني",
            "slug_en": "national-system",
            "slug_ar": "النظام-الوطني",
            "kind": "national",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "Saudi Ministry of Education",
            "link_label_ar": "وزارة التعليم السعودية",
        },
        {
            "name": "American International System",
            "name_ar": "النظام الدولي الامريكي",
            "slug_en": "american-international",
            "slug_ar": "النظام-الدولي-الامريكي",
            "kind": "american",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "International education in Saudi Arabia",
            "link_label_ar": "التعليم الدولي في السعودية",
        },
        {
            "name": "British International System",
            "name_ar": "النظام الدولي البريطاني",
            "slug_en": "british-international",
            "slug_ar": "النظام-الدولي-البريطاني",
            "kind": "british",
            "link": "https://www.moe.gov.sa/",
            "link_label_en": "British curriculum in Saudi Arabia",
            "link_label_ar": "المنهج البريطاني في السعودية",
        },
        {
            "name": "International Baccalaureate",
            "name_ar": "البكالوريا الدولية",
            "slug_en": "international-baccalaureate",
            "slug_ar": "البكالوريا-الدولية",
            "kind": "ib",
            "link": "https://www.ibo.org/",
            "link_label_en": "International Baccalaureate",
            "link_label_ar": "البكالوريا الدولية",
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


def american_grades() -> list[dict[str, Any]]:
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
            stage_en, stage_ar = "elementary", "الابتدائي الامريكي"
        elif n <= 8:
            stage_en, stage_ar = "middle school", "المتوسط الامريكي"
        else:
            stage_en, stage_ar = "high school", "الثانوي الامريكي"
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


def british_grades() -> list[dict[str, Any]]:
    grades = [
        {
            "name": "FS1",
            "name_ar": "FS1 التمهيدي",
            "slug_en": "fs1",
            "slug_ar": "تمهيدي-fs1",
            "sort_order": 0,
            "stage_en": "early years",
            "stage_ar": "السنوات الأولى",
        },
        {
            "name": "FS2",
            "name_ar": "FS2 الروضة",
            "slug_en": "fs2",
            "slug_ar": "روضة-fs2",
            "sort_order": 1,
            "stage_en": "early years",
            "stage_ar": "السنوات الأولى",
        },
    ]
    for n in range(1, 14):
        if n <= 6:
            stage_en, stage_ar = "primary", "الابتدائي البريطاني"
        elif n <= 11:
            stage_en, stage_ar = "secondary", "الثانوي البريطاني"
        else:
            stage_en, stage_ar = "sixth form", "المرحلة السادسة"
        grades.append(
            {
                "name": f"Year {n}",
                "name_ar": f"Year {n}",
                "slug_en": f"year-{n}",
                "slug_ar": f"السنة-{n}",
                "sort_order": n + 1,
                "stage_en": stage_en,
                "stage_ar": stage_ar,
            }
        )
    return grades


def ib_grades() -> list[dict[str, Any]]:
    grades = [
        {
            "name": "Kindergarten",
            "name_ar": "رياض الأطفال",
            "slug_en": "kindergarten",
            "slug_ar": "رياض-الاطفال",
            "sort_order": 0,
            "stage_en": "early years",
            "stage_ar": "السنوات الأولى",
        }
    ]
    for n in range(1, 13):
        if n <= 5:
            stage_en, stage_ar = "pyp", "برنامج السنوات الابتدائية"
        elif n <= 10:
            stage_en, stage_ar = "myp", "البرنامج المتوسط"
        else:
            stage_en, stage_ar = "dp", "برنامج الدبلوما"
        grades.append(
            {
                "name": f"Grade {n}",
                "name_ar": f"Grade {n}",
                "slug_en": f"grade-{n}",
                "slug_ar": f"الصف-{n}",
                "sort_order": n,
                "stage_en": stage_en,
                "stage_ar": stage_ar,
            }
        )
    return grades


def grades_for(kind: str) -> list[dict[str, Any]]:
    if kind == "american":
        return american_grades()
    if kind == "british":
        return british_grades()
    if kind == "ib":
        return ib_grades()
    return sa_national_grades()


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


def subjects_for(kind: str, stage_en: str) -> list[tuple[str, str, str, str, str, str]]:
    if kind == "national":
        if stage_en == "early years":
            return SUBJECT_EARLY
        if stage_en == "secondary":
            return SUBJECT_SECONDARY
        return SUBJECT_CORE
    if stage_en in {"early years"}:
        return SUBJECT_EARLY
    if stage_en in {"high school", "secondary", "sixth form", "dp"}:
        return SUBJECT_SECONDARY
    if stage_en in {"elementary", "middle school", "primary", "pyp", "myp"}:
        return SUBJECT_INTERNATIONAL
    return SUBJECT_INTERNATIONAL


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
    ) or _match(
        store.list_education_systems(country_id=country["id"]),
        name=system["name_ar"],
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


def purge_other_catalog(store: JobStore) -> None:
    keep_en = {item["name"].strip().lower() for item in SYSTEMS["SA"]}
    keep_ar = {item["name_ar"].strip() for item in SYSTEMS["SA"]}
    for country in store.list_countries(active_only=True):
        code = (country.get("code") or "").upper()
        if code != "SA":
            store.deactivate_country(country["id"])
            continue
        for system in store.list_education_systems(country_id=country["id"], active_only=True):
            name = (system.get("name") or "").strip().lower()
            name_ar = (system.get("name_ar") or "").strip()
            if name not in keep_en and name_ar not in keep_ar:
                store.deactivate_education_system(system["id"])


def seed(store: JobStore | None = None) -> dict[str, int]:
    own_store = store is None
    store = store or JobStore(settings.database_url)
    created = {"countries": 0, "systems": 0, "grades": 0, "subjects": 0}
    try:
        purge_other_catalog(store)
        country = upsert_country(store, name="Saudi Arabia", name_ar="السعودية", code="SA")
        created["countries"] += 1
        for system in SYSTEMS["SA"]:
            system_row = upsert_system(store, country, system)
            created["systems"] += 1
            for grade in grades_for(system["kind"]):
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
