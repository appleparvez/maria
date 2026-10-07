<div align="center">

# MARIA

### Modular AI Runtime & Intelligent Assistant

*An open-source, modular, personal AI agent platform for Windows and Android.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-brightgreen.svg)](https://python.org)
[![Status: Phase 1](https://img.shields.io/badge/Status-Phase%201%20Foundation-orange.svg)](ROADMAP.md)

</div>

---

## Vision

MARIA is a personal AI assistant that aims to be your intelligent companion on desktop and mobile. Inspired by JARVIS, MARIA is designed to:

- **Converse naturally** in Bangla, Hindi, and English through voice and text.
- **Control your computer** — files, terminal, browser, IDE — with your permission.
- **Use multiple AI providers** — Google Gemini, OpenAI, Claude, OpenRouter, or local models like Ollama — with intelligent model routing.
- **Remember context** across sessions with long-term memory.
- **Work across devices** — Windows PC and Android phone, communicating in real time.
- **Stay secure** — every sensitive action requires human approval.

## Architecture Overview

MARIA follows a **modular, tool-based agent architecture**:

```
┌─────────────────────────────────────────────────┐
│                  Clients                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│   │  Web UI  │  │ Android  │  │  CLI / API   │  │
│   └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
└────────┼─────────────┼───────────────┼──────────┘
         │             │               │
         ▼             ▼               ▼
┌─────────────────────────────────────────────────┐
│              API Gateway (FastAPI)                │
│         REST + WebSocket endpoints               │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌───────────┐ ┌──────────┐ ┌───────────────┐
   │   Agent   │ │ Provider │ │    Tool       │
   │   Core    │ │  Router  │ │   Registry    │
   └─────┬─────┘ └────┬─────┘ └──────┬────────┘
         │            │              │
         ▼            ▼              ▼
   ┌───────────┐ ┌──────────┐ ┌───────────────┐
   │  Memory   │ │ AI APIs  │ │  Tools:       │
   │  System   │ │ (Gemini, │ │  - Files      │
   │ (SQLite+  │ │  OpenAI, │ │  - Terminal   │
   │  Vector)  │ │  Claude, │ │  - Browser    │
   │           │ │  Ollama) │ │  - Git        │
   └───────────┘ └──────────┘ │  - System     │
                              └───────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

## Project Status

🟧 **Phase 1 — Foundation** (current)

See [ROADMAP.md](ROADMAP.md) for the complete phased development plan.

## Security

Security is a core design principle, not an afterthought. See [SECURITY.md](SECURITY.md).

Key principles:
- **Never** store API keys in source code.
- **Never** hard-code credentials.
- **Human confirmation** required for all critical actions.
- **Least-privilege** permission model.
- **BYOK** (Bring Your Own API Key) — your keys stay on your machine.

## Getting Started

> ⚠️ MARIA is in early development (Phase 1). The instructions below will be updated as the project matures.

### Prerequisites

- Python 3.12 or higher
- Git
- Windows 10/11 (primary platform)

### Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/maria.git
cd maria

# Create a virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the environment template
copy .env.example .env
# Edit .env with your API keys

# Run MARIA
python -m maria
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| API Framework | FastAPI |
| Data Validation | Pydantic |
| Real-time | WebSockets |
| Database | SQLite (upgradeable) |
| AI Providers | Gemini, OpenAI, Claude, OpenRouter, Ollama |
| Future: Android | Kotlin / Jetpack Compose |
| Future: Voice | Gemini Live API, Whisper, TTS |

## Contributing

MARIA is open-source and welcomes contributions. Contribution guidelines will be published in Phase 2.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built with purpose. Designed for people.</sub>
</div>
