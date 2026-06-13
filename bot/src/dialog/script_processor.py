# -*- coding: utf-8 -*-
"""
Lesson Script Processor — обработчик сценариев урока.

Расширяет базовый формат сценария новыми возможностями:
  1. Автоматическая генерация команд для доски на основе текста
  2. Определение speak_only vs write_and_speak для каждого шага
  3. Маркировка сложности шагов
  4. Определение prerequisite шагов
  5. Автоматическое добавление аналогий и примеров
  6. Генерация проверочных вопросов если не заданы

Формат расширенного сценария:
[
    {
        "step": 1,
        "text": "Алканы — это предельные углеводороды...",
        "question": "Можешь назвать формулу метана?",
        "board_commands": [{"type": "show_formula", "smiles": "C", "label": "Метан"}],
        "listen": true,
        "speak_only": false,
        "difficulty": "normal",
        "prerequisite_steps": [],
        "common_mistakes": ["путают с алкенами"],
        "analogies": ["как цепочка из кирпичиков"],
        "key_concepts": ["алканы", "углеводороды", "одинарные связи"]
    },
    ...
]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Типы данных
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class LessonStep:
    """Расширенный шаг урока."""
    step: int
    text: str
    question: Optional[str] = None
    board_commands: list[dict] = field(default_factory=list)
    listen: bool = True
    speak_only: bool = False
    difficulty: str = "normal"  # easy / normal / hard
    prerequisite_steps: list[int] = field(default_factory=list)
    common_mistakes: list[str] = field(default_factory=list)
    analogies: list[str] = field(default_factory=list)
    key_concepts: list[str] = field(default_factory=list)
    estimated_duration_sec: int = 60

    @classmethod
    def from_dict(cls, data: dict) -> "LessonStep":
        """Создать шаг из словаря."""
        return cls(
            step=data.get("step", 0),
            text=data.get("text", ""),
            question=data.get("question"),
            board_commands=data.get("board_commands", []),
            listen=data.get("listen", True),
            speak_only=data.get("speak_only", False),
            difficulty=data.get("difficulty", "normal"),
            prerequisite_steps=data.get("prerequisite_steps", []),
            common_mistakes=data.get("common_mistakes", []),
            analogies=data.get("analogies", []),
            key_concepts=data.get("key_concepts", []),
            estimated_duration_sec=data.get("estimated_duration_sec", 60),
        )

    def to_dict(self) -> dict:
        """Сериализовать шаг в словарь."""
        return {
            "step": self.step,
            "text": self.text,
            "question": self.question,
            "board_commands": self.board_commands,
            "listen": self.listen,
            "speak_only": self.speak_only,
            "difficulty": self.difficulty,
            "prerequisite_steps": self.prerequisite_steps,
            "common_mistakes": self.common_mistakes,
            "analogies": self.analogies,
            "key_concepts": self.key_concepts,
            "estimated_duration_sec": self.estimated_duration_sec,
        }


@dataclass
class ProcessedScript:
    """Обработанный сценарий урока."""
    steps: list[LessonStep]
    total_duration_sec: int = 0
    difficulty_distribution: dict[str, int] = field(default_factory=dict)
    key_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Сериализовать сценарий."""
        return {
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_sec": self.total_duration_sec,
            "difficulty_distribution": self.difficulty_distribution,
            "key_concepts": self.key_concepts,
        }


# ──────────────────────────────────────────────────────────────────────────
# Паттерны для автогенерации команд доски
# ──────────────────────────────────────────────────────────────────────────

# Паттерны для определения типов контента
FORMULA_PATTERNS = [
    r"(?:формула|уравнение|молекул)[а-я]*\s+(?:[A-Z][A-Za-z0-9+\-=()]+)",
    r"[A-Z][a-z]?\d*[A-Z]?\d*[A-Z]?\d*",  # химические формулы
    r"(?:CH[234]|C2H[2456]|H2O|CO2|NaCl|H2SO4|HCl|NaOH)",
]

