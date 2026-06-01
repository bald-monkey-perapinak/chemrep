# Bot — Виртуальный участник конференций

Python-сервис, который подключается к видеоконференции, ведёт урок голосом преподавателя и управляет доской Miro.

## Структура

```
src/
├── orchestrator/   # Менеджер сессий, запуск/остановка урока по расписанию
├── vcs/            # Подключение к Zoom / Яндекс Телемост (WebRTC / SDK)
├── audio/          # TTS (синтез речи), ASR (распознавание), VAD, шумоподавление
├── dialog/         # LLM-ядро, RAG, контекст диалога, генерация ответов
└── miro/           # Управление доской Miro через REST API
```

## Поток данных

```
Расписание → Orchestrator
    → VCS Client (подключиться к конференции)
        → Audio OUT: TTS → виртуальный микрофон
        → Audio IN: микрофон ученика → ASR → Dialog Core
            → RAG (база знаний) → LLM → ответ → TTS
    → Miro API (рисовать на доске по шагам конспекта)
```

## Ключевые зависимости (планируемые)

- `openai-whisper` / `faster-whisper` — распознавание речи
- `elevenlabs` / `silero-tts` — синтез голоса
- `anthropic` — LLM (Claude API)
- `miro-api-python` — управление доской
- `pyaudio` / `sounddevice` — работа с аудио
- `webrtcvad` — детектор активности голоса

## Запуск

```bash
pip install -r requirements.txt
python -m src.orchestrator.main
```
