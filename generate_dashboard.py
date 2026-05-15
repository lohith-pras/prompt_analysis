#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard from Claude conversations JSON export.

Usage:
    python generate_dashboard.py <path_to_conversations.json> [output_file.html]

Example:
    python generate_dashboard.py claude/data-*/conversations.json
    python generate_dashboard.py conversations.json dashboard.html
"""

import json
import sys
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple


def load_conversations(json_path: str) -> List[Dict]:
    """Load and parse Claude conversations JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON: {e}")
        sys.exit(1)


def extract_metrics(conversations: List[Dict]) -> Dict:
    """Extract key metrics from conversations."""
    filler_pattern = r'\b(please|could you|if you don\'t mind|thanks|thank you|maybe|i think|just|wondering)\b'
    constraint_pattern = r'\b(must|do not|only|strictly|always|never|require|specifically|using)\b'
    
    chat_metrics = []
    total_fillers = 0
    total_constraints = 0
    filler_counter = Counter()
    
    for target_id, conv in enumerate(conversations):
        name = conv.get('name', f'Unnamed_Chat_{target_id}')
        messages = conv.get('chat_messages', [])
        
        human_turns = 0
        total_human_words = 0
        chat_fillers = 0
        chat_constraints = 0
        first_prompt = "N/A"
        
        for msg in messages:
            sender = str(msg.get('sender', '')).capitalize()
            text = msg.get('text', '').strip()
            
            if not text:
                continue
            
            if sender == 'Human':
                if human_turns == 0:
                    clean = text.replace('\n', ' ')
                    first_prompt = clean[:75] + '...' if len(clean) > 75 else clean
                
                human_turns += 1
                total_human_words += len(text.split())
                
                text_lower = text.lower()
                fillers = re.findall(filler_pattern, text_lower)
                constraints = re.findall(constraint_pattern, text_lower)
                
                chat_fillers += len(fillers)
                chat_constraints += len(constraints)
                filler_counter.update(fillers)
        
        if human_turns > 0:
            avg_prompt = total_human_words // human_turns
            total_fillers += chat_fillers
            total_constraints += chat_constraints
            
            chat_metrics.append({
                'target_id': target_id,
                'name': name,
                'turns': human_turns,
                'avg_length': avg_prompt,
                'filler_count': chat_fillers,
                'constraints': chat_constraints,
                'preview': first_prompt
            })
    
    # Get top 10 by turns
    top_10_chats = sorted(chat_metrics, key=lambda x: x['turns'], reverse=True)[:10]
    
    # Calculate global stats
    total_chats = len(chat_metrics)
    total_prompts = sum(c['turns'] for c in chat_metrics)
    total_words = sum(c['avg_length'] * c['turns'] for c in chat_metrics)
    avg_prompt_len = total_words // total_prompts if total_prompts > 0 else 0
    avg_turns = total_prompts / total_chats if total_chats > 0 else 0
    
    return {
        'total_chats': total_chats,
        'total_prompts': total_prompts,
        'total_words': total_words,
        'avg_prompt_length': avg_prompt_len,
        'avg_turns_per_chat': avg_turns,
        'total_fillers': total_fillers,
        'total_constraints': total_constraints,
        'top_fillers': dict(filler_counter.most_common(3)),
        'top_10_chats': top_10_chats
    }


def generate_csv_data(metrics: Dict) -> str:
    """Generate CSV string for embedding in HTML."""
    csv_lines = ['Target_ID,Chat_Name,Total_Turns,Avg_Prompt_Length,Filler_Word_Count,Explicit_Constraints']
    
    for chat in metrics['top_10_chats']:
        csv_lines.append(
            f"{chat['target_id']},{chat['name']},{chat['turns']},{chat['avg_length']},"
            f"{chat['filler_count']},{chat['constraints']}"
        )
    
    return '\n'.join(csv_lines)


