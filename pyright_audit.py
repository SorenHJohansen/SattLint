import tomllib
import pathlib
import os

def get_tracked_files():
    # 1. Total tracked *.py files (exclude .venv, htmlcov, artifacts, hidden)
    all_py = []
    for path in pathlib.Path('.').rglob('*.py'):
        parts = path.parts
        if '.venv' in parts or 'venv' in parts or 'htmlcov' in parts or 'artifacts' in parts:
            continue
        if any(p.startswith('.') for p in parts if p != '.'):
            continue
        all_py.append(str(path))
    return all_py

def get_src_files():
    # 2. Total src/**/*.py files, excluding src/sattlint.egg-info/**
    src_py = []
    for path in pathlib.Path('src').rglob('*.py'):
        if 'sattlint.egg-info' in path.parts:
            continue
        src_py.append(str(path))
    return src_py

def get_tests_files():
    # 3. Total tests/**/*.py files
    return [str(p) for p in pathlib.Path('tests').rglob('*.py')]

def get_scripts_files():
    # 4. Total scripts/**/*.py files
    return [str(p) for p in pathlib.Path('scripts').rglob('*.py')]

def parse_pyproject():
    with open('pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
    pyright_cfg = data.get('tool', {}).get('pyright', {})
    include = pyright_cfg.get('include', [])
    mode = pyright_cfg.get('typeCheckingMode', 'standard')
    strict_list = pyright_cfg.get('strict', [])
    return include, mode, strict_list

def main():
    all_py = get_tracked_files()
    src_py = get_src_files()
    tests_py = get_tests_files()
    scripts_py = get_scripts_files()
    
    include, mode, strict_list = parse_pyproject()
    
    print(f"1. Total tracked .py files: {len(all_py)}")
    print(f"2. Total src/**/*.py files: {len(src_py)}")
    print(f"3. Total tests/**/*.py files: {len(tests_py)}")
    print(f"4. Total scripts/**/*.py files: {len(scripts_py)}")
    print(f"5. pyproject.toml pyright config:")
    print(f"   - include: {include}")
    print(f"   - typeCheckingMode: {mode}")
    print(f"   - strict count: {len(strict_list)}")
    
    # 6. Compare strict against src
    src_set = set(src_py)
    strict_set = set(strict_list)
    missing_in_strict = sorted([f for f in src_py if f not in strict_set])
    
    print(f"\n6. src/ files NOT in strict list:")
    for f in missing_in_strict:
        print(f"   - {f}")
        
    # 7. Strict entries that don't exist
    non_existent_strict = sorted([f for f in strict_list if not os.path.exists(f)])
    print(f"\n7. Strict entries that do not exist:")
    for f in non_existent_strict:
        print(f"   - {f}")

if __name__ == '__main__':
    main()
