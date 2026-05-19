import json
import sys
from collections import defaultdict

def process_results(file_path, target_files):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {file_path}.")
        return

    diagnostics = data.get('generalDiagnostics', [])
    filtered = [d for d in diagnostics if any(d.get('file', '').endswith(t) for t in target_files)]

    grouped = defaultdict(list)
    for d in filtered:
        grouped[d['file']].append(d)

    for file, diags in grouped.items():
        print(f"\nFile: {file}")
        # Message -> Rule -> List of lines
        summary = defaultdict(lambda: defaultdict(list))
        for d in diags:
            msg = d.get('message', 'No message')
            rule = d.get('rule', 'No rule')
            line = d.get('range', {}).get('start', {}).get('line', -1) + 1
            summary[msg][rule].append(line)
        
        for msg, rules in summary.items():
            for rule, lines in rules.items():
                if len(lines) > 5:
                    lines_str = f"{lines[0]}-{lines[-1]} ({len(lines)} lines)"
                else:
                    lines_str = ", ".join(map(str, sorted(lines)))
                print(f"  Line(s) {lines_str} | Rule: {rule} | Message: {msg}")

if __name__ == "__main__":
    targets = [
        "src/sattlint/devtools/_ai_work_map_planning.py",
        "src/sattlint/devtools/_ai_work_map_freshness.py"
    ]
    process_results("/home/sqhj/projects/SattLint/pyright_strict_devtools_results.json", targets)
