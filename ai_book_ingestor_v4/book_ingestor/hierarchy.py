from __future__ import annotations

from dataclasses import dataclass, field
from .schemas import HierarchyContext, PageExtraction


@dataclass
class HierarchyResolver:
    current: HierarchyContext = field(default_factory=HierarchyContext)

    def apply_page(self, page: PageExtraction) -> HierarchyContext:
        # Only explicit titles can change state. This prevents hallucinated hierarchy.
        if page.explicit_unit_title:
            self.current.unit_title = page.explicit_unit_title.strip()
            self.current.chapter_title = None
            self.current.lesson_title = None
            self.current.section_title = None
        if page.explicit_chapter_title:
            self.current.chapter_title = page.explicit_chapter_title.strip()
            self.current.lesson_title = None
            self.current.section_title = None
        if page.explicit_lesson_title:
            self.current.lesson_title = page.explicit_lesson_title.strip()
            self.current.section_title = None
        if page.explicit_section_title:
            self.current.section_title = page.explicit_section_title.strip()
        return HierarchyContext.model_validate(self.current.model_dump())
