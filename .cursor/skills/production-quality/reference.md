# Production Quality Reference — Detailed Patterns

## Backend Patterns

### Adding a New Route

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/<domain>", tags=["<domain>"])


class NewRequest(BaseModel):
    field: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0)


class NewResponse(BaseModel):
    status: str
    data: dict


@router.post("/<action>", response_model=NewResponse)
async def new_action(req: NewRequest):
    try:
        result = domain_service.perform_action(req.field, req.amount)
        logger.info("Action completed: %s amount=%.2f", req.field, req.amount)
        return NewResponse(status="success", data=result)
    except ValueError as e:
        logger.warning("Validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in new_action")
        raise HTTPException(status_code=500, detail="Internal error")
```

### Adding Business Logic (trading_engine pattern)

```python
def new_business_function(param1: str, param2: float) -> dict:
    """
    Docstring explaining business rules.
    
    Raises:
        ValueError: when input validation fails
        RuntimeError: when system state prevents operation
    """
    # 1. Load current state
    state = store.load_state()
    
    # 2. Validate business rules
    if param2 > state.limit:
        raise ValueError(f"Exceeds limit: {param2} > {state.limit}")
    
    # 3. Perform mutation
    state.field += param2
    
    # 4. Persist
    store.save_state(state)
    
    # 5. Return result (plain dict, route layer wraps in envelope)
    return {"field": state.field, "change": param2}
```

### File Store Thread Safety

```python
from filelock import FileLock

def _write_json_safe(path: Path, data) -> None:
    lock = FileLock(str(path) + ".lock", timeout=5)
    with lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
```

## Frontend Patterns

### Adding a New Page

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";

export default function NewPage() {
  const queryClient = useQueryClient();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ["domain", "list"],
    queryFn: () => api.domain.list(),
    refetchInterval: 5000,
  });

  const mutation = useMutation({
    mutationFn: api.domain.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["domain"] });
    },
    onError: (err) => {
      // Show error toast
    },
  });

  if (isLoading) return <LoadingSkeleton />;
  if (error) return <ErrorDisplay message={error.message} />;

  return (/* JSX */);
}
```

### WebSocket Hook Usage

```tsx
import { useWebSocket } from "../lib/useWebSocket";
import { useAppStore } from "../store/useAppStore";

function LiveComponent() {
  const updatePrice = useAppStore((s) => s.updatePrice);
  
  useWebSocket({
    onTick: (tick) => updatePrice(tick),
    onSnapshot: (snapshot) => useAppStore.getState().setPrices(snapshot),
  });
}
```

### Error Boundary Pattern

```tsx
import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error?: Error; }

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? <div>Something went wrong.</div>;
    }
    return this.props.children;
  }
}
```

## Testing Patterns

### Backend Unit Test

```python
import pytest
from unittest.mock import patch, MagicMock
from backend.trading_engine import buy_option, sell_option
from backend.db.schema import Portfolio, Position


@pytest.fixture
def mock_portfolio():
    return Portfolio(balance=700000.0, initial_balance=700000.0)


@pytest.fixture
def mock_store(mock_portfolio):
    with patch("backend.trading_engine.store") as mock:
        mock.load_portfolio.return_value = mock_portfolio
        mock.load_positions.return_value = []
        mock.find_position.return_value = None
        yield mock


def test_buy_option_deducts_balance(mock_store, mock_portfolio):
    result = buy_option(
        symbol="NIFTY07MAY2524000CE",
        token="12345",
        name="NIFTY",
        strike=24000.0,
        option_type="CE",
        expiry="07MAY2025",
        qty=1,
        price=100.0,
    )
    expected_cost = 1 * 25 * 100.0  # qty * lot_size * price
    assert result["total_cost"] == expected_cost
    assert result["balance"] == 700000.0 - expected_cost


def test_buy_option_insufficient_balance(mock_store, mock_portfolio):
    mock_portfolio.balance = 100.0
    mock_store.load_portfolio.return_value = mock_portfolio
    
    with pytest.raises(ValueError, match="Insufficient balance"):
        buy_option(
            symbol="NIFTY07MAY2524000CE",
            token="12345",
            name="NIFTY",
            strike=24000.0,
            option_type="CE",
            expiry="07MAY2025",
            qty=1,
            price=100.0,
        )
```

### Frontend Component Test

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe("LoginPage", () => {
  it("shows error on failed login", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Invalid credentials" }),
    } as Response);

    renderWithProviders(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });
});
```

## Deployment Checklist

```
- [ ] Pin all Python dependencies with versions
- [ ] Run `npm run build` — zero TypeScript errors
- [ ] Run `eslint .` — zero lint errors
- [ ] All tests pass (`pytest`, `vitest run`)
- [ ] `.env.example` updated with any new variables
- [ ] README updated if setup steps changed
- [ ] No TODO/FIXME/HACK comments left unresolved
- [ ] Logging verified: no secrets in output
- [ ] CORS origins updated for production domain
- [ ] Health endpoint responding at /api/health
```
