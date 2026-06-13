# Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add frontend UX improvements, backend observability, and infra reliability to ChemTutor

**Architecture:** Enhance existing components with error handling, monitoring, and CI/CD

**Tech Stack:** React, FastAPI, PostgreSQL, GitHub Actions, Prometheus, Grafana

---

## Task 1: Frontend Error Boundary Integration

**Covers:** Frontend UX

**Files:**
- Modify: `frontend/src/App.jsx:97-107`
- Test: Manual verification

- [ ] **Step 1: Wrap lazy routes with ErrorBoundary**

Edit `frontend/src/App.jsx` to wrap the Suspense section:

```jsx
import ErrorBoundary from './components/shared/ErrorBoundary'

// ... existing code ...

<div className="content">
  <ErrorBoundary>
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/calendar" element={<Calendar onOpenNewLesson={openNewLesson} />} />
        <Route path="/lessons" element={<Lessons />} />
        <Route path="/students" element={<Students />} />
        <Route path="/knowledge" element={<KnowledgeBase />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  </ErrorBoundary>
</div>
```

- [ ] **Step 2: Create NotFound component**

Create `frontend/src/components/shared/NotFound.jsx`:

```jsx
export default function NotFound() {
  return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <h2>404</h2>
      <p style={{ color: 'var(--color-text-muted)' }}>Страница не найдена</p>
      <a href="/" className="btn">На главную</a>
    </div>
  )
}
```

- [ ] **Step 3: Add offline detection hook**

Create `frontend/src/hooks/useOffline.js`:

```javascript
import { useState, useEffect } from 'react'

export function useOffline() {
  const [isOffline, setIsOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  return isOffline
}
```

- [ ] **Step 4: Add offline banner to AppShell**

Edit `frontend/src/App.jsx` to add offline indicator in AppShell:

```jsx
import { useOffline } from './hooks/useOffline'

// Inside AppShell component:
const isOffline = useOffline()

// Add after topbar:
{isOffline && (
  <div style={{ 
    background: 'var(--color-warning)', 
    color: 'white', 
    padding: '8px 16px', 
    textAlign: 'center' 
  }}>
    Нет подключения к интернету
  </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/shared/NotFound.jsx frontend/src/hooks/useOffline.js
git commit -m "feat: add error boundary, 404 page, offline detection"
```

---

## Task 2: Backend API Versioning

**Covers:** Backend observability

**Files:**
- Modify: `backend/main.py:70-78`
- Create: `backend/src/api/versioned.py`
- Test: Manual verification

- [ ] **Step 1: Create versioned router wrapper**

Create `backend/src/api/versioned.py`:

```python
from fastapi import APIRouter

def versioned_router(router: APIRouter, prefix: str = "/api/v1") -> APIRouter:
    """Wrap router with /api/v1 prefix."""
    versioned = APIRouter(prefix=prefix)
    versioned.include_router(router)
    return versioned
```

- [ ] **Step 2: Update main.py to use versioned routes**

Edit `backend/main.py` to replace current router includes:

```python
from src.api.versioned import versioned_router

# Replace:
# app.include_router(auth_router,      prefix="/api")
# ... with:
app.include_router(versioned_router(auth_router))
app.include_router(versioned_router(knowledge_router))
app.include_router(versioned_router(students_router))
app.include_router(versioned_router(lessons_router))
app.include_router(versioned_router(sessions_router))
app.include_router(versioned_router(voice_router))
app.include_router(versioned_router(sse_router))
app.include_router(versioned_router(training_router))
app.include_router(versioned_router(extract_router))

# Keep backward compatibility for /api/* (optional)
@app.get("/api/health", tags=["system"])
async def api_health_compat():
    return {"status": "ok", "version": APP_VERSION}
```

- [ ] **Step 3: Commit**

```bash
git add backend/main.py backend/src/api/versioned.py
git commit -m "feat: add API versioning with /api/v1 prefix"
```

---

## Task 3: Request ID Middleware

**Covers:** Backend observability

**Files:**
- Create: `backend/src/middleware/request_id.py`
- Modify: `backend/main.py`
- Test: Manual verification

- [ ] **Step 1: Create request ID middleware**

Create `backend/src/middleware/request_id.py`:

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 2: Add middleware to main.py**

Edit `backend/main.py` to add after RateLimitMiddleware:

```python
from src.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/middleware/request_id.py backend/main.py
git commit -m "feat: add request ID tracking middleware"
```

---

## Task 4: Structured JSON Logging

**Covers:** Backend observability

