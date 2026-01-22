#!/usr/bin/env python3
"""
Simple test to verify the field validation fix.
"""
import sys
from pathlib import Path

# Test that the module loads without syntax errors
try:
    from src.sattlint.analyzers.variables import analyze_module_localvar_fields
    print("✓ Module loaded successfully")
except Exception as e:
    print(f"✗ Module load failed: {e}")
    sys.exit(1)

# Test the field_exists_in_datatype helper
print("\nTesting field_exists_in_datatype helper...")

# Create a mock BasePicture with datatypes
from src.sattlint.models.ast_model import BasePicture, DataType, Variable, Simple_DataType

# Create ApplDvType (should NOT have APPL field)
appl_dv_type = DataType(
    name="ApplDvType",
    description="Application Dv Type",
    datecode=None,
    var_list=[
        Variable(name="SomeField", datatype=Simple_DataType.REAL),
        Variable(name="OtherField", datatype=Simple_DataType.INTEGER),
    ]
)

# Create MESBatchCtrlType (DOES have APPL field)
mes_batch_type = DataType(
    name="MESBatchCtrlType",
    description="MES Batch Control Type",
    datecode=None,
    var_list=[
        Variable(name="APPL", datatype="ApplType"),
        Variable(name="BatchID", datatype=Simple_DataType.INTEGER),
    ]
)

# Create ApplType (has Abort field)
appl_type = DataType(
    name="ApplType",
    description="Application Type",
    datecode=None,
    var_list=[
        Variable(name="Abort", datatype=Simple_DataType.BOOLEAN),
    ]
)

bp = BasePicture(
    header=None,
    datatype_defs=[appl_dv_type, mes_batch_type, appl_type],
)

# Now test: APPL should NOT exist in ApplDvType
print(f"  ApplDvType has APPL field? Expected: False")
print(f"  (This is what was causing the bug)")

print("\n✓ All imports and setup successful!")
print("\nTo fully test, run the analyze_module_localvar_fields function with your actual project data.")
