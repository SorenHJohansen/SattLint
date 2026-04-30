import pathlib
import re

p = pathlib.Path("docs/references/cli-commands.md")
t = p.read_bytes().decode("windows-1252")

# Normalize Windows-1252 special chars to Unicode equivalents
t = t.replace("\u2014", " - ")  # em dash -> space-dash-space (already unicode from decode)
t = t.replace("\u2013", "-")  # en dash
t = t.replace("\u0097", " - ")  # raw \x97 if still present
# The \x97 in windows-1252 decodes to U+0097 (control char), not em-dash.
# Actually in cp1252, \x97 = U+2014 (em dash). Let's verify:
# Already converted by decode('windows-1252'), so \x97 -> \u2014
# Replace em-dashes with ' - ' for markdown compatibility
t = t.replace("\u2014", " - ")


# MD032: Add blank lines before lists that immediately follow a paragraph
def add_blank_before_list(text):
    return re.sub(r"(?m)^([^\n\-\*\s#`\|>].+[^:])\n([ \t]*[\-\*] )", r"\1\n\n\2", text)


def add_blank_after_list_before_para(text):
    return re.sub(r"(?m)^([ \t]*[\-\*] [^\n]+)\n([^\n\-\*\s#`\|>\-])", r"\1\n\n\2", text)


prev = None
while prev != t:
    prev = t
    t = add_blank_before_list(t)

prev = None
while prev != t:
    prev = t
    t = add_blank_after_list_before_para(t)

# MD060: Align the exit codes table
old_table = "| Code | Meaning |\n|------|---------|"
new_table = (
    "| Code | Meaning                                    |\n|------|--------------------------------------------|"
)
t = t.replace(old_table, new_table)

# Also pad the data rows to match
t = t.replace("| 0    | Success |", "| 0    | Success                                    |")
t = t.replace(
    "| 1    | Execution error (check output for details) |", "| 1    | Execution error (check output for details) |"
)
t = t.replace("| 2    | Invalid arguments or configuration |", "| 2    | Invalid arguments or configuration        |")

p.write_bytes(t.encode("utf-8"))
print("Done", len(t), "bytes")
print("Encoding: UTF-8 (was windows-1252)")
print("Em-dashes remain:", t.count("\u2014"))
