## Lottery Analysis Project Handoff

Last updated: 2026-04-01
Repo: https://github.com/2klips/lottery_analysis
Branch: `master`
Latest code commit before this handoff document: `54c8a95` (`fix: use 308 real rounds only, remove incorrect 6-set collection`)

---

## 1. Project goal

This project collects **Korean Pension Lottery 720+** historical data from `https://www.dhlottery.co.kr`, stores it locally, analyzes the history, and generates several prediction reports.

Important domain rule:

- **There is exactly ONE 1st-prize winning number per round**.
- Example: round 308 → `5조 920388`
- 2nd prize = same 6 digits with a different group (`조`)
- 3rd~7th prizes = trailing-digit matches derived from 1st prize
- Bonus = one separate 6-digit bonus number

This rule matters because there was a temporary incorrect implementation that treated API detail rows like multiple 1st-prize sets. That has been corrected. Current analysis/prediction commands use **only the real 308 rounds** from `pension_rounds`.

---

## 2. Current verified state

### Git / branch

- Working branch: `master`
- Remote: `origin/master`
- Status at handoff: clean and pushed

### Test status

- Latest local verification: `50 passed`
- Command:

```powershell
python -m pytest tests/ -q
```

### Database state

Current local database file:

- `data/lottery.db`

Current known counts:

- `pension_rounds`: **308**
- `pension_round_sets`: **3318** (legacy/incorrect experimental table; currently **not used** by main analysis commands)

Important:

- Main commands now use `db.get_all_rounds()`.
- Do **not** switch analysis/prediction back to `get_all_round_sets()` unless the data model is redesigned correctly.

---

## 3. What has been implemented so far

### Core collection / storage

- `src/collector/fetcher.py`
  - Fetches latest round and round list from DHLottery API/site
  - Handles retry / rate limiting / session reuse
- `src/collector/parser.py`
  - Parses round list JSON and main page latest round
- `src/models/lottery.py`
  - `PensionRound` dataclass
- `src/storage/database.py`
  - SQLite storage for `pension_rounds`
  - progress tracking and JSON export

### Analysis / prediction modules

- `src/analysis/statistics.py`
  - frequency, hot/cold, gap, temporal stats
- `src/analysis/predictor.py`
  - baseline multi-strategy predictor
- `src/analysis/prediction_report.py`
  - user-friendly comprehensive prediction report
  - includes strategy reasoning, bonus probability summary, and backtest summary
- `src/analysis/backtester.py`
  - walk-forward backtest engine
- `src/analysis/markov.py`
  - Markov chain predictor
- `src/analysis/monte_carlo.py`
  - Monte Carlo simulation
- `src/analysis/lstm_predictor.py`
  - MLP-based neural predictor (named LSTM predictor, but implemented with sklearn MLP)
- `src/analysis/advanced_stats.py`
  - entropy, cross-position correlation, autocorrelation, seasonal bias, trend proxy
- `src/analysis/bayesian.py`
  - Dirichlet/Multinomial Bayesian predictor
- `src/analysis/feature_engine.py`
  - feature engineering + dynamic ensemble weighting

### Interface / automation

- `main.py`
  - CLI entrypoint
- `dashboard.py`
  - Streamlit dashboard
- `schedule_task.py`
  - Windows Task Scheduler helper

### Quality / tooling

- `.pre-commit-config.yaml`
- `pyproject.toml`
- test suite with 50 tests

---

## 4. Commands that currently work

### Setup

Recommended on a new PC:

```powershell
git clone https://github.com/2klips/lottery_analysis.git
cd lottery_analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install -e ".[dev]"
pip install -e ".[ml]"
pip install -e ".[dashboard]"
```

If editable install fails, fallback:

```powershell
pip install requests beautifulsoup4 lxml scikit-learn streamlit pandas pytest black ruff mypy pre-commit
```

### Main commands

