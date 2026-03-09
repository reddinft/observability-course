"""Markdown parser and course content loader."""
import os
import yaml
from pathlib import Path
from typing import Optional

COURSE_DIR = Path(__file__).parent.parent / "course"


def load_modules() -> list[dict]:
    """Load and parse all modules from course/ directory."""
    modules = []
    
    for module_dir in sorted(COURSE_DIR.glob("module-*")):
        if not module_dir.is_dir():
            continue
        
        meta_file = module_dir / "meta.yaml"
        if not meta_file.exists():
            continue
        
        with open(meta_file) as f:
            meta = yaml.safe_load(f)
        
        # Ensure lessons is a list
        if "lessons" not in meta:
            meta["lessons"] = []
        
        # Add module ID
        meta["id"] = module_dir.name
        modules.append(meta)
    
    return sorted(modules, key=lambda m: int(m.get("order", 999)))


def load_module(module_id: str) -> Optional[dict]:
    """Load a single module by ID."""
    module_dir = COURSE_DIR / module_id
    meta_file = module_dir / "meta.yaml"
    
    if not meta_file.exists():
        return None
    
    with open(meta_file) as f:
        meta = yaml.safe_load(f)
    
    meta["id"] = module_id
    if "lessons" not in meta:
        meta["lessons"] = []
    
    return meta


def load_lesson(module_id: str, lesson_slug: str) -> Optional[dict]:
    """Load a single lesson and its module context."""
    module = load_module(module_id)
    if not module:
        return None
    
    lesson_file = COURSE_DIR / module_id / f"{lesson_slug}.md"
    if not lesson_file.exists():
        return None
    
    with open(lesson_file) as f:
        content = f.read()
    
    # Find lesson metadata in lessons array
    lesson_meta = None
    for lesson in module.get("lessons", []):
        if lesson["slug"] == lesson_slug:
            lesson_meta = lesson
            break
    
    if not lesson_meta:
        lesson_meta = {"slug": lesson_slug, "title": "Untitled", "estimated_minutes": 5}
    
    return {
        "lesson_id": f"{module_id}::{lesson_slug}",
        "lesson": lesson_meta,
        "module": module,
        "content": content,
    }


def load_quiz(module_id: str) -> Optional[dict]:
    """Load quiz for a module."""
    quiz_file = COURSE_DIR / module_id / "quiz.yaml"
    if not quiz_file.exists():
        return None
    
    with open(quiz_file) as f:
        quiz = yaml.safe_load(f)
    
    quiz["id"] = f"{module_id}::quiz"
    return quiz


def get_all_progress_ids() -> list[str]:
    """Return all possible lesson IDs for progress tracking."""
    ids = []
    for module in load_modules():
        for lesson in module.get("lessons", []):
            ids.append(f"{module['id']}::{lesson['slug']}")
    return ids
