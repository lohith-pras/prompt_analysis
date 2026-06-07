# Prompt Analysis Dashboard

Analyses your exported Claude, Gemini, and ChatGPT conversation logs and generates a single interactive HTML dashboard with stats on your prompting behaviour.

Useful for understanding how you write prompts — filler word frequency, prompt length distribution, constraint patterns, and more.

## What it produces

- Total conversations and messages per model
- Prompt length trends over time
- Filler word usage (`please`, `just`, `could you`, etc.)
- Constraint language frequency (`must`, `never`, `always`, etc.)
- Interactive charts — no server needed, everything is in one HTML file

## Stack

- **Python** 3.13
- **DuckDB** — fast in-process SQL for log querying
- **Anthropic SDK** — optional AI-generated summary of your prompting habits
- **Output:** self-contained HTML (no external dependencies)

## Usage

Export your conversations from Claude (Settings → Export data) then run:

```bash
pip install uv
uv sync
uv run generate_dashboard.py path/to/conversations.json
```

Opens `dashboard_generated.html` in your browser.
