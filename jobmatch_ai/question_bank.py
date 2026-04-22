import os
import csv
import glob
from pathlib import Path
from typing import List, Dict, Optional
import random

ROOT = Path(__file__).resolve().parent.parent


def _resolve_dir(env_key: str, *candidates: Path) -> Path:
    """Resolve a directory path.

    Order:
    1) explicit env var (absolute or relative to ROOT)
    2) first existing candidate
    3) otherwise return the first candidate (for clearer error messages)
    """
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ROOT / p)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _candidate_bank_dirs(env_key: str, preferred: Path, fallback: Path) -> List[Path]:
    """Return candidate bank dirs in priority order.

    If env var is set, it becomes first priority, and we still keep preferred/fallback
    as secondary options (useful when some CSVs only exist in the legacy bank).
    """
    dirs: List[Path] = []
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        p = Path(raw)
        p = p if p.is_absolute() else (ROOT / p)
        dirs.append(p)
        for d in (preferred, fallback):
            if d not in dirs:
                dirs.append(d)
        return dirs

    if preferred.exists():
        dirs.append(preferred)
        if fallback.exists():
            dirs.append(fallback)
        return dirs

    dirs.append(fallback)
    return dirs


# Prefer knowledge-base question banks (题库), but keep legacy folders as fallback.
_FRONTEND_BANK_DIRS = _candidate_bank_dirs(
    "JOBMATCH_BANK_FRONTEND_DIR",
    ROOT / "知识库-前端" / "题库",
    ROOT / "questionBank1",
)
_UNITY_BANK_DIRS = _candidate_bank_dirs(
    "JOBMATCH_BANK_UNITY_DIR",
    ROOT / "知识库-游戏" / "题库",
    ROOT / "questionBank2",
)


def _bank_dirs_for_role(role: str) -> List[Path]:
    return _UNITY_BANK_DIRS if role == "unity" else _FRONTEND_BANK_DIRS


# Map tech stack keywords to (role, relative CSV path under the bank dir).
# NOTE: role here is the question-bank track, not the job title.
TECH_TO_QUESTIONS = {
    # Frontend
    "javascript": ("frontend", "1. JavaScript/1_JavaScript.csv"),
    "js": ("frontend", "1. JavaScript/1_JavaScript.csv"),
    "jsx": ("frontend", "1. JavaScript/1_JavaScript.csv"),
    "typescript": ("frontend", "9. TypeScript/9_TypeScript.csv"),
    "ts": ("frontend", "9. TypeScript/9_TypeScript.csv"),
    "react": ("frontend", "4. React/4_React.csv"),
    "vue": ("frontend", "5. Vue/5_Vue.csv"),
    "css": ("frontend", "2. CSS/2_CSS.csv"),
    "html": ("frontend", "3. HTML/3_HTML.csv"),
    "node.js": ("frontend", "8. Node.js/8_Node.js.csv"),
    "nodejs": ("frontend", "8. Node.js/8_Node.js.csv"),
    "node": ("frontend", "8. Node.js/8_Node.js.csv"),
    "algorithm": ("frontend", "6. 算法/6_算法.csv"),
    "algorithms": ("frontend", "6. 算法/6_算法.csv"),
    "network": ("frontend", "7. 计算机网络/7_计算机网络.csv"),
    "performance": ("frontend", "10. 性能优化/10_性能优化.csv"),
    "optimization": ("frontend", "10. 性能优化/10_性能优化.csv"),
    "security": ("frontend", "11. 前端安全/11_前端安全.csv"),
    "es6": ("frontend", "13. ES6/13_ES6.csv"),
    "design pattern": ("frontend", "15. 设计模式/15_设计模式.csv"),
    "engineering": ("frontend", "16. 工程化/16_工程化.csv"),
    "coding": ("frontend", "14. 编程题/14_编程题.csv"),
    "reactjs": ("frontend", "4. React/4_React.csv"),
    "vue2": ("frontend", "5. Vue/5_Vue.csv"),
    "vue3": ("frontend", "5. Vue/5_Vue.csv"),
    "front-end": ("frontend", "1. JavaScript/1_JavaScript.csv"),
    "frontend": ("frontend", "1. JavaScript/1_JavaScript.csv"),
    "前端": ("frontend", "1. JavaScript/1_JavaScript.csv"),

    # Game Dev / Unity
    "csharp": ("unity", "01_编程语言_CSharp/01_编程语言_CSharp.csv"),
    "c#": ("unity", "01_编程语言_CSharp/01_编程语言_CSharp.csv"),
    "cpp": ("unity", "02_编程语言_Cpp/02_编程语言_Cpp.csv"),
    "c++": ("unity", "02_编程语言_Cpp/02_编程语言_Cpp.csv"),
    "lua": ("unity", "03_脚本语言_Lua与热更新/03_脚本语言_Lua与热更新.csv"),
    "unity": ("unity", "04_Unity引擎_基础与组件/04_Unity引擎_基础与组件.csv"),
    "shader": ("unity", "08_渲染与着色器/08_渲染与着色器.csv"),
    "networking": ("unity", "09_网络与同步/09_网络与同步.csv"),
}

