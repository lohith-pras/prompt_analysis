# Prompt Evaluation Dashboard Generator

A Python script that converts Claude conversations JSON export into an interactive HTML dashboard.

## Features

- ✅ Loads Claude conversations JSON export
- ✅ Extracts key metrics: filler words, constraints, conversation patterns
- ✅ Generates standalone HTML dashboard (no external dependencies after generation)
- ✅ Sortable table with top 10 longest conversations
- ✅ Interactive charts (pie & bar charts)
- ✅ Responsive design (works on desktop & mobile)
- ✅ No dependencies required (uses CDN for Chart.js)

## Installation

No external dependencies needed! The script uses only Python standard library:
- `json`, `re`, `sys`, `pathlib`, `collections`

## Usage

### Basic Usage

```bash
python3 generate_dashboard.py <path_to_conversations.json>
```

This will create `prompt_evaluation_dashboard.html` in the current directory.

### Custom Output Path

```bash
python3 generate_dashboard.py <path_to_conversations.json> <output_file.html>
```

### Examples

#### Using glob pattern:
```bash
python3 generate_dashboard.py claude/data-*/conversations.json
```

#### Specifying output file:
```bash
python3 generate_dashboard.py conversations.json my_dashboard.html
```

#### With full paths:
```bash
python3 generate_dashboard.py /Users/lohith/Documents/Data/claude/data-*/conversations.json /Users/lohith/Documents/Data/dashboard.html
```

## Output

The script generates:
- A single self-contained HTML file with embedded CSS and JavaScript
- No external files needed
- Works offline (Chart.js loaded from CDN during generation)

## Dashboard Contents

### Summary Cards
- Total Chats Analyzed
- Total Prompts Sent
- Total Words Written
- Average Prompt Length
- Average Turns per Chat

### Habit Patterns
1. **Pie Chart** - Top filler words distribution
   - Shows which conversational filler words you use most
   - Examples: "just", "please", "maybe"

2. **Bar Chart** - Filler Words vs Explicit Constraints
   - Compares how often you use filler words vs explicit constraints

### Top 10 Conversations Table
- Sortable columns: Chat Name, Total Turns, Avg Prompt Length, Filler Words, Constraints
- Click any column header to sort
- Highlights conversations with high filler word usage

## Metrics Extracted

For each conversation:
- **Total Turns**: Number of human prompts sent
- **Avg Prompt Length**: Average words per prompt
- **Filler Word Count**: Occurrences of common filler words
  - Tracked: "please", "could you", "if you don't mind", "thanks", "thank you", "maybe", "i think", "just", "wondering"
- **Explicit Constraints**: Use of directive language
  - Tracked: "must", "do not", "only", "strictly", "always", "never", "require", "specifically", "using"

## Global Statistics

The dashboard calculates:
- Total number of conversations
- Total number of prompts
- Total words written
- Average metrics across all conversations
- Distribution of habits (filler vs constraints)

## Example Output

```
📂 Loading conversations from: /path/to/conversations.json
✓ Loaded 145 conversations
📊 Extracting metrics...
✓ Found 142 active chats
✓ Processed 1,094 prompts
✓ Total words: 52,300
✓ Filler words: 173 | Constraints: 218
🎨 Generating HTML dashboard...
💾 Saving to: prompt_evaluation_dashboard.html
✅ Dashboard created successfully!
📈 Open in browser: file:///path/to/prompt_evaluation_dashboard.html
```

## Script Logic

1. **Load JSON** - Parse conversations.json
2. **Extract Metrics** - Iterate through messages, extract patterns and stats
3. **Generate HTML** - Create dashboard with embedded metrics
4. **Save File** - Write HTML to disk

## Removing Unnecessary Parts

Compared to the Jupyter notebook analysis, this script:
- ✂️ Removed: exploratory data analysis cells
- ✂️ Removed: correlation matrix calculations
- ✂️ Removed: multiple visualization experiments
- ✂️ Removed: notebook-specific imports (matplotlib, plotly)
- ✂️ Kept: Core metric extraction logic
- ✂️ Kept: Essential visualizations (top fillers, filler vs constraints)
- ✂️ Kept: Top 10 conversations table

Result: **~400 lines of focused Python** instead of sprawling notebook with 50+ cells.

## File Locations

```
/Users/lohith/Documents/Data/
├── generate_dashboard.py          (this script)
├── prompt_evaluation_dashboard.html (example output)
└── claude/data-*/conversations.json (your data source)
```

## Tips

- Run the script after each new Claude export to update your dashboard
- The HTML file can be shared or stored as a backup
- Sort the table by "Filler Words" to find your chattiest conversations
- Sort by "Total Turns" to find extended discussions
