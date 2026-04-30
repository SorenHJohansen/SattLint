import xml.etree.ElementTree as ET

tree = ET.parse("coverage.xml")
results = []
for cls in tree.findall(".//class"):
    fn = cls.get("filename", "").replace("\\", "/")
    if not fn.startswith("src/"):
        continue
    all_lines = cls.findall("lines/line")
    missed = [line for line in all_lines if line.get("hits") == "0"]
    covered = [line for line in all_lines if line.get("hits") != "0"]
    total = len(missed) + len(covered)
    if total > 0 and missed:
        pct = len(covered) / total * 100
        results.append((pct, len(missed), fn, [line.get("number") for line in missed]))

results.sort(reverse=True)
for pct, n, fn, lines in results[:30]:
    print(f"{pct:.0f}%  {n:4d} missing  {fn}")