class QuestionBank:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.questions_cache: Dict[str, List[Dict]] = {}

    def _candidate_csv_paths(self, role: str, rel_csv: str) -> List[str]:
        paths: List[str] = []
        for bank_dir in _bank_dirs_for_role(role):
            paths.append(str(bank_dir / rel_csv))
        return paths

    def _load_first_available_csv(self, role: str, rel_csv: str) -> List[Dict]:
        for full_path in self._candidate_csv_paths(role, rel_csv):
            if not os.path.exists(full_path):
                continue
            questions = self.load_csv(full_path)
            if questions:
                return questions
        return []
    
    def load_csv(self, csv_path: str) -> List[Dict]:
        """Load questions from a CSV file."""
        if csv_path in self.questions_cache:
            return self.questions_cache[csv_path]
        
        full_path = os.path.join(self.base_path, csv_path)
        questions = []
        
        try:
            with open(full_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
                reader = csv.DictReader(f)
                for row in reader:
                    # Strip BOM from keys if present
                    cleaned_row = {}
                    for key, value in row.items():
                        cleaned_key = key.lstrip('\ufeff')
                        cleaned_row[cleaned_key] = value
                    questions.append(cleaned_row)
            self.questions_cache[csv_path] = questions
        except FileNotFoundError:
            print(f"Warning: Question bank file not found: {full_path}")
        
        return questions
    
    def get_questions_for_tech(self, tech: str, num_questions: int = 5) -> List[Dict]:
        """Get questions matching a technology keyword."""
        tech_lower = tech.lower().strip()
        
        # Look for direct match
        if tech_lower in TECH_TO_QUESTIONS:
            role, rel_csv = TECH_TO_QUESTIONS[tech_lower]
            questions = self._load_first_available_csv(role, rel_csv)
            return random.sample(questions, min(num_questions, len(questions)))
        
        # Look for partial match
        for key, (role, rel_csv) in TECH_TO_QUESTIONS.items():
            if key in tech_lower or tech_lower in key:
                questions = self._load_first_available_csv(role, rel_csv)
                return random.sample(questions, min(num_questions, len(questions)))
        
        return []
    
    def get_random_questions(self, num_questions: int = 10) -> List[Dict]:
        """Load a broad mix of questions when no specific tech stack is detected."""
        all_questions = []
        for role, rel_csv in sorted(set(TECH_TO_QUESTIONS.values())):
            all_questions.extend(self._load_first_available_csv(role, rel_csv))
        random.shuffle(all_questions)
        return all_questions[:num_questions]

    def get_questions_for_stack(self, tech_stack: List[str], num_questions: int = 10) -> List[Dict]:
        """Get questions for multiple technologies in the stack."""
        if not tech_stack:
            return self.get_random_questions(num_questions)

        all_questions = []
        per_tech = max(1, num_questions // len(tech_stack))
        for tech in tech_stack:
            questions = self.get_questions_for_tech(tech, per_tech)
            all_questions.extend(questions)

        # Shuffle and return
        random.shuffle(all_questions)
        return all_questions[:num_questions]
    
    def get_all_available_categories(self) -> List[str]:
        """Get all available question categories."""
        # Expose as strings for display/debugging.
        return sorted({f"{role}:{rel_csv}" for role, rel_csv in TECH_TO_QUESTIONS.values()})


def extract_tech_stack(resume_text: str, stack_summary: str, projects: List[str]) -> List[str]:
    """Extract technology stack from resume, stack summary, and projects."""
    tech_stack = set()
    
    text = f"{resume_text} {stack_summary} {' '.join(projects)}".lower()
    
    for tech_keyword in TECH_TO_QUESTIONS.keys():
        if tech_keyword in text:
            tech_stack.add(tech_keyword)
    
    return list(tech_stack)
