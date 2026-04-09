import os
import csv
import glob
from typing import List, Dict, Optional
import random

# Map tech stack keywords to question bank CSV files
TECH_TO_QUESTIONS = {
    # Frontend
    "javascript": "questionBank1/1. JavaScript/1_JavaScript.csv",
    "js": "questionBank1/1. JavaScript/1_JavaScript.csv",
    "jsx": "questionBank1/1. JavaScript/1_JavaScript.csv",
    "typescript": "questionBank1/9. TypeScript/9_TypeScript.csv",
    "ts": "questionBank1/9. TypeScript/9_TypeScript.csv",
    "react": "questionBank1/4. React/4_React.csv",
    "vue": "questionBank1/5. Vue/5_Vue.csv",
    "css": "questionBank1/2. CSS/2_CSS.csv",
    "html": "questionBank1/3. HTML/3_HTML.csv",
    "node.js": "questionBank1/8. Node.js/8_Node.js.csv",
    "nodejs": "questionBank1/8. Node.js/8_Node.js.csv",
    "node": "questionBank1/8. Node.js/8_Node.js.csv",
    "algorithm": "questionBank1/6. 算法/6_算法.csv",
    "algorithms": "questionBank1/6. 算法/6_算法.csv",
    "network": "questionBank1/7. 计算机网络/7_计算机网络.csv",
    "performance": "questionBank1/10. 性能优化/10_性能优化.csv",
    "optimization": "questionBank1/10. 性能优化/10_性能优化.csv",
    "security": "questionBank1/11. 前端安全/11_前端安全.csv",
    "es6": "questionBank1/13. ES6/13_ES6.csv",
    "design pattern": "questionBank1/15. 设计模式/15_设计模式.csv",
    "engineering": "questionBank1/16. 工程化/16_工程化.csv",
    "coding": "questionBank1/14. 编程题/14_编程题.csv",
    "reactjs": "questionBank1/4. React/4_React.csv",
    "vue2": "questionBank1/5. Vue/5_Vue.csv",
    "vue3": "questionBank1/5. Vue/5_Vue.csv",
    "front-end": "questionBank1/1. JavaScript/1_JavaScript.csv",
    "frontend": "questionBank1/1. JavaScript/1_JavaScript.csv",
    "前端": "questionBank1/1. JavaScript/1_JavaScript.csv",
    
    # Game Dev
    "csharp": "questionBank2/01_编程语言_CSharp/01_编程语言_CSharp.csv",
    "c#": "questionBank2/01_编程语言_CSharp/01_编程语言_CSharp.csv",
    "cpp": "questionBank2/02_编程语言_Cpp/02_编程语言_Cpp.csv",
    "c++": "questionBank2/02_编程语言_Cpp/02_编程语言_Cpp.csv",
    "lua": "questionBank2/03_脚本语言_Lua与热更新/03_脚本语言_Lua与热更新.csv",
    "unity": "questionBank2/04_Unity引擎_基础与组件/04_Unity引擎_基础与组件.csv",
    "shader": "questionBank2/08_渲染与着色器/08_渲染与着色器.csv",
    "networking": "questionBank2/09_网络与同步/09_网络与同步.csv",
}

class QuestionBank:
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        self.questions_cache: Dict[str, List[Dict]] = {}
    
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
            csv_path = TECH_TO_QUESTIONS[tech_lower]
            questions = self.load_csv(csv_path)
            return random.sample(questions, min(num_questions, len(questions)))
        
        # Look for partial match
        for key, csv_path in TECH_TO_QUESTIONS.items():
            if key in tech_lower or tech_lower in key:
                questions = self.load_csv(csv_path)
                return random.sample(questions, min(num_questions, len(questions)))
        
        return []
    
    def get_random_questions(self, num_questions: int = 10) -> List[Dict]:
        """Load a broad mix of questions when no specific tech stack is detected."""
        all_questions = []
        for csv_path in sorted(set(TECH_TO_QUESTIONS.values())):
            all_questions.extend(self.load_csv(csv_path))
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
        return sorted(list(set(TECH_TO_QUESTIONS.values())))


def extract_tech_stack(resume_text: str, stack_summary: str, projects: List[str]) -> List[str]:
    """Extract technology stack from resume, stack summary, and projects."""
    tech_stack = set()
    
    text = f"{resume_text} {stack_summary} {' '.join(projects)}".lower()
    
    for tech_keyword in TECH_TO_QUESTIONS.keys():
        if tech_keyword in text:
            tech_stack.add(tech_keyword)
    
    return list(tech_stack)
