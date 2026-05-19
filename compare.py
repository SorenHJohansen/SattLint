import re

with open("/home/sqhj/projects/SattLint/pyproject.toml") as f:
    content = f.read()

strict_match = re.search(r"\[tool\.pyright\].*?strict\s*=\s*\[(.*?)\]", content, re.DOTALL)
strict_paths = []
if strict_match:
    strict_paths = [p.strip().strip('"').strip("'") for p in strict_match.group(1).split(",") if p.strip()]

debt_match = re.search(r"\[tool\.sattlint\.typing_ratchet\].*?debt_allowlist\s*=\s*\[(.*?)\]", content, re.DOTALL)
debt_paths = []
if debt_match:
    debt_paths = [p.strip().strip('"').strip("'") for p in debt_match.group(1).split(",") if p.strip()]

present = sorted([p for p in debt_paths if p in strict_paths])
missing = sorted([p for p in debt_paths if p not in strict_paths])

print("1. debt_allowlist entries already present in tool.pyright.strict:")
for p in present:
    print(f"   - {p}")
print("\n2. debt_allowlist entries missing from tool.pyright.strict:")
for p in missing:
    print(f"   - {p}")
print("\n3. Counts:")
print(f"   - Present: {len(present)}")
print(f"   - Missing: {len(missing)}")
