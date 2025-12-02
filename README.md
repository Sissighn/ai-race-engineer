# AI Race Engineer

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-red)
![FastF1](https://img.shields.io/badge/Data-FastF1-orange)
![License](https://img.shields.io/badge/License-MIT-green)

## Project Overview

AI Race Engineer is a specialized telemetry analysis platform designed to simulate the workflow of a Formula 1 performance engineer. This application bridges the gap between raw data acquisition and actionable motorsport insights by leveraging the FastF1 API.

The project was developed as a comprehensive portfolio piece within the scope of a Business Informatics degree, demonstrating proficiency in data science, software architecture, and full-stack Python development. It emphasizes modular design, separation of concerns, and high-performance data caching.

## Features

### 1. Telemetry & Performance Analysis

- **Corner-Level Granularity:** Algorithms automatically segment track data to calculate time loss and speed deltas for specific corners.
- **Micro-Telemetry:** Visualization of throttle, brake, gear, and speed traces synchronized by track distance.
- **Delta Lap Calculation:** Computation of live time deltas between two drivers to identify dominance areas.

### 2. Algorithmic Coaching Assistant

- **Automated Insights:** A logic engine processes telemetry differentials to generate text-based driving advice.
- **Pattern Recognition:** Identifies specific driver weaknesses, such as early braking points or lower minimum apex speeds compared to a reference lap.

### 3. Session Management & UI

- **Live Data Integration:** Real-time countdowns and result fetching for active Grand Prix sessions.
- **Custom Design System:** Implementation of a bespoke dark theme using external CSS injection to ensure optimal readability in low-light environments.

## Tech Stack

### Core Languages & Frameworks

- **Core:** Python 3.9+
- **Frontend/App Framework:** Streamlit (used for rapid application development and deployment)
- **Styling:** Custom CSS (Externalized for clean code, combined with the Streamlit theming system)

### Data Handling & Analysis

- **Data Source:** FastF1 API (Used to retrieve real-time and historical F1 telemetry and session data)
- **Data Processing:** Pandas, NumPy (For efficient handling and manipulation of large time-series and tabular data)
- **Telemetry Processing:** Custom Python logic (Calculations for time loss and corner segmentation)

### Visualization & Quality

- **Visualization:** Plotly Express / Graph Objects (Used for creating interactive, dynamic, and publication-ready charts like speed traces and bar charts)
- **Code Quality:** Black (Python Code Formatter)

## System Architecture

The project follows a strict separation of concerns, isolating business logic, data retrieval, and user interface components.

```text
AI-RACE-ENGINEER/
├── .streamlit/          # Server configuration (Global Theme & Sidebar settings)
│   └── config.toml
├── app/                 # Frontend Application Layer
│   ├── assets/          # Static assets (External CSS, Images)
│   ├── components/      # Reusable UI modules (Charts, Maps, Navbar)
│   ├── pages/           # Streamlit multipage routing
│   ├── utils/           # Utility functions (UI Loaders, Formatters)
│   └── main.py          # Application entry point
├── src/                 # Business Logic & Backend Layer
│   ├── data/            # Data fetching, caching, and preprocessing
│   └── insights/        # Mathematical engines (Time Loss, Coaching algorithms)
├── cache/               # Local filesystem cache for API responses
├── data/                # Persistent data storage
├── notebooks/           # Jupyter notebooks for exploratory data analysis (EDA)
├── venv/                # Virtual Environment
├── .gitignore           # Git configuration
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

## Technical Highlights

- Modular Architecture: The codebase is split into app/ (Presentation Layer) and src/ (Logic Layer), ensuring that UI changes do not affect data processing algorithms.

- Data Caching: Implements advanced caching strategies to minimize API calls to FastF1 and reduce load times for heavy telemetry datasets.

- Clean Code Standards:

* Adherence to PEP 8 standards using the Black formatter.

* Strict typing (Type Hints) used throughout the backend logic.

* Externalized CSS styling to maintain readable Python code.

## Installation and Usage

- **Prerequisites**

* Python 3.9 or higher
* pip (Python Package Installer)

1. Clone the repository

```Bash
git clone [https://github.com/Sissighn/ai-race-engineer.git](https://github.com/Sissighn/ai-race-engineer.git)
cd ai-race-engineer
```

2. Set up the environment
   It is recommended to use a virtual environment.

```Bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies

```Bash
pip install -r requirements.txt
```

4. Run the application
   Execute the main entry point from the root directory:

```Bash
streamlit run app/main.py
```

## Future Roadmap

- Tyre Degradation Model: Implementation of lap time drop-off analysis to predict optimal pit windows.
- Race Strategy Simulation: Monte Carlo simulation for strategic decision-making.
- Weather Integration: Layering track temperature and wind data onto performance metrics.

## License

MIT License © 2025 Setayesh Golshan
This project is unofficial and not associated in any way with the Formula 1 companies. F1, FORMULA ONE, FORMULA 1, FIA FORMULA ONE WORLD CHAMPIONSHIP, GRAND PRIX and related marks are trade marks of Formula One Licensing B.V.
