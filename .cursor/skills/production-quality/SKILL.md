---
name: production-quality
description: >-
  Enforce production-level standards for the PaperTrader application (FastAPI + React).
  Use when adding features, fixing bugs, refactoring, or reviewing code in this project.
  Ensures proper error handling, logging, type safety, testing, security, and performance.
---

# Production Quality Standards — PaperTrader

## Architecture Overview

| Layer | Stack | Key Files |
|-------|-------|-----------|
| Backend | FastAPI, Pydantic, SmartAPI SDK | `backend/main.py`, `backend/routes/`, `backend/trading_engine.py` |
| Frontend | React 19, Zustand, TanStack Query, TailwindCSS | `frontend/src/` |
| Data | JSON file store | `backend/db/store.py` |
| Real-time | WebSocket (Angel One → backend thread → frontend WS) | `backend/websocket_manager.py` |

## Mandatory Checklist (apply to every change)

```
- [ ] Type annotations on all function signatures (backend: full Python types; frontend: strict TypeScript, no `any`)
- [ ] Input validation via Pydantic models for all API endpoints
- [ ] Structured logging (use existing `logger` instances; include context like token, symbol, amount)
- [ ] Graceful error handling: never expose stack traces to the client
- [ ] No hardcoded secrets or credentials — everything via `backend/config.py` → `.env`
- [ ] Unit-testable: pure logic separated from I/O (trading_engine should not directly call external APIs)
- [ ] CORS restricted to known origins only
```

## Backend Standards

### Error Handling

Raise domain exceptions, catch at the route layer, return consistent error shape:

```python
# Route layer pattern
@router.post("/action")
async def action(req: ActionRequest):
    try:
        result = service_function(req)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail="Internal error")
```

Never let unhandled exceptions leak; add a global exception handler in `main.py` for safety:

```python
@app.exception_handler(Exception)
async def global_handler(request, exc):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### Logging

- Use `logging.getLogger(__name__)` per module (already set up).
- Log at INFO for business events (login, trade, reset).
- Log at WARNING for recoverable issues (cache miss, retry).
- Log at ERROR for failures (API errors, WebSocket drops).
- Include structured context: `logger.info("BUY %d lots %s @ %.2f", qty, symbol, price)`.

### Data Layer

- All JSON read/write goes through `backend/db/store.py` — never open data files directly elsewhere.
- Use file locks (`fcntl` or `filelock` lib) for concurrent write safety.
- Validate data on read using Pydantic models (already done via `Portfolio(**data)`).
- Keep backup before writes for critical operations (portfolio balance changes).

### WebSocket Manager

- The Angel One WS runs in a daemon thread; always handle thread-safety when accessing `_latest_prices`.
- Handle reconnection: if `_on_close` fires unexpectedly, attempt reconnect with exponential backoff.
- Clean up dead clients promptly in `_broadcast`.

### Security

- Validate `option_type` is strictly "CE" or "PE" (use enum, already done).
- Sanitize `folder` param in `/api/system/history/{folder}` to prevent path traversal.
- Never log auth tokens, PINs, or TOTP secrets at any level.
- Rate-limit the `/api/auth/login` endpoint.

## Frontend Standards

### TypeScript

- Enable `strict: true` in `tsconfig.json`.
- All API responses typed in `frontend/src/lib/types.ts`.
- No `as any` casts. Use type guards or discriminated unions.

### State Management

- Zustand store (`useAppStore`) for global state only (auth, portfolio, prices).
- Component-local state for UI concerns (modals, form fields).
- TanStack Query for server state (option chain, trades, history).

### Error UX

- Show toast/notification on API errors — never silent failures.
- Disable action buttons during pending requests.
- Show loading skeletons, not blank screens.

### Performance

- Debounce rapid WebSocket price updates before re-rendering the full option chain.
- Memoize expensive computations (sorted strikes, filtered positions).
- Lazy-load pages with React.lazy + Suspense.

## Testing Requirements

### Backend (pytest)

- Unit tests for `trading_engine.py` (buy/sell logic, balance checks, P&L calculation).
- Unit tests for `instrument_service.py` (option chain parsing, expiry sorting).
- Integration tests for each route (use FastAPI TestClient).
- Mock `SmartAPISession` and file I/O in tests.

### Frontend (Vitest + React Testing Library)

- Component tests for critical flows (Login, Buy, Sell, Reset).
- Store tests for Zustand state transitions.
- Mock WebSocket and API calls.

### Test file naming

- Backend: `backend/tests/test_<module>.py`
- Frontend: `frontend/src/__tests__/<Component>.test.tsx`

## API Response Format

All endpoints return a consistent envelope:

```json
// Success
{"status": "success", "data": { ... }}

// Error (via HTTPException)
{"detail": "Human-readable error message"}
```

## Git & Deployment

- Commit messages: `type(scope): description` (e.g., `feat(trading): add stop-loss support`).
- Never commit `.env`, `data/`, `venv/`, `node_modules/`, or `__pycache__/`.
- Pin dependency versions in `requirements.txt` (e.g., `fastapi==0.115.0`).
- Add a `Dockerfile` and `docker-compose.yml` when preparing for deployment.
- Add health check at `/api/health` (already exists).

## Performance Guidelines

- Instrument cache: refresh once per day, serve from memory.
- WebSocket broadcast: batch ticks if > 50 updates/sec to reduce frontend re-renders.
- File store reads are acceptable for current scale; plan migration to SQLite if trades exceed 10k.

## What NOT To Do

- Do NOT add ORM/database unless the user explicitly requests it.
- Do NOT replace the JSON file store without discussion.
- Do NOT add authentication middleware (this is a local paper trading tool).
- Do NOT place real trades or interact with order placement APIs.
- Do NOT log sensitive credentials.