def generate_html_dashboard(metrics: Dict) -> str:
    """Generate complete HTML dashboard."""
    
    # Calculate filler distribution
    top_fillers = metrics['top_fillers']
    other_fillers = metrics['total_fillers'] - sum(top_fillers.values())
    
    csv_data = generate_csv_data(metrics)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt Evaluation Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: #3b82f6;
            --secondary: #8b5cf6;
            --accent-warm: #f59e0b;
            --accent-cool: #06b6d4;
            --bg-dark: #0f172a;
            --bg-light: #f8fafc;
            --card-bg: #ffffff;
            --text-dark: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #ef4444;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, var(--bg-light) 0%, #f1f5f9 100%);
            color: var(--text-dark);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}

        .header {{
            margin-bottom: 3rem;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }}

        .header p {{
            color: var(--text-light);
            font-size: 1.1rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}

        .card {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }}

        .card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }}

        .card.stat {{
            text-align: center;
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0.5rem 0;
        }}

        .stat-label {{
            color: var(--text-light);
            font-size: 0.95rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .stat-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .section-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            color: var(--text-dark);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .section-title::before {{
            content: '';
            width: 4px;
            height: 28px;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            border-radius: 2px;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
            margin-bottom: 3rem;
        }}

        .chart-container {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }}

        .chart-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: var(--text-dark);
        }}

        .chart-wrapper {{
            position: relative;
            height: 300px;
        }}

        .table-container {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
            margin-bottom: 3rem;
        }}

        .table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        thead {{
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%);
        }}

        th {{
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            color: var(--text-dark);
            border-bottom: 2px solid var(--border);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }}

        th:hover {{
            background: rgba(59, 130, 246, 0.1);
        }}

        th.sortable::after {{
            content: ' ⇅';
            opacity: 0.5;
            font-size: 0.9rem;
        }}

        th.sorted-asc::after {{
            content: ' ↑';
            opacity: 1;
            color: var(--primary);
        }}

        th.sorted-desc::after {{
            content: ' ↓';
            opacity: 1;
            color: var(--primary);
        }}

        td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border);
            color: var(--text-dark);
        }}

        tbody tr:hover {{
            background: rgba(59, 130, 246, 0.03);
        }}

        .chat-name {{
            font-weight: 500;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .filler-badge {{
            display: inline-block;
            padding: 0.4rem 0.8rem;
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.05));
            color: #92400e;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }}

        .filler-badge.high {{
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(239, 68, 68, 0.05));
            color: #7f1d1d;
            border-color: rgba(239, 68, 68, 0.2);
        }}

        .turns-badge {{
            display: inline-block;
            padding: 0.4rem 0.8rem;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.1), rgba(6, 182, 212, 0.05));
            color: #164e63;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(6, 182, 212, 0.2);
        }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-light);
            font-size: 0.9rem;
            border-top: 1px solid var(--border);
            margin-top: 3rem;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            .header h1 {{
                font-size: 1.8rem;
            }}

            .summary-grid {{
                grid-template-columns: 1fr;
                gap: 1rem;
            }}

            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            .chart-wrapper {{
                height: 250px;
            }}

            table {{
                font-size: 0.9rem;
            }}

            td, th {{
                padding: 0.75rem;
            }}

            .chat-name {{
                max-width: 150px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Prompt Evaluation Dashboard</h1>
            <p>Personal insights into your conversational patterns with Claude</p>
        </div>

        <div class="summary-grid">
            <div class="card stat">
                <div class="stat-icon">💬</div>
                <div class="stat-label">Total Chats</div>
                <div class="stat-value">{metrics['total_chats']}</div>
            </div>
            <div class="card stat">
                <div class="stat-icon">🔤</div>
                <div class="stat-label">Total Prompts</div>
                <div class="stat-value">{metrics['total_prompts']:,}</div>
            </div>
            <div class="card stat">
                <div class="stat-icon">📝</div>
                <div class="stat-label">Total Words</div>
                <div class="stat-value">{metrics['total_words']/1000:.1f}K</div>
            </div>
            <div class="card stat">
                <div class="stat-icon">⏱️</div>
                <div class="stat-label">Avg Prompt</div>
                <div class="stat-value">{metrics['avg_prompt_length']}<span style="font-size: 0.6em;"> words</span></div>
            </div>
            <div class="card stat">
                <div class="stat-icon">🔄</div>
                <div class="stat-label">Avg Turns</div>
                <div class="stat-value">{metrics['avg_turns_per_chat']:.1f}</div>
            </div>
        </div>

        <h2 class="section-title">Habit Patterns</h2>
        <div class="charts-grid">
            <div class="chart-container">
                <h3 class="chart-title">Top Filler Words Usage</h3>
                <div class="chart-wrapper">
                    <canvas id="fillerPieChart"></canvas>
                </div>
            </div>

            <div class="chart-container">
                <h3 class="chart-title">Filler Words vs Explicit Constraints</h3>
                <div class="chart-wrapper">
                    <canvas id="fillerVsConstraintsChart"></canvas>
                </div>
            </div>
        </div>

        <h2 class="section-title">Top 10 Longest Conversations</h2>
        <div class="table-container">
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th class="sortable" data-column="rank">#</th>
                            <th class="sortable" data-column="name">Chat Name</th>
                            <th class="sortable" data-column="turns">Total Turns</th>
                            <th class="sortable" data-column="avg_length">Avg Prompt Length</th>
                            <th class="sortable" data-column="filler">Filler Words</th>
                            <th class="sortable" data-column="constraints">Constraints</th>
                        </tr>
                    </thead>
                    <tbody id="topChatsTable">
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            <p>Dashboard generated from Claude conversations export analysis</p>
            <p style="font-size: 0.85rem; margin-top: 0.5rem; opacity: 0.8;">Data represents {metrics['total_prompts']} prompts across {metrics['total_chats']} conversations</p>
        </div>
    </div>

    <script>
        const csvData = `{csv_data}`;

        function parseCSV(csv) {{
            const lines = csv.trim().split('\\n');
            const headers = lines[0].split(',');
            const data = [];
            
            for (let i = 1; i < lines.length; i++) {{
                const obj = {{}};
                const line = lines[i];
                const regex = /(?:[^,"]|"(?:(?="")|(?!.*?"[^,])|[^"])*")+/g;
                const matches = line.match(regex) || [];
                
                for (let j = 0; j < headers.length; j++) {{
                    let value = matches[j] || '';
                    value = value.trim().replace(/^"|"$/g, '');
                    
                    if (headers[j] === 'Chat_Name') {{
                        obj[headers[j]] = value;
                    }} else {{
                        obj[headers[j]] = isNaN(value) ? value : Number(value);
                    }}
                }}
                
                if (obj.Chat_Name) {{
                    data.push(obj);
                }}
            }}
            return data;
        }}

        const chatData = parseCSV(csvData);

        const ctx1 = document.getElementById('fillerPieChart').getContext('2d');
        new Chart(ctx1, {{
            type: 'doughnut',
            data: {{
                labels: {list(metrics['top_fillers'].keys())},
                datasets: [{{
                    data: {list(metrics['top_fillers'].values()) + [other_fillers]},
                    backgroundColor: [
                        '#f59e0b',
                        '#f97316',
                        '#ef4444',
                        '#fbbf24'
                    ],
                    borderColor: '#ffffff',
                    borderWidth: 3
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            usePointStyle: true,
                            padding: 15,
                            font: {{
                                size: 13,
                                weight: '500'
                            }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {{ size: 14, weight: 'bold' }},
                        bodyFont: {{ size: 13 }},
                        callbacks: {{
                            label: function(context) {{
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = {metrics['total_fillers']};
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${{label}}: ${{value}} (${{percentage}}%)`;
                            }}
                        }}
                    }}
                }}
            }}
        }});

        const ctx2 = document.getElementById('fillerVsConstraintsChart').getContext('2d');
        new Chart(ctx2, {{
            type: 'bar',
            data: {{
                labels: ['Filler Words', 'Explicit Constraints'],
                datasets: [{{
                    label: 'Count',
                    data: [{metrics['total_fillers']}, {metrics['total_constraints']}],
                    backgroundColor: [
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(6, 182, 212, 0.8)'
                    ],
                    borderColor: [
                        '#f59e0b',
                        '#06b6d4'
                    ],
                    borderWidth: 2,
                    borderRadius: 8
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: {{ size: 14, weight: 'bold' }},
                        bodyFont: {{ size: 13 }}
                    }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        max: {max(metrics['total_fillers'], metrics['total_constraints']) + 50},
                        ticks: {{
                            font: {{ size: 12 }}
                        }}
                    }},
                    y: {{
                        ticks: {{
                            font: {{ size: 13, weight: '600' }}
                        }}
                    }}
                }}
            }}
        }});

        function populateTable(data) {{
            const tbody = document.getElementById('topChatsTable');
            tbody.innerHTML = '';
            
            data.forEach((chat, index) => {{
                const fillerClass = chat.Filler_Word_Count > 5 ? 'high' : '';
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${{index + 1}}</td>
                    <td class="chat-name" title="${{chat.Chat_Name}}">${{chat.Chat_Name || '(Unnamed)'}}</td>
                    <td><span class="turns-badge">${{chat.Total_Turns}}</span></td>
                    <td>${{chat.Avg_Prompt_Length}}</td>
                    <td><span class="filler-badge ${{fillerClass}}">${{chat.Filler_Word_Count}}</span></td>
                    <td>${{chat.Explicit_Constraints}}</td>
                `;
                tbody.appendChild(row);
            }});
        }}

        populateTable(chatData);

        document.querySelectorAll('th.sortable').forEach(th => {{
            th.addEventListener('click', function() {{
                const column = this.dataset.column;
                const isAsc = this.classList.contains('sorted-asc');
                
                document.querySelectorAll('th.sortable').forEach(h => {{
                    h.classList.remove('sorted-asc', 'sorted-desc');
                }});
                
                let sortedData;
                if (column === 'turns') {{
                    sortedData = chatData.sort((a, b) => 
                        isAsc ? a.Total_Turns - b.Total_Turns : b.Total_Turns - a.Total_Turns
                    );
                    this.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
                }} else if (column === 'filler') {{
                    sortedData = chatData.sort((a, b) => 
                        isAsc ? a.Filler_Word_Count - b.Filler_Word_Count : b.Filler_Word_Count - a.Filler_Word_Count
                    );
                    this.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
                }} else if (column === 'avg_length') {{
                    sortedData = chatData.sort((a, b) => 
                        isAsc ? a.Avg_Prompt_Length - b.Avg_Prompt_Length : b.Avg_Prompt_Length - a.Avg_Prompt_Length
                    );
                    this.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
                }} else if (column === 'constraints') {{
                    sortedData = chatData.sort((a, b) => 
                        isAsc ? a.Explicit_Constraints - b.Explicit_Constraints : b.Explicit_Constraints - a.Explicit_Constraints
                    );
                    this.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
                }} else if (column === 'name') {{
                    sortedData = chatData.sort((a, b) => 
                        isAsc ? b.Chat_Name.localeCompare(a.Chat_Name) : a.Chat_Name.localeCompare(b.Chat_Name)
                    );
                    this.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');
                }}
                
                populateTable(sortedData);
            }});
        }});
    </script>
</body>
</html>"""
    
    return html


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python generate_dashboard.py <path_to_conversations.json> [output_file.html]")
        print("\nExample:")
        print("  python generate_dashboard.py claude/data-*/conversations.json")
        print("  python generate_dashboard.py conversations.json dashboard.html")
        sys.exit(1)
    
    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "prompt_evaluation_dashboard.html"
    
    print(f"📂 Loading conversations from: {json_path}")
    conversations = load_conversations(json_path)
    print(f"✓ Loaded {len(conversations)} conversations")
    
    print("📊 Extracting metrics...")
    metrics = extract_metrics(conversations)
    
    print(f"✓ Found {metrics['total_chats']} active chats")
    print(f"✓ Processed {metrics['total_prompts']} prompts")
    print(f"✓ Total words: {metrics['total_words']:,}")
    print(f"✓ Filler words: {metrics['total_fillers']} | Constraints: {metrics['total_constraints']}")
    
    print("🎨 Generating HTML dashboard...")
    html = generate_html_dashboard(metrics)
    
    print(f"💾 Saving to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Dashboard created successfully!")
    print(f"📈 Open in browser: file://{Path(output_path).resolve()}")


if __name__ == '__main__':
    main()