**Files:**
- Create: `backend/src/utils/logging.py`
- Modify: `backend/main.py`
- Test: Manual verification

- [ ] **Step 1: Create structured logger**

Create `backend/src/utils/logging.py`:

```python
import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_json_logging(level: str = "INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    logging.root.handlers = [handler]
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))
```

- [ ] **Step 2: Update main.py to use JSON logging**

Edit `backend/main.py` lifespan:

```python
from src.utils.logging import setup_json_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    from src.utils.s3 import ensure_bucket
    ensure_bucket()
    yield
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/utils/logging.py backend/main.py
git commit -m "feat: add structured JSON logging"
```

---

## Task 5: Prometheus Metrics

**Covers:** Backend observability

**Files:**
- Create: `backend/src/middleware/metrics.py`
- Modify: `backend/main.py`
- Modify: `requirements.txt`
- Test: Manual verification

- [ ] **Step 1: Add prometheus_client dependency**

Edit `backend/requirements.txt`:

```
prometheus-client>=0.20.0
```

- [ ] **Step 2: Create metrics middleware**

Create `backend/src/middleware/metrics.py`:

```python
import time
from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response
```

- [ ] **Step 3: Add metrics endpoint and middleware to main.py**

Edit `backend/main.py`:

```python
from src.middleware.metrics import MetricsMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app.add_middleware(MetricsMiddleware)

@app.get("/metrics", tags=["system"])
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/middleware/metrics.py backend/main.py backend/requirements.txt
git commit -m "feat: add Prometheus metrics endpoint"
```

---

## Task 6: GitHub Actions CI/CD

**Covers:** Infra reliability

**Files:**
- Create: `.github/workflows/ci.yml`
- Test: Manual verification

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v
      - name: Run lint
        run: |
          cd backend
          python -m flake8 src/ --max-line-length=120

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run lint
        run: |
          cd frontend
          npm run lint
      - name: Build
        run: |
          cd frontend
          npm run build

  bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd bot
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd bot
          pytest tests/ -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add GitHub Actions CI/CD pipeline"
```

---

## Task 7: Prometheus + Grafana Docker Compose

**Covers:** Infra reliability

**Files:**
- Create: `infra/prometheus/prometheus.yml`
- Create: `infra/grafana/datasources.yml`
- Modify: `docker-compose.yml`
- Test: Manual verification

- [ ] **Step 1: Create Prometheus config**

Create `infra/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'chemrep-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

- [ ] **Step 2: Create Grafana datasource**

Create `infra/grafana/datasources.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

- [ ] **Step 3: Add services to docker-compose.yml**

Edit `docker-compose.yml` to add:

```yaml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    networks:
      - chemrep

  grafana:
    image: grafana/grafana:latest
    volumes:
      - ./infra/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
    ports:
      - "3002:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - chemrep
```

- [ ] **Step 4: Commit**

```bash
git add infra/ docker-compose.yml
git commit -m "feat: add Prometheus and Grafana monitoring"
```

---

## Task 8: Automated Database Backups

**Covers:** Infra reliability

**Files:**
- Create: `scripts/backup-db.sh`
- Create: `.github/workflows/backup.yml`
- Test: Manual verification

- [ ] **Step 1: Create backup script**

Create `scripts/backup-db.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/chemrep_$TIMESTAMP.sql.gz"

mkdir -p $BACKUP_DIR

docker exec chemrep-postgres pg_dump -U chemrep chemrep | gzip > $BACKUP_FILE

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

- [ ] **Step 2: Create backup workflow**

Create `.github/workflows/backup.yml`:

```yaml
name: Database Backup

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run backup
        run: |
          chmod +x scripts/backup-db.sh
          ./scripts/backup-db.sh
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: database-backup
          path: backups/*.sql.gz
          retention-days: 7
```

- [ ] **Step 3: Commit**

```bash
git add scripts/backup-db.sh .github/workflows/backup.yml
git commit -m "feat: add automated database backups"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Error boundary, 404, offline detection | App.jsx, NotFound.jsx, useOffline.js |
| 2 | API versioning | main.py, versioned.py |
| 3 | Request ID tracking | request_id.py, main.py |
| 4 | Structured JSON logging | logging.py, main.py |
| 5 | Prometheus metrics | metrics.py, main.py, requirements.txt |
| 6 | GitHub Actions CI/CD | ci.yml |
| 7 | Prometheus + Grafana | prometheus.yml, datasources.yml, docker-compose.yml |
| 8 | Database backups | backup-db.sh, backup.yml |
