# SIP Monte Carlo Planner

A small personal-finance planning tool that answers one question honestly:
**given your real income, expenses, and SIP, what range of financial futures
are actually plausible for you — not one guessed number, but the full spread?**

Built as a demo project in the same spirit as Monte Carlo–based financial
planning tools: instead of "you'll retire at 58," it shows the median path,
a 1-in-20 bad market, and a 1-in-20 great one — for several asset allocation
mixes, compared fairly using **Common Random Numbers** (every allocation is
tested against the identical simulated market conditions, so differences in
outcome reflect the allocation, not luck).

## Stack

- **Backend:** Python, FastAPI, NumPy (the simulation engine), SQLAlchemy + SQLite
- **Frontend:** plain HTML/CSS/JS, Chart.js (via CDN) — no build step
- **Storage:** SQLite by default; one line to swap to PostgreSQL/MySQL (see `backend/database.py`)

## Running it locally

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
This starts the API at `http://localhost:8000` and auto-creates
`finlaxmi_planner.db` on first run. Interactive API docs are at
`http://localhost:8000/docs`.

**Frontend:**
```bash
cd frontend
python3 -m http.server 5500
```
Then open `http://localhost:5500` in a browser. (The backend must be running
too — the frontend calls `http://localhost:8000` directly.)

## How the simulation works (`backend/simulation.py`)

1. For each of 2,000 simulated futures, draw one random annual return for
   equity, debt, and gold, for every year from your current age to your
   retirement age.
2. **The same 2,000 draws are reused for every allocation mix** (conservative
   30/60/10, balanced 60/30/10, aggressive 80/10/10 — equity/debt/gold). This
   is what makes comparing allocations fair: if "aggressive" comes out ahead,
   it's because it really did better under identical market conditions, not
   because it got a luckier random seed.
3. Each year, the portfolio compounds by the blended return for that
   allocation and adds your annual SIP contribution.
4. We report the 5th/25th/50th/75th/95th percentile of outcomes — both as a
   full year-by-year path (for the fan chart) and as a final number at
   retirement.
5. A separate "lever" analysis holds the market path fixed and only varies
   how much extra you invest each month, showing what that alone is worth in
   final corpus.

The return assumptions (`ASSET_ASSUMPTIONS` in `simulation.py`) are simplified
illustrative figures for a demo, not calibrated to real historical index
data — see "Next steps" below for how to fix that.

## Project structure

```
backend/
  main.py          FastAPI app, request/response models, endpoints
  simulation.py     Monte Carlo engine (pure functions, no framework code)
  database.py       SQLAlchemy models + save/list past runs
  requirements.txt
frontend/
  index.html
  style.css
  script.js
```

## API

| Method | Path              | Purpose                                   |
|--------|-------------------|--------------------------------------------|
| POST   | `/api/simulate`   | Run the simulation for one set of inputs   |
| GET    | `/api/history`    | List past simulation runs                  |
| GET    | `/api/allocations`| The allocation presets used                |
| GET    | `/api/health`      | Health check                              |

## What's implemented so far

- ✅ Custom allocation: a checkbox + equity/gold sliders let a user define
  their own mix (debt is the computed remainder). It's simulated through the
  same market draws as the 3 presets and shown as a 4th tab ("Your mix"), so
  it's directly comparable — not just eyeballed. Validated server-side
  (`CustomAllocation` model in `main.py`) to make sure the weights sum to 1.
- ✅ Loading skeleton: the results panel shows an animated placeholder while
  the 2,000 simulations run, instead of just a disabled button.
- ✅ Inline error banner: request/validation failures (e.g. backend not
  running, retirement age before current age) show in the results panel
  itself, not a browser `alert()`.


