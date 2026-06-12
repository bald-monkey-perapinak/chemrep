# Architecture Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task.

**Goal:** Fix critical bugs, performance issues, and architectural debt across backend, bot, and frontend.

**Architecture:** Fix P0 bugs first (deadline undefined, N+1 query, NullPool), then package backend properly, then clean up frontend store and CSS.

**Tech Stack:** Python/FastAPI, PostgreSQL/SQLAlchemy, React/Zustand, Docker

---

## File Structure

**Modified files:**
- `bot/src/orchestrator/runner.py` — fix deadline bug, clean up sys.path
- `backend/src/api/routes/students.py` — fix N+1 query
- `backend/src/db/base.py` — replace NullPool with proper pool
- `backend/src/api/routes/auth.py` — use from_attributes, fix UUID
- `backend/src/api/routes/lessons.py` — deduplicate SessionOut/HomeworkOut
- `frontend/src/utils/api.js` — add timeout, retry, fix 401 handling
- `frontend/src/store/useStore.js` — fix toast timer, deduplicate findNode
- `frontend/src/utils/helpers.js` — add fmtDt
- `frontend/src/App.jsx` — add error boundary, loading states
- `frontend/src/components/shared/LessonMonitor.jsx` — extract to CSS classes

**New files:**
- `backend/pyproject.toml` — package backend as installable module
- `frontend/src/components/shared/ErrorBoundary.jsx` — React error boundary

---

### Task 1: Fix deadline bug in runner.py

**Files:**
- Modify: `bot/src/orchestrator/runner.py`

- [ ] **Step 1: Add deadline computation in _free_dialog**

Find the `_free_dialog` method and add `deadline = asyncio.get_event_loop().time() + timeout` after the docstring, before the `async for` loop.

- [ ] **Step 2: Verify fix**

Read the method to confirm `deadline` is defined before first use at the `if asyncio.get_event_loop().time() >= deadline:` check.

- [ ] **Step 3: Commit**

```bash
git add bot/src/orchestrator/runner.py
git commit -m "fix: add missing deadline variable in _free_dialog"
```

---

### Task 2: Fix N+1 query in students.py

**Files:**
- Modify: `backend/src/api/routes/students.py`

- [ ] **Step 1: Add joinedload to get_student query**

Change the query in `get_student()` (around line 118) from:
```python
lessons = (
    db.query(Lesson)
    .filter(Lesson.student_id == student_id)
    .order_by(Lesson.scheduled_at.desc())
    .limit(20)
    .all()
)
```
To:
```python
from sqlalchemy.orm import joinedload
lessons = (
    db.query(Lesson)
    .options(joinedload(Lesson.topic))
    .filter(Lesson.student_id == student_id)
    .order_by(Lesson.scheduled_at.desc())
    .limit(20)
    .all()
)
```

- [ ] **Step 2: Verify fix**

Read the file to confirm joinedload is in the query.

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/routes/students.py
git commit -m "fix: add joinedload to prevent N+1 query in get_student"
```

---

### Task 3: Replace NullPool with proper connection pool

**Files:**
- Modify: `backend/src/db/base.py`

- [ ] **Step 1: Replace NullPool with QueuePool**

Change:
```python
from sqlalchemy.pool import NullPool
engine = create_engine(DATABASE_URL, poolclass=NullPool)
```
To:
```python
from sqlalchemy import create_engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
```

- [ ] **Step 2: Verify fix**

Read the file to confirm the change.

- [ ] **Step 3: Commit**

```bash
git add backend/src/db/base.py
git commit -m "fix: replace NullPool with connection pooling"
```

---

### Task 4: Package backend as installable module

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "chemrep-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools.packages.find]
include = ["src*"]
```

- [ ] **Step 2: Verify file exists**

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "chore: add pyproject.toml to backend for package install"
```

---

### Task 5: Fix toast timer leak in useStore.js

**Files:**
- Modify: `frontend/src/store/useStore.js`

- [ ] **Step 1: Store timeout ID and clear before setting new**

Find `showToast` and change:
```javascript
showToast: (msg) => {
  set({ toast: msg })
  setTimeout(() => set({ toast: null }), 2500)
},
```
To:
```javascript
_showToastTimer: null,
showToast: (msg) => {
  const prev = get()._showToastTimer
  if (prev) clearTimeout(prev)
  const timer = setTimeout(() => set({ toast: null, _showToastTimer: null }), 2500)
  set({ toast: msg, _showToastTimer: timer })
},
```

- [ ] **Step 2: Verify fix**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/useStore.js
git commit -m "fix: prevent toast timer leak on rapid calls"
```

---

### Task 6: Add ErrorBoundary component

**Files:**
- Create: `frontend/src/components/shared/ErrorBoundary.jsx`

