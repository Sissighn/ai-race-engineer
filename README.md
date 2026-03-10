# AI Race Engineer

[![CI](https://github.com/Sissighn/ai-race-engineer/actions/workflows/ci.yml/badge.svg)](https://github.com/Sissighn/ai-race-engineer/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31%2B-red)
![FastF1](https://img.shields.io/badge/Data-FastF1-orange)
![Pydantic](https://img.shields.io/badge/Validation-Pydantic-1f6feb)
![Tests](https://img.shields.io/badge/Tests-Pytest-0A9EDC)
![License](https://img.shields.io/badge/License-MIT-green)

AI Race Engineer is a Formula 1 telemetry analysis platform that simulates the workflow of a race/performance engineer. It transforms raw telemetry into corner-level insights, time-loss diagnostics, driver-style profiling, and actionable coaching recommendations.

![Driver Comparison](./docs/4.png)
---

## Current Project Status

This repository now includes:

- Centralized structured logging (`structlog`)
- Standardized domain exceptions and UI-friendly error mapping
- Environment-based configuration (`.env` + settings module)
- Type hints across core modules
- Pydantic schemas for validated payloads
- Automated test suite (`pytest` + `pytest-cov`)
- CI pipeline with GitHub Actions

---

## Key Features

### Telemetry & Performance Analysis

- Corner segmentation and corner-level delta analytics
- Time loss estimation per corner
- Delta lap comparison between two drivers
- Speed, throttle, brake, gear, and track map visualizations

![Driver Comparison](./docs/1.png)
![Driver Comparison](./docs/2.png)
![Driver Comparison](./docs/3.png)

### Coaching & Reporting

- Rule-based driving coaching suggestions
- Driver DNA profiling (aggressiveness, smoothness, etc.)
- Executive race engineer summary report

### Session Management

- FastF1 schedule/session integration
- Dynamic track loading by season
- Local caching support for faster repeated analysis

---

## Tech Stack

- **Language:** Python 3.11+
- **App Framework:** Streamlit
- **Data Source:** FastF1
- **Data/Math:** Pandas, NumPy, SciPy
- **Visualization:** Plotly, Matplotlib
- **Validation:** Pydantic
- **Logging:** structlog
- **Testing:** pytest, pytest-cov

---

## Project Structure

```bash
ai-race-engineer/
├── .github/workflows/      # CI pipeline (GitHub Actions)
├── app/                    # UI layer (Streamlit pages/components)
│   ├── assets/
│   ├── components/
│   ├── pages/
│   ├── utils/
│   └── main.py
├── src/                    # Core logic layer
│   ├── config/             # Settings management
│   ├── data/               # Data loading and preprocessing
│   ├── insights/           # Analysis/report engines
│   ├── logging/            # Logging bootstrap/config
│   ├── models/             # Pydantic schemas
│   └── exceptions.py       # Domain exception hierarchy
├── tests/                  # Unit tests
├── cache/
├── data/
├── notebooks/
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Getting Started

### 1) Clone

```bash
git clone https://github.com/Sissighn/ai-race-engineer.git
cd ai-race-engineer
```

### 2) Create and activate virtual environment

```bash
python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Run the app

```bash
streamlit run app/main.py
```

---

## Testing

Run tests:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=src --cov=app/components --cov-report=term-missing
```

---

## CI/CD (GitHub Actions)

The CI workflow is defined in [.github/workflows/ci.yml](.github/workflows/ci.yml).

It currently performs:

1. Dependency installation
2. Import smoke-check
3. Test execution with coverage and a minimum threshold

Pipeline triggers on pushes and pull requests to `main`.

---

## Configuration

Use environment variables for runtime behavior. See [.env.example](.env.example) if present.

Important settings include:

- `ENVIRONMENT`
- `LOG_LEVEL`
- `FASTF1_CACHE_ENABLED`
- `FASTF1_REQUEST_TIMEOUT`
- `SESSION_CACHE_TTL`
- `TELEMETRY_CACHE_TTL`

---

## License

MIT License © 2026 Setayesh Golshan

This project is unofficial and is not associated with Formula 1. F1, FORMULA ONE, FORMULA 1, FIA FORMULA ONE WORLD CHAMPIONSHIP, GRAND PRIX, and related marks are trademarks of Formula One Licensing B.V.