EQUATION_PATTERNS = [
    r"(?:реакц\w+\s+(?:происходит|идёт|осуществляется))",
    r"[A-Z][A-Za-z0-9]*\s*[\+\-→=]\s*[A-Z][A-Za-z0-9]*",
    r"(?:->|→|=)",
]

DEFINITION_PATTERNS = [
    r"(?:это\s+(?:называется|означает|представляет собой))",
    r"(?:определение|термин|понятие)",
    r"^\w+\s+—\s+",  # "Термин — определение"
]

# Паттерны для определения speak_only
SPEAK_ONLY_PATTERNS = [
    r"(?:представь|вообрази|подумай|вспомни)",
    r"(?:давай|рассмотрим|обсудим)",
    r"(?:хорошо|отлично|замечательно|молодец)",
    r"(?:понятно|ясно|ясно)",
]


# ──────────────────────────────────────────────────────────────────────────
# Обработчик сценариев
# ──────────────────────────────────────────────────────────────────────────

class LessonScriptProcessor:
    """
    Обрабатывает сценарий урока и расширяет его:
    - Автогенерация команд для доски
    - Определение speak_only
    - Определение сложности
    - Добавление аналогий
    - Генерация проверочных вопросов
    """

    def __init__(self, topic_name: str = "", topic_description: str = ""):
        self._topic_name = topic_name
        self._topic_description = topic_description

    def process(self, raw_script: list[dict]) -> ProcessedScript:
        """
        Обработать сырой сценарий и вернуть расширенную версию.
        """
        steps = []
        all_concepts = []
        difficulty_counts = {"easy": 0, "normal": 0, "hard": 0}
        total_duration = 0

        for i, raw_step in enumerate(raw_script):
            step = self._process_step(raw_step, i + 1)
            steps.append(step)

            # Собираем статистику
            difficulty_counts[step.difficulty] = difficulty_counts.get(step.difficulty, 0) + 1
            total_duration += step.estimated_duration_sec
            all_concepts.extend(step.key_concepts)

        # Убираем дубликаты концепций
        unique_concepts = list(dict.fromkeys(all_concepts))

        return ProcessedScript(
            steps=steps,
            total_duration_sec=total_duration,
            difficulty_distribution=difficulty_counts,
            key_concepts=unique_concepts,
        )

    def _process_step(self, raw_step: dict, step_number: int) -> LessonStep:
        """Обработать один шаг сценария."""
        text = raw_step.get("text", "")
        question = raw_step.get("question")
        board_commands = raw_step.get("board_commands", [])

        # 1. Определяем speak_only
        speak_only = raw_step.get("speak_only", False)
        if not speak_only:
            speak_only = self._is_speak_only(text)

        # 2. Автогенерация команд доски если не заданы
        if not board_commands and not speak_only:
            board_commands = self._generate_board_commands(text, step_number)

        # 3. Определяем сложность
        difficulty = raw_step.get("difficulty", "normal")
        if difficulty == "normal":
            difficulty = self._estimate_difficulty(text, question)

        # 4. Определяем prerequisite шаги
        prerequisite_steps = raw_step.get("prerequisite_steps", [])

        # 5. Добавляем аналогии если не заданы
        analogies = raw_step.get("analogies", [])
        if not analogies:
            analogies = self._suggest_analogies(text)

        # 6. Извлекаем ключевые концепции
        key_concepts = raw_step.get("key_concepts", [])
        if not key_concepts:
            key_concepts = self._extract_key_concepts(text)

        # 7. Генерируем проверочный вопрос если не задан
        if not question and raw_step.get("listen", True):
            question = self._generate_check_question(text, key_concepts)

        # 8. Оцениваем длительность
        estimated_duration = raw_step.get("estimated_duration_sec", 0)
        if not estimated_duration:
            estimated_duration = self._estimate_duration(text, question)

        return LessonStep(
            step=step_number,
            text=text,
            question=question,
            board_commands=board_commands,
            listen=raw_step.get("listen", True),
            speak_only=speak_only,
            difficulty=difficulty,
            prerequisite_steps=prerequisite_steps,
            common_mistakes=raw_step.get("common_mistakes", []),
            analogies=analogies,
            key_concepts=key_concepts,
            estimated_duration_sec=estimated_duration,
        )

    def _is_speak_only(self, text: str) -> bool:
        """Определить, нужно ли только говорить (без доски)."""
        text_lower = text.lower()

        # Проверяем паттерны speak_only
        for pattern in SPEAK_ONLY_PATTERNS:
            if re.search(pattern, text_lower):
                return True

        # Если нет химических формул или уравнений — speak_only
        has_formula = any(re.search(p, text) for p in FORMULA_PATTERNS)
        has_equation = any(re.search(p, text) for p in EQUATION_PATTERNS)

        if not has_formula and not has_equation:
            # Проверяем, есть ли определения или ключевые термины
            has_definition = any(re.search(p, text_lower) for p in DEFINITION_PATTERNS)
            if not has_definition:
                return True

        return False

    def _generate_board_commands(self, text: str, step_number: int) -> list[dict]:
        """Автогенерировать команды для доски на основе текста."""
        commands = []
        text_lower = text.lower()

        # Проверяем на наличие формул
        formula_match = re.search(r"[A-Z][a-z]?\d*[A-Z]?\d*[A-Z]?\d*", text)
        if formula_match:
            formula = formula_match.group()
            # Пытаемся найти SMILES-эквивалент
            smiles = self._formula_to_smiles(formula)
            if smiles:
                commands.append({
                    "type": "show_formula",
                    "smiles": smiles,
                    "label": formula,
                    "x": 300,
                    "y": 200,
                })

        # Проверяем на наличие уравнений реакций
        equation_match = re.search(
            r"[A-Z][A-Za-z0-9]*\s*[\+\-→=]\s*[A-Z][A-Za-z0-9]*",
            text
        )
        if equation_match:
            equation = equation_match.group()
            commands.append({
                "type": "show_equation",
                "equation": equation,
                "label": f"Реакция (шаг {step_number})",
                "x": 200,
                "y": 150,
            })

        # Проверяем на определения
        definition_match = re.search(r"(\w+)\s+—\s+(.+?)(?:\.|$)", text)
        if definition_match:
            term = definition_match.group(1)
            definition = definition_match.group(2)
            commands.append({
                "type": "draw_text",
                "text": f"{term} — {definition[:100]}",
                "x": 100,
                "y": 50,
            })

        return commands

    def _formula_to_smiles(self, formula: str) -> Optional[str]:
        """Попытаться конвертировать формулу в SMILES-нотацию."""
        # Простые маппинг для базовых формул
        simple_map = {
            "CH4": "C",
            "C2H6": "CC",
            "C3H8": "CCC",
            "C4H10": "CCCC",
            "C2H4": "C=C",
            "C2H2": "C#C",
            "CH3OH": "CO",
            "C2H5OH": "CCO",
            "CH3COOH": "CC(=O)O",
            "H2O": "O",
            "CO2": "O=C=O",
            "HCl": "Cl",
            "H2SO4": "OS(=O)(=O)O",
            "NaOH": "[Na+].[OH-]",
            "NaCl": "[Na+].[Cl-]",
        }
        return simple_map.get(formula)

    def _estimate_difficulty(self, text: str, question: Optional[str]) -> str:
        """Оценить сложность шага."""
        text_lower = text.lower()

        # Простые маркеры сложности
        easy_markers = [
            "простой", "легкий", "базовый", "основной",
            "первый", "введение", "начнём",
        ]
        hard_markers = [
            "сложный", "продвинутый", "каверзный",
            "необычный", "исключение", "особый",
        ]

        for marker in easy_markers:
            if marker in text_lower:
                return "easy"

        for marker in hard_markers:
            if marker in text_lower:
                return "hard"

        # Оцениваем по длине и сложности текста
        word_count = len(text.split())
        if word_count < 20:
            return "easy"
        elif word_count > 60:
            return "hard"

        return "normal"

    def _suggest_analogies(self, text: str) -> list[str]:
        """Предложить аналогии для объяснения."""
        text_lower = text.lower()
        analogies = []

        # Аналогии для типичных химических концепций
        analogy_map = {
            "молекула": "как конструктор LEGO — из отдельных деталей",
            "атом": "как крошечный солнечная система — ядро и электроны",
            "связь": "как руки, которые держат атомы вместе",
            "реакция": "как танец — атомы меняются партнёрами",
            "раствор": "как сахар в чае — растворяется и исчезает",
            "кислота": "как лимон — кислая на вкус",
            "основание": "как мыло — скользкое на ощупь",
            "катион": "как позитивный друг — отдаёт электроны",
            "анион": "как негативный друг — принимает электроны",
            "валентность": "как количество рук у атома — сколько связей может образовать",
            "окисление": "как ржавчина — атом отдаёт электроны",
            "восстановление": "как противоположность ржавчины — атом принимает электроны",
        }

        for key, analogy in analogy_map.items():
            if key in text_lower:
                analogies.append(analogy)

        return analogies[:2]  # максимум 2 аналогии на шаг

    def _extract_key_concepts(self, text: str) -> list[str]:
        """Извлечь ключевые концепции из текста."""
        concepts = []
        text_lower = text.lower()

        # Известные химические концепции
        known_concepts = [
            "алканы", "алкены", "алкадиены", "алкины",
            "ароматические", "спирты", "альдегиды", "кетоны",
            "карбоновые кислоты", "эфиры", "амины",
            "окисление", "восстановление", "замещение",
            "добавление", "конденсация", "полимеризация",
            "изомерия", "стереоизомерия", "оптическая изомерия",
            "валентность", "окислительное состояние",
            "периодическая таблица", "группа", "период",
            "ионная связь", "ковалентная связь", "металлическая связь",
            "раствор", "концентрация", "молярность",
            "pH", "кислотность", "щёлочность",
        ]

        for concept in known_concepts:
            if concept in text_lower:
                concepts.append(concept)

        # Извлекаем термины в скобках или после "—"
        bracket_terms = re.findall(r"\(([^)]+)\)", text)
        for term in bracket_terms:
            if len(term.split()) <= 3:  # короткие термины
                concepts.append(term.strip())

        dash_terms = re.findall(r"(\w+)\s+—\s+", text)
        for term in dash_terms:
            if len(term) <= 20:
                concepts.append(term.strip())

        return list(dict.fromkeys(concepts))[:5]  # максимум 5, без дубликатов

    def _generate_check_question(self, text: str, key_concepts: list[str]) -> Optional[str]:
        """Сгенерировать проверочный вопрос если не задан."""
        if not key_concepts:
            return None

        # Типичные шаблоны проверочных вопросов
        templates = [
            "Можешь повторить, что такое {concept}?",
            "Как ты думаешь, зачем нужно {concept}?",
            "Можешь привести пример {concept}?",
            "Объясни своими словами, что такое {concept}.",
        ]

        # Выбираем случайный шаблон
        import random
        template = random.choice(templates)
        concept = key_concepts[0]

        return template.format(concept=concept)

    def _estimate_duration(self, text: str, question: Optional[str]) -> int:
        """Оценить длительность шага в секундах."""
        # Базовая длительность: ~150 слов в минуту для объяснения
        word_count = len(text.split())
        base_duration = int(word_count / 150 * 60)

        # Добавляем время на вопрос и ответ
        if question:
            base_duration += 15  # время на вопрос
            base_duration += 12  # время на ответ ученика

        # Добавляем время на доску
        base_duration += 5

        return max(30, base_duration)  # минимум 30 секунд


# ──────────────────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────────────────

def process_lesson_script(
    raw_script: list[dict],
    topic_name: str = "",
    topic_description: str = "",
) -> ProcessedScript:
    """
    Обработать сценарий урока.
    Удобная обёртка для использования без создания экземпляра класса.
    """
    processor = LessonScriptProcessor(topic_name, topic_description)
    return processor.process(raw_script)


def enhance_lesson_script(raw_script: list[dict]) -> list[dict]:
    """
    Расширить сценарий урока и вернуть в формате dict для сохранения.
    """
    processed = process_lesson_script(raw_script)
    return [step.to_dict() for step in processed.steps]
