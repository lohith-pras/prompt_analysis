# Prompt Dashboard Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the repository into a focused prompt-analysis project with a clean Python CLI, a useful README, and a clear path for future Gemini and ChatGPT log integration.

**Architecture:** Keep the dashboard generator as a single Python entry point that accepts a Claude conversations JSON export and writes a standalone HTML dashboard. Treat the notebook as exploratory history, not the primary deliverable, and move user-facing guidance into the README. Keep packaging minimal and remove scaffold noise so the repository clearly communicates its purpose.

**Tech Stack:** Python 3.13, standard library for the CLI, Chart.js in the generated HTML, `uv` for local environment management.

---

### Task 1: Clean the package metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `main.py`

- [ ] **Step 1: Replace scaffold metadata with project-specific metadata**

```toml
[project]
name = "prompt-dashboard"
version = "0.1.0"
description = "Generate an HTML dashboard from Claude, Gemini, and ChatGPT conversation exports"
readme = "README.md"
requires-python = ">=3.13"
dependencies = []
```

- [ ] **Step 2: Replace the placeholder entry point with a thin launcher or remove the placeholder behavior**

```python
from generate_dashboard import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run a quick import check**

Run: `python3 -m py_compile main.py generate_dashboard.py`
Expected: no syntax errors.

### Task 2: Focus the dashboard generator

**Files:**
- Modify: `generate_dashboard.py`

- [ ] **Step 1: Keep the JSON-to-dashboard logic but compute exact summary metrics from the JSON export**

```python
# Exact totals should come from raw human messages, not from averaged values.
```

- [ ] **Step 2: Ensure the script accepts a JSON file path and optional output path**

```python
# Usage:
#   python3 generate_dashboard.py /path/to/conversations.json
#   python3 generate_dashboard.py /path/to/conversations.json /path/to/output.html
```

- [ ] **Step 3: Keep only the dashboard-relevant analysis**

```python
# Keep: total chats, total prompts, total words, averages, filler counts, constraints, top 10 longest chats.
# Remove: notebook-only exploratory sections and unused plotting libraries.
```

- [ ] **Step 4: Run the script against the real export**

Run: `python3 generate_dashboard.py claude/data-*/conversations.json dashboard_generated.html`
Expected: an HTML file is written and the printed summary matches the export size.

### Task 3: Write the root README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a short project overview and screenshot placeholder**

```md
## Dashboard Preview

![Prompt dashboard screenshot](docs/images/prompt-dashboard.png)
```

- [ ] **Step 2: Document how to run the script with a JSON input**

```md
python3 generate_dashboard.py <path_to_conversations.json> [output_file.html]
```

- [ ] **Step 3: Explain the purpose of the project and future integrations**

```md
This project helps analyze prompt patterns from exported conversation logs.
Future work will add Gemini and ChatGPT log support.
It is part of a broader effort to analyze data from services I use, learn behavioral patterns, and potentially build ML feature extraction and training pipelines.
```

- [ ] **Step 4: Add repo structure and quick-start guidance**

```md
- `generate_dashboard.py`: CLI entry point for dashboard generation
- `eda_claude.ipynb`: exploratory notebook that produced the initial analysis
- `prompt_evaluation_metrics.csv`: derived metrics export
```

### Task 4: Add a minimal home for future assets

**Files:**
- Create: `docs/images/.gitkeep`

- [ ] **Step 1: Create the placeholder directory for dashboard screenshots**

```text
# empty file to keep the screenshot directory in git
```

- [ ] **Step 2: Verify the README image path points to a real folder**

Run: `test -d docs/images`
Expected: success.

### Task 5: Validate the cleaned repo

**Files:**
- None

- [ ] **Step 1: Compile the Python files**

Run: `python3 -m py_compile main.py generate_dashboard.py`
Expected: no syntax errors.

- [ ] **Step 2: Generate the dashboard from the actual JSON export**

Run: `python3 generate_dashboard.py claude/data-*/conversations.json dashboard_generated.html`
Expected: dashboard file exists and opens in a browser.

- [ ] **Step 3: Review the README for the user-facing story**

Run: `sed -n '1,220p' README.md`
Expected: overview, screenshot placeholder, usage, roadmap, and repo structure are all present.

- [ ] **Step 4: Commit the cleanup as a small focused change**

```bash
git add README.md pyproject.toml main.py generate_dashboard.py docs/images/.gitkeep
git commit -m "chore: clean up prompt dashboard repo"
```
