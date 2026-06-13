# -*- coding: utf-8 -*-
"""
Тесты профессионального диалогового модуля (TutorDialogEngine).

Запуск:
    cd bot
    pytest tests/test_tutor_engine.py -v

Не требуют БД, Claude API или сети — используют заглушки.
"""

import asyncio
import os
import sys
import pytest

_bot_root = os.path.dirname(os.path.dirname(__file__))
_backend_root = os.path.abspath(os.path.join(_bot_root, "..", "backend"))
for p in (_bot_root, _backend_root):
    pa = os.path.abspath(p)
    if pa not in sys.path:
        sys.path.insert(0, pa)

os.environ["LLM_STUB_MODE"] = "true"
os.environ["TTS_STUB_MODE"] = "true"
os.environ["ASR_STUB_MODE"] = "true"
os.environ["VCS_STUB_MODE"] = "true"

from src.dialog.intent_classifier import IntentClassifier, IntentType
from src.dialog.teaching_strategies import (
    TeachingStrategy, UnderstandingLevel,
    select_strategy, build_strategy_prompt, estimate_understanding,
)
from src.dialog.student_model import StudentModel, LearningStyle, EmotionState as StudentEmotion
from src.dialog.tutor_engine import StubTutorEngine, make_tutor_engine


# ═══════════════════════════════════════════════════════════════════════════
#  IntentClassifier
# ═══════════════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    def setup_method(self):
        self.classifier = IntentClassifier(current_topic_keywords="\u0430\u043b\u043a\u0430\u043d\u044b \u0443\u0433\u043b\u0435\u0432\u043e\u0434\u043e\u0440\u043e\u0434\u044b")

    def test_question_detection(self):
        intent = self.classifier.classify("\u0427\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0430\u043b\u043a\u0430\u043d\u044b?")
        assert intent.type == IntentType.ON_TOPIC_QUESTION
        assert intent.is_question is True

    def test_off_topic_question(self):
        intent = self.classifier.classify("\u0410 \u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u044f\u0434\u0435\u0440\u043d\u044b\u0439 \u0441\u0438\u043d\u0442\u0435\u0437?")
        assert intent.type == IntentType.OFF_TOPIC_QUESTION
        assert intent.is_question is True

    def test_confusion_signal(self):
        intent = self.classifier.classify("\u041d\u0435 \u043f\u043e\u043d\u044f\u043b, \u043c\u043e\u0436\u0435\u0448\u044c \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c?")
        assert intent.type == IntentType.CONFUSION_SIGNAL

    def test_correct_answer(self):
        intent = self.classifier.classify(
            "\u0414\u0430",
            current_step_question="\u042d\u0442\u043e \u0430\u043b\u043a\u0430\u043d?",
        )
        assert intent.type == IntentType.CORRECT_ANSWER

    def test_filler(self):
        intent = self.classifier.classify("\u043c\u043c")
        assert intent.type == IntentType.FILLER

    def test_greeting(self):
        intent = self.classifier.classify("\u041f\u0440\u0438\u0432\u0435\u0442!")
        assert intent.type == IntentType.GREETING

    def test_farewell(self):
        intent = self.classifier.classify("\u041f\u043e\u043a\u0430!")
        assert intent.type == IntentType.FAREWELL

    def test_engagement_check(self):
        intent = self.classifier.classify("\u0422\u044b \u043c\u0435\u043d\u044f \u0441\u043b\u044b\u0448\u0438\u0448\u044c?")
        assert intent.type == IntentType.ENGAGEMENT_CHECK

    def test_silence(self):
        intent = self.classifier.classify("")
        assert intent.type == IntentType.SILENCE

    def test_clarification_request(self):
        intent = self.classifier.classify("\u041c\u043e\u0436\u0435\u0448\u044c \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c?")
        assert intent.type == IntentType.CONFUSION_SIGNAL


# ═══════════════════════════════════════════════════════════════════════════
#  TeachingStrategies
# ═══════════════════════════════════════════════════════════════════════════

class TestTeachingStrategies:
    def test_select_strategy_on_topic_confused(self):
        strategy = select_strategy(
            intent=IntentType.ON_TOPIC_QUESTION,
            understanding=UnderstandingLevel.CONFUSED,
        )
        assert strategy.method.value == "step_back"

    def test_select_strategy_correct_answer(self):
        strategy = select_strategy(
            intent=IntentType.CORRECT_ANSWER,
            understanding=UnderstandingLevel.BASIC,
        )
        assert strategy.method.value == "retrieval_practice"

    def test_select_strategy_confusion(self):
        strategy = select_strategy(
            intent=IntentType.CONFUSION_SIGNAL,
            understanding=UnderstandingLevel.CONFUSED,
        )
        assert strategy.method.value == "analogy"

    def test_select_strategy_off_topic(self):
        strategy = select_strategy(
            intent=IntentType.OFF_TOPIC_QUESTION,
            understanding=None,
        )
        assert strategy.method.value == "direct_explanation"

    def test_build_strategy_prompt(self):
        from src.dialog.teaching_strategies import TeachingMethod
        strategy = TeachingStrategy(
            method=TeachingMethod.ANALOGY,
            reason="test",
            suggested_response_style="test",
        )
        prompt = build_strategy_prompt(strategy)
        # Проверяем что промпт содержит ключевые слова по аналогии
        assert "аналоги" in prompt.lower() or "жизн" in prompt.lower()

    def test_estimate_understanding_empty(self):
        level = estimate_understanding([])
        assert level == UnderstandingLevel.BASIC

    def test_estimate_understanding_confused(self):
        history = [
            {"role": "student", "text": "\u041d\u0435 \u043f\u043e\u043d\u044f\u043b \u044d\u0442\u043e"},
            {"role": "student", "text": "\u0421\u043b\u0438\u0448\u043a\u043e\u043c \u0441\u043b\u043e\u0436\u043d\u043e"},
        ]
        level = estimate_understanding(history)
        assert level == UnderstandingLevel.CONFUSED


