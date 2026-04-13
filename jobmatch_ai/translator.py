import re
from typing import Dict, List

# Simple translation cache for common terms
COMMON_TRANSLATIONS = {
    "题目": "Question",
    "答案要点": "Answer Key Points",
    "难度": "Difficulty",
    "相关岗位": "Related Position",
    "标签": "Tags",
    "题目类型": "Question Type",
    "技术知识": "Technical Knowledge",
    "场景题": "Scenario Question",
    "行为题": "Behavioral Question",
}

class QuestionTranslator:
    def __init__(self):
        self.cache: Dict[tuple[str, str], str] = {}
        self.translator_name = None
        self.translator = None
        self.translator_cls = None
        self._init_translator()
    
    def _init_translator(self):
        """Initialize translator - prefer deep-translator, fallback to google-trans-new."""
        try:
            from deep_translator import GoogleTranslator
            self.translator_name = "deep_translator"
            self.translator_cls = GoogleTranslator
        except ImportError:
            try:
                from google_trans_new import google_translator
                self.translator_name = "google_trans_new"
                self.translator = google_translator()
            except ImportError:
                print("Warning: Translation library not available. Install 'deep-translator' or 'google-trans-new' for automatic translation.")
                self.translator_name = None
    
    def translate(self, text: str, target_language: str = "en") -> str:
        """Translate text to the target language."""
        if not text or self.translator_name is None:
            return text

        if self._should_skip_translation(text, target_language):
            return text
        
        cache_key = (text, target_language)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            if self.translator_name == "deep_translator":
                translator = self.translator_cls(source="auto", target=target_language)
                translated = translator.translate(text)
            elif self.translator_name == "google_trans_new":
                translated = self.translator.translate(text, lang_tgt=target_language)
            else:
                translated = text
        except Exception as e:
            print(f"Translation error ({target_language}): {e}")
            translated = text
        self.cache[cache_key] = translated
        return translated

    def _should_skip_translation(self, text: str, target_language: str) -> bool:
        if target_language.startswith("en"):
            return not bool(re.search(r"[\u4e00-\u9fff]", text))
        if target_language.startswith("zh"):
            return bool(re.search(r"[\u4e00-\u9fff]", text))
        return False
    
    def translate_question_dict(self, question: Dict, target_language: str = "en") -> Dict:
        """Translate question dictionary fields."""
        translated = {}
        for key, value in question.items():
            new_key = COMMON_TRANSLATIONS.get(key, key)
            if isinstance(value, str):
                translated_value = self.translate(value, target_language=target_language)
            else:
                translated_value = value
            translated[new_key] = translated_value
        return translated
    
    def translate_questions(self, questions: List[Dict], target_language: str = "en") -> List[Dict]:
        """Translate a list of question dictionaries."""
        return [self.translate_question_dict(q, target_language=target_language) for q in questions]


# Global translator instance
_translator = None

def get_translator() -> QuestionTranslator:
    global _translator
    if _translator is None:
        _translator = QuestionTranslator()
    return _translator

def translate_text(text: str, language: str = "en") -> str:
    """Translate text based on language setting."""
    if language == "en":
        return get_translator().translate(text, target_language="en")
    if language == "zh":
        return get_translator().translate(text, target_language="zh-CN")
    return text
