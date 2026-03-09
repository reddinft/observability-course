# 🔭 Observability Engineering Course

A hands-on, practitioner-focused course on modern observability engineering — covering the three pillars (logs, metrics, traces), OpenTelemetry as the universal standard, and a deep dive into **Langfuse** as a production-grade LLM observability platform.

## 🎯 What You'll Learn

- **Module 01:** The Three Pillars of Observability
- **Module 02:** OpenTelemetry: The Universal Standard
- **Module 03:** Instrumenting Real Applications
- **Module 04:** Metrics: Prometheus & Grafana
- **Module 05:** Distributed Tracing: Tempo & Jaeger
- **Module 06:** LLM Observability: Why It's Different
- **Module 07:** Langfuse Deep Dive: Architecture & SDK
- **Module 08:** Langfuse in Production: SandSync Case Study
- **Module 09:** Synthetic Datasets: Generation & Usage
- **Module 10:** Production Readiness & Best Practices

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/reddinft/observability-course.git
cd observability-course

# Build and run with Docker Compose
docker compose up

# Open http://localhost:8080
```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
export DB_PATH=/tmp/progress.db
uvicorn app.main:app --reload --port 8080

# Open http://localhost:8080
```

## 📚 Course Features

- **Free & Open Access** — No authentication required
- **Progress Tracking** — Mark lessons as complete, track your progress
- **Interactive Quizzes** — Module-based assessments with instant feedback
- **Real Code Examples** — Reference implementation from SandSync hackathon
- **Dark Theme** — Observatory aesthetic with amber accents
- **Responsive Design** — Works on desktop and mobile

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.12) |
| Frontend | HTMX + Jinja2 |
| Styling | Custom CSS (Observatory theme) |
| Progress DB | SQLite (aiosqlite) |
| Content | Markdown files |
| Hosting | Fly.io (syd region) |
| Syntax Highlighting | Highlight.js (CDN) |
| Diagrams | Mermaid.js (CDN) |

## 📁 Repository Structure

```
observability-course/
├── app/
│   ├── main.py              # FastAPI application
│   ├── content.py           # Markdown parser & loader
│   ├── database.py          # SQLite progress tracking
│   ├── analytics.py         # Analytics middleware
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
├── course/                  # Course content modules
│   ├── module-01-*/
│   ├── module-02-*/
│   └── ... (10 modules total)
├── scripts/                 # Utility scripts
├── sample_data/             # Sample datasets
├── Dockerfile
├── docker-compose.yml
├── fly.toml
├── requirements.txt
└── README.md
```

## 🔄 Development Workflow

### Adding a Lesson

1. Create a markdown file in the appropriate module: `course/module-XX-*/lesson-slug.md`
2. Update the module's `meta.yaml` with lesson metadata
3. Run the app and navigate to the lesson

### Updating Quizzes

1. Edit the module's `quiz.yaml` file
2. Add questions with multiple-choice options
3. Quizzes are validated and scored automatically

### Styling

- Colors and theme are defined in `app/static/style.css`
- Observatory dark theme with amber (#f0a500) and green (#238636) accents
- JetBrains Mono for code, Inter for body text

## 🚢 Deployment

### Deploy to Fly.io

```bash
# Prerequisites
brew install flyctl
flyctl auth login

# Deploy
flyctl deploy --app observability-course

# View logs
flyctl logs -a observability-course
```

### Environment Variables

- `DB_PATH` — SQLite database path (default: `/data/progress.db`)

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Homepage with module list |
| `/module/{id}` | GET | Module overview page |
| `/module/{id}/lesson/{slug}` | GET | Lesson content page |
| `/progress/toggle` | POST | Toggle lesson completion (HTMX) |
| `/module/{id}/quiz` | GET | Quiz page |
| `/module/{id}/quiz` | POST | Submit quiz answers |
| `/api/progress` | GET | Get all progress (JSON) |
| `/health` | GET | Health check |

## 📝 License

This course is open-source and available under the MIT License.

## 👥 Contributors

- **Benjamin Locutus Dookeran** (Loki) — Engineering & Architecture
- **Sara** — Content Writing
- **Archie** — Research
- **Nissan Dookeran** — Vision & Oversight

## 🔗 Links

- **Live:** https://observability-course.fly.dev
- **GitHub:** https://github.com/reddinft/observability-course
- **Issues:** https://github.com/reddinft/observability-course/issues

---

_Made with ❤️ for practitioners who want to understand observability deeply._