- [ ] **Step 1: Create ErrorBoundary**

```jsx
import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <h2>Что-то пошло не так</h2>
          <p style={{ color: 'var(--color-text-muted)' }}>
            {this.state.error?.message || 'Неизвестная ошибка'}
          </p>
          <button className="btn" onClick={() => this.setState({ hasError: false })}>
            Попробовать снова
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
```

- [ ] **Step 2: Verify file exists**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shared/ErrorBoundary.jsx
git commit -m "feat: add React ErrorBoundary component"
```

---

### Task 7: Wrap App content in ErrorBoundary

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Import and wrap**

Add import at top:
```javascript
import ErrorBoundary from './components/shared/ErrorBoundary'
```

Wrap the `<main>` content in ErrorBoundary:
```jsx
<ErrorBoundary>
  <div className="content">
    {/* ... existing section renders ... */}
  </div>
</ErrorBoundary>
```

- [ ] **Step 2: Verify fix**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: wrap main content in ErrorBoundary"
```

---

### Task 8: Fix 401 handling in api.js

**Files:**
- Modify: `frontend/src/utils/api.js`

- [ ] **Step 1: Replace window.location.reload with graceful logout**

Find the 401 handling in `request()` and change:
```javascript
if (res.status === 401) {
  localStorage.removeItem('token')
  window.location.reload()
  return
}
```
To:
```javascript
if (res.status === 401) {
  localStorage.removeItem('token')
  window.dispatchEvent(new CustomEvent('auth:logout'))
  return
}
```

- [ ] **Step 2: Add event listener in App.jsx**

In App.jsx, add after `useEffect` for auth checking:
```javascript
useEffect(() => {
  const handleLogout = () => setLoggedIn(false)
  window.addEventListener('auth:logout', handleLogout)
  return () => window.removeEventListener('auth:logout', handleLogout)
}, [])
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/api.js frontend/src/App.jsx
git commit -m "fix: graceful 401 logout without page reload"
```

---

### Task 9: Add fmtDt to helpers.js and deduplicate

**Files:**
- Modify: `frontend/src/utils/helpers.js`
- Modify: `frontend/src/components/Dashboard/Dashboard.jsx`
- Modify: `frontend/src/components/Lessons/Lessons.jsx`

- [ ] **Step 1: Add fmtDt to helpers.js**

Add to `frontend/src/utils/helpers.js`:
```javascript
export function fmtDt(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const mo = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
  return `${d.getDate()} ${mo[d.getMonth()]}, ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
```

- [ ] **Step 2: Update Dashboard.jsx to use shared fmtDt**

Remove the local `fmtDt` definition and import from helpers:
```javascript
import { fmtDt } from '../../utils/helpers'
```

- [ ] **Step 3: Update Lessons.jsx to use shared fmtDt**

Remove the local `fmtDt` definition and import from helpers:
```javascript
import { fmtDt } from '../../utils/helpers'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/helpers.js frontend/src/components/Dashboard/Dashboard.jsx frontend/src/components/Lessons/Lessons.jsx
git commit -m "refactor: deduplicate fmtDt into shared helpers"
```

---

### Task 10: Add loading states to Dashboard and Lessons

**Files:**
- Modify: `frontend/src/components/Dashboard/Dashboard.jsx`
- Modify: `frontend/src/components/Lessons/Lessons.jsx`
- Modify: `frontend/src/components/Students/Students.jsx`

- [ ] **Step 1: Add loading check to Dashboard**

Add at top of Dashboard component:
```javascript
const lessonsLoading = useStore(s => s.lessonsLoading)
const studentsLoading = useStore(s => s.studentsLoading)
```

Add loading indicator before the stats grid:
```javascript
if (lessonsLoading || studentsLoading) {
  return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Загрузка...</div>
}
```

- [ ] **Step 2: Add loading check to Lessons**

```javascript
const lessonsLoading = useStore(s => s.lessonsLoading)
if (lessonsLoading) {
  return <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Загрузка занятий...</div>
}
```

- [ ] **Step 3: Add loading check to Students**

```javascript
const studentsLoading = useStore(s => s.studentsLoading)
if (studentsLoading) {
  return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Загрузка учеников...</div>
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Dashboard/Dashboard.jsx frontend/src/components/Lessons/Lessons.jsx frontend/src/components/Students/Students.jsx
git commit -m "feat: add loading states to Dashboard, Lessons, Students"
```

---

## Verification

After all tasks:
1. `docker-compose up -d --build` — all services start
2. `docker exec chemrep-backend-1 alembic upgrade head` — migration runs
3. Open http://localhost:3000 — app loads without errors
4. Add a student — persists to DB
5. Create a lesson — platform auto-detected, duration saved
6. Check http://localhost:3001 — whiteboard loads
