"""
Тесты диалогового модуля (RAG retriever + LLM engine).

Запуск:
    cd bot
    pytest tests/test_dialog.py -v

Не требуют БД, Claude API или сети — используют заглушки.
"""

import asyncio
import os
import sys
import pytest

_bot_root     = os.path.dirname(os.path.dirname(__file__))
_backend_root = os.path.abspath(os.path.join(_bot_root, "..", "backend"))
for p in (_bot_root, _backend_root):
    pa = os.path.abspath(p)
    if pa not in sys.path:
        sys.path.insert(0, pa)

os.environ["LLM_STUB_MODE"] = "true"
os.environ["TTS_STUB_MODE"] = "true"
os.environ["ASR_STUB_MODE"] = "true"
os.environ["VCS_STUB_MODE"] = "true"

from src.dialog.engine import (
    StubDialogEngine, ClaudeDialogEngine, TemplateDialogEngine, DialogMessage,
    make_dialog_engine, _format_rag_context, _build_messages, _extract_reply,
)
from src.dialog.retriever import (
    _extract_keywords, _keyword_score, _truncate, _split_into_chunks,
)


# ═══════════════════════════════════════════════════════════════════════════
#  RAG helper functions
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractKeywords:
    def test_basic(self):
        kws = _extract_keywords("Что такое алканы и их свойства?")
        assert "алканы" in kws
        assert "свойства" in kws

    def test_stop_words_removed(self):
        kws = _extract_keywords("как это работает")
        assert "как" not in kws
        assert "это" not in kws

    def test_short_words_removed(self):
        kws = _extract_keywords("pH и ко")
        assert "и" not in kws
        assert "ко" not in kws   # 2 символа — ниже порога в 3

    def test_empty_string(self):
        assert _extract_keywords("") == []

    def test_only_stop_words(self):
        kws = _extract_keywords("как это что для или при")
        assert kws == []


class TestKeywordScore:
    def test_full_match(self):
        score = _keyword_score("алканы — это углеводороды", ["алканы", "углеводороды"])
        assert score == 1.0

    def test_partial_match(self):
        score = _keyword_score("алканы — это вещества", ["алканы", "углеводороды"])
        assert score == 0.5

    def test_no_match(self):
        score = _keyword_score("реакция горения", ["алканы", "метан"])
        assert score == 0.0

    def test_empty_keywords(self):
        assert _keyword_score("любой текст", []) == 0.0

    def test_empty_text(self):
        assert _keyword_score("", ["алканы"]) == 0.0


class TestTruncate:
    def test_short_text_unchanged(self):
        text = "Алканы — это углеводороды."
        assert _truncate(text, 100) == text

    def test_long_text_truncated(self):
        text = "слово " * 200
        result = _truncate(text, 50)
        assert len(result) <= 55   # немного больше из-за "…"
        assert result.endswith("…")

    def test_exact_length(self):
        text = "а" * 100
        result = _truncate(text, 100)
        assert result == text


class TestSplitIntoChunks:
    def test_short_text_one_chunk(self):
        chunks = _split_into_chunks("Короткий текст.", 500)
        assert len(chunks) >= 1
        assert "Короткий текст." in chunks[0]

    def test_long_text_multiple_chunks(self):
        text = "слово " * 500
        chunks = _split_into_chunks(text, 100)
        assert len(chunks) > 1

    def test_chunks_not_empty(self):
        text = "Алканы. " * 50
        chunks = _split_into_chunks(text, 80)
        assert all(c.strip() for c in chunks)


# ═══════════════════════════════════════════════════════════════════════════
#  StubDialogEngine
# ═══════════════════════════════════════════════════════════════════════════

class TestStubDialogEngine:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_respond_returns_text(self):
        engine = StubDialogEngine()
        resp = self._run(engine.respond("Что такое алканы?"))
        assert isinstance(resp.text, str)
        assert len(resp.text) > 0

    def test_cycles_through_responses(self):
        engine = StubDialogEngine()
        replies = [self._run(engine.respond("вопрос")).text for _ in range(8)]
        # должен зациклиться — не все одинаковые
        assert len(set(replies)) > 1

    def test_empty_used_chunks(self):
        engine = StubDialogEngine()
        resp = self._run(engine.respond("вопрос"))
        assert resp.used_chunks == []

    def test_close_is_safe(self):
        engine = StubDialogEngine()
        self._run(engine.close())