# ═══════════════════════════════════════════════════════════════════════════
#  StudentModel
# ═══════════════════════════════════════════════════════════════════════════

class TestStudentModel:
    def test_initial_state(self):
        model = StudentModel(student_name="\u0422\u0435\u0441\u0442", grade=9)
        assert model.student_name == "\u0422\u0435\u0441\u0442"
        assert model.grade == 9
        assert model.overall_confidence == 0.5

    def test_update_correct_answer(self):
        model = StudentModel()
        model.update_from_interaction(
            step_index=1,
            understanding=UnderstandingLevel.BASIC,
            emotion=StudentEmotion.CONFIDENT,
            is_correct=True,
        )
        assert model.total_correct == 1
        assert model.overall_confidence > 0.5

    def test_update_incorrect_answer(self):
        model = StudentModel()
        model.update_from_interaction(
            step_index=1,
            understanding=UnderstandingLevel.CONFUSED,
            emotion=StudentEmotion.CONFUSED,
            is_correct=False,
        )
        assert model.total_incorrect == 1
        assert model.overall_confidence < 0.5

    def test_get_summary(self):
        model = StudentModel(student_name="\u0410\u043b\u0438\u0441\u0430", grade=10)
        summary = model.get_summary()
        assert "\u0410\u043b\u0438\u0441\u0430" in summary
        assert "10 \u043a\u043b\u0430\u0441\u0441" in summary

    def test_to_dict_and_from_dict(self):
        model = StudentModel(student_name="\u0422\u0435\u0441\u0442", grade=11)
        model.update_from_interaction(
            step_index=1,
            understanding=UnderstandingLevel.PROFICIENT,
            emotion=StudentEmotion.CONFIDENT,
            is_correct=True,
        )
        data = model.to_dict()
        restored = StudentModel.from_dict(data)
        assert restored.student_name == "\u0422\u0435\u0441\u0442"
        assert restored.grade == 11
        assert restored.total_correct == 1

    def test_recommendations(self):
        model = StudentModel()
        for _ in range(3):
            model.update_from_interaction(
                step_index=1,
                understanding=UnderstandingLevel.CONFUSED,
                emotion=StudentEmotion.CONFUSED,
                is_correct=False,
            )
        recommendations = model.get_teaching_recommendations()
        assert len(recommendations) > 0


# ═══════════════════════════════════════════════════════════════════════════
#  StubTutorEngine
# ═══════════════════════════════════════════════════════════════════════════

class TestStubTutorEngine:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_respond_returns_text(self):
        engine = StubTutorEngine(student_name="\u0422\u0435\u0441\u0442")
        resp = self._run(engine.respond("\u0427\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0430\u043b\u043a\u0430\u043d\u044b?"))
        assert isinstance(resp.text, str)
        assert len(resp.text) > 0

    def test_cycles_through_responses(self):
        engine = StubTutorEngine()
        replies = [self._run(engine.respond("\u0432\u043e\u043f\u0440\u043e\u0441")).text for _ in range(8)]
        assert len(set(replies)) > 1

    def test_set_step_context(self):
        engine = StubTutorEngine()
        engine.set_step_context(5, 10)

    def test_get_student_model(self):
        engine = StubTutorEngine(student_name="\u041c\u043e\u0434\u0435\u043b\u044c")
        model = engine.get_student_model()
        assert model.student_name == "\u041c\u043e\u0434\u0435\u043b\u044c"

    def test_get_recommendations(self):
        engine = StubTutorEngine()
        recs = engine.get_recommendations()
        assert isinstance(recs, list)

    def test_close_is_safe(self):
        engine = StubTutorEngine()
        self._run(engine.close())


# ═══════════════════════════════════════════════════════════════════════════
#  make_tutor_engine factory
# ═══════════════════════════════════════════════════════════════════════════

class TestMakeTutorEngine:
    def test_stub_mode_returns_stub(self):
        engine = make_tutor_engine(
            retriever=None,
            topic_context="\u0442\u0435\u043c\u0430",
            student_name="\u0422\u0435\u0441\u0442",
            student_grade=9,
        )
        assert isinstance(engine, StubTutorEngine)

    def test_no_api_key_returns_stub(self, monkeypatch):
        monkeypatch.setenv("LLM_STUB_MODE", "false")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        engine = make_tutor_engine(
            retriever=None,
            topic_context="\u0442\u0435\u043c\u0430",
            student_name="\u0422\u0435\u0441\u0442",
            student_grade=9,
        )
        assert isinstance(engine, StubTutorEngine)
