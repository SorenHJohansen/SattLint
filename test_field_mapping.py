#!/usr/bin/env python3
"""
Test the updated field path mapping logic.
Verifies that only the last component of a dotted path is used as the prefix.
"""

# Test case: Dv.I.WT001 -> Signal
# Expected: Signal.Value should become WT001.Value

source_path = "Dv.I.WT001"
# Extract last component
last_component = source_path.split(".")[-1] if "." in source_path else ""
print(f"Source: {source_path}")
print(f"Last component (mapping name): {last_component}")
print(f"Expected: WT001")
print(f"Match: {last_component == 'WT001'}")

# Test case: Signal.Value field access
field_path = "Value"
field_prefix = last_component

if field_prefix and field_path:
    full_field_path = f"{field_prefix}.{field_path}"
elif field_prefix:
    full_field_path = field_prefix
else:
    full_field_path = field_path

print(f"\nField accessed on Signal: {field_path}")
print(f"Reconstructed field on Dv: {full_field_path}")
print(f"Expected: WT001.Value")
print(f"Match: {full_field_path == 'WT001.Value'}")

# Test with deeper nesting
print("\n" + "="*50)
print("Testing deeper nesting:")
source_path2 = "Dv.A.B.C.D.WT002"
last_component2 = source_path2.split(".")[-1]
print(f"Source: {source_path2}")
print(f"Last component: {last_component2}")
print(f"Expected: WT002")
print(f"Match: {last_component2 == 'WT002'}")

# Reconstruct
field_accessed = "Status.Code"
if last_component2 and field_accessed:
    reconstructed = f"{last_component2}.{field_accessed}"
print(f"Field accessed: {field_accessed}")
print(f"Reconstructed: {reconstructed}")
print(f"Expected: WT002.Status.Code")
print(f"Match: {reconstructed == 'WT002.Status.Code'}")