```powershell
python main.py collect
python main.py analyze
python main.py predict
python main.py backtest
python main.py markov
python main.py montecarlo
python main.py neural
python main.py advanced
python main.py bayesian
python main.py ensemble
python main.py export
python main.py dashboard
```

### Test / verification

```powershell
python -m pytest tests/ -q
python -m py_compile main.py
```

---

## 5. Files an agent should read first

If another agent continues work, start here:

1. `main.py`
2. `src/models/lottery.py`
3. `src/storage/database.py`
4. `src/analysis/prediction_report.py`
5. `src/analysis/predictor.py`
6. `src/analysis/backtester.py`
7. `src/analysis/advanced_stats.py`
8. `tests/test_predictor.py`
9. `tests/test_statistics.py`

---

## 6. Important historical decisions / pitfalls

### Corrected misunderstanding: 6-set collection

There was a mistaken interpretation of the detail API response:

- Wrong assumption: one round has multiple independent 1st-prize sets
- Correct interpretation: one round has one 1st-prize number, and detail rows represent lower prize derivations / bonus-related rows

Result:

- `pension_round_sets` table exists but is **legacy experimental data**
- Current code has been fixed so all analysis commands use **308 real rounds only**

If you continue development, be careful not to reintroduce this mistake.

### Prediction output was improved recently

`python main.py predict` now shows:

- final ensemble prediction
- detailed explanation for each strategy
- bonus number top probabilities by position
- recent 50-round walk-forward backtest summary

### ARIMA note

`advanced_stats.py` includes a trend proxy rather than full ARIMA, because the implementation was kept stdlib-only / lightweight.

### Neural note

`lstm_predictor.py` is actually based on `sklearn.neural_network.MLPClassifier`, not a true TensorFlow/PyTorch LSTM.

---

## 7. Recent commit history summary

Recent commits:

```text
54c8a95 fix: use 308 real rounds only, remove incorrect 6-set collection
e6499b6 feat: comprehensive prediction report with per-strategy reasoning and backtest
706ae1c feat: add 6-set collection, advanced analysis, Bayesian predictor, dynamic ensemble
53ca948 feat: add prediction models, backtester, dashboard, and expanded tests
5a08ffd feat: implement pension lottery 720+ data collection and prediction system
```

Interpretation:

- `706ae1c` introduced useful advanced analysis modules **but also the mistaken 6-set collection idea**
- `54c8a95` is the fix that restores correct 308-round usage
- When understanding current behavior, trust **HEAD** over older commits

---

## 8. Recommended next tasks

Good next tasks for another agent:

1. **Clean up legacy experimental artifacts**
   - Decide whether to remove `pension_round_sets` entirely or keep it as unused legacy code
   - If keeping it, clearly mark it deprecated in code/comments/docs

2. **Add dedicated tests for newer modules**
   - `prediction_report.py`
   - `advanced_stats.py`
   - `bayesian.py`
   - `feature_engine.py`
   - `backtester.py`, `markov.py`, `monte_carlo.py`, `lstm_predictor.py`

3. **Normalize main.py formatting**
   - Functions are currently dense and could use cleanup/formatting for readability

4. **Validate prediction assumptions with domain knowledge**
   - Re-check all prize / bonus handling directly against official rules
   - Verify that bonus prediction logic matches real lottery semantics

5. **Improve docs for end users**
   - Add README usage examples
   - Document what each prediction model means and its limitations

---

## 9. Quick start for another PC / another agent

Minimum workflow to continue immediately:

```powershell
git clone https://github.com/2klips/lottery_analysis.git
cd lottery_analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install -e ".[dev]"
pip install -e ".[ml]"
pip install -e ".[dashboard]"
python -m pytest tests/ -q
python main.py predict
```

If the above works, the environment is ready and the next agent can continue immediately.

---

## 10. Single-sentence truth of the project right now

This project is a working Pension Lottery 720+ historical collection and multi-model prediction toolkit based on **308 real rounds**, with prediction reporting and several experimental analysis modules already implemented, but it still needs cleanup around legacy experimental code and more tests for newer modules.