# ═══════════════════════════════════════════════════════════════════════════
#  make_dialog_engine factory
# ═══════════════════════════════════════════════════════════════════════════

class TestMakeDialogEngine:
    def test_stub_mode_returns_stub(self):
        engine = make_dialog_engine(retriever=None, topic_context="тема")
        assert isinstance(engine, StubDialogEngine)

    def test_no_api_key_returns_template(self, monkeypatch):
        monkeypatch.setenv("LLM_STUB_MODE", "false")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        engine = make_dialog_engine(retriever=None, topic_context="тема")
        assert isinstance(engine, TemplateDialogEngine)

    def test_with_api_key_returns_claude(self, monkeypatch):
        monkeypatch.setenv("LLM_STUB_MODE", "false")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        engine = make_dialog_engine(retriever=None, topic_context="тема")
        assert isinstance(engine, ClaudeDialogEngine)
        asyncio.get_event_loop().run_until_complete(engine.close())


# ═══════════════════════════════════════════════════════════════════════════
#  _build_messages
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildMessages:
    def _make_history(self, n_turns: int) -> list[DialogMessage]:
        history = []
        for i in range(n_turns):
            history.append(DialogMessage(role="user",      text=f"вопрос {i}"))
            history.append(DialogMessage(role="assistant", text=f"ответ {i}"))
        return history

    def test_short_history_all_included(self):
        history = self._make_history(3)
        msgs = _build_messages(history, max_turns=10, rag_block="")
        assert len(msgs) == 6

    def test_long_history_trimmed(self):
        history = self._make_history(20)
        msgs = _build_messages(history, max_turns=5, rag_block="")
        assert len(msgs) == 10   # 5 пар × 2

    def test_rag_block_appended_to_last_user(self):
        history = [DialogMessage(role="user", text="вопрос")]
        msgs = _build_messages(history, max_turns=5, rag_block="КОНТЕКСТ")
        assert "КОНТЕКСТ" in msgs[-1]["content"]

    def test_no_rag_block_no_injection(self):
        history = [DialogMessage(role="user", text="вопрос")]
        msgs = _build_messages(history, max_turns=5, rag_block="")
        assert msgs[-1]["content"] == "вопрос"

    def test_roles_correct(self):
        history = [
            DialogMessage(role="user",      text="вопрос"),
            DialogMessage(role="assistant", text="ответ"),
        ]
        msgs = _build_messages(history, max_turns=10, rag_block="")
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"


# ═══════════════════════════════════════════════════════════════════════════
#  _extract_reply
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractReply:
    def test_normal_response(self):
        data = {"content": [{"type": "text", "text": "Алканы — это углеводороды."}]}
        assert _extract_reply(data) == "Алканы — это углеводороды."

    def test_multiple_text_blocks(self):
        data = {"content": [
            {"type": "text", "text": "Первая часть."},
            {"type": "text", "text": "Вторая часть."},
        ]}
        reply = _extract_reply(data)
        assert "Первая часть." in reply
        assert "Вторая часть." in reply

    def test_empty_content(self):
        data = {"content": []}
        reply = _extract_reply(data)
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_missing_content_key(self):
        reply = _extract_reply({})
        assert isinstance(reply, str)

    def test_non_text_blocks_ignored(self):
        data = {"content": [
            {"type": "tool_use", "id": "123"},
            {"type": "text",     "text": "Ответ."},
        ]}
        assert _extract_reply(data) == "Ответ."


# ═══════════════════════════════════════════════════════════════════════════
#  _format_rag_context
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatRagContext:
    def test_empty_chunks(self):
        assert _format_rag_context([]) == ""

    def test_single_chunk(self):
        from src.dialog.retriever import RetrievedChunk
        chunk = RetrievedChunk(source="topic_script", title="Алканы", text="Алканы — углеводороды.", score=0.9)
        result = _format_rag_context([chunk])
        assert "Алканы" in result
        assert "углеводороды" in result

    def test_multiple_chunks_separated(self):
        from src.dialog.retriever import RetrievedChunk
        chunks = [
            RetrievedChunk(source="topic_script", title="Тема А", text="Текст А", score=0.9),
            RetrievedChunk(source="file_text",    title="Тема Б", text="Текст Б", score=0.7),
        ]
        result = _format_rag_context(chunks)
        assert "Тема А" in result
        assert "Тема Б" in result
