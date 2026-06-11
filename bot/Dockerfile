FROM python:3.12-slim
WORKDIR /app
COPY bot/requirements.txt ./bot_requirements.txt
COPY backend/requirements.txt ./backend_requirements.txt
RUN pip install --no-cache-dir -r bot_requirements.txt
COPY bot/ ./bot/
COPY backend/ ./backend/
WORKDIR /app/bot
CMD ["python", "-m", "src.orchestrator.main"]
