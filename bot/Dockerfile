FROM python:3.12-slim
WORKDIR /app
COPY bot/requirements.txt ./bot_requirements.txt
COPY backend/requirements.txt ./backend_requirements.txt
RUN pip install --no-cache-dir -r bot_requirements.txt
COPY bot/ ./bot/
COPY backend/ ./backend/
RUN ln -s /app/backend/src/models /app/bot/src/models && \
    ln -s /app/backend/src/events /app/bot/src/events && \
    ln -s /app/backend/src/utils /app/bot/src/utils && \
    ln -s /app/backend/src/db /app/bot/src/db
WORKDIR /app/bot
CMD ["python", "-m", "src.orchestrator.main"]
