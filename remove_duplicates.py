#!/usr/bin/env python3
"""
Remove duplicate test cases from the test suite

Based on comprehensive duplicate analysis, this script removes 5 duplicate test cases:
- Index 49: "Tell me about NIREL DIGITALS" (memory_sequence_3a)
- Index 52: "Show me invoices with sticker products" (memory_sequence_5a)  
- Index 56: "Do we have invoices from NIREL DIGITALS?" (existence_positive)
- Index 59: "Are there any invoices with GSTIN 36ARKPC6820F1ZZ?" (existence_positive)
- Index 62: "Show me all invoices from NIREL DIGITALS" (list_all)

This reduces test runtime by ~7.5 minutes (104 → 99 tests).
"""

import json
from pathlib import Path

def remove_duplicates():
    test_file = Path("invoice-extraction-current/rag/test_suite_extended.py")
    
    # Read the current file
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔄 REMOVING DUPLICATE TEST CASES")
    print("="*50)
    
    # Parse the file to find TEST_CASES 
    import ast
    import re
    
    # Extract the TEST_CASES list from the file
    # Find the start of TEST_CASES
    start_pattern = r'TEST_CASES:\s*List\[.*?\]\s*=\s*\['
    end_pattern = r'^\]'
    
    lines = content.split('\n')
    start_line = None
    end_line = None
    
    for i, line in enumerate(lines):
        if 'TEST_CASES:' in line and '[' in line:
            start_line = i
        elif start_line is not None and line.strip() == ']' and 'TEST_CASES' in lines[max(0, i-50):i+1]:
            end_line = i
            break
    
    if start_line is None or end_line is None:
        print("❌ Could not find TEST_CASES list boundaries")
        return False
    
    print(f"📍 Found TEST_CASES list: lines {start_line} to {end_line}")
    
    # Parse the test cases to identify which to remove
    test_cases_content = '\n'.join(lines[start_line:end_line+1])
    
    # Load the module to get the actual TEST_CASES
    import sys
    sys.path.insert(0, str(Path("invoice-extraction-current").resolve()))
    
    try:
        from rag.test_suite_extended import TEST_CASES
        print(f"✅ Loaded {len(TEST_CASES)} test cases")
    except Exception as e:
        print(f"❌ Error loading test cases: {e}")
        return False
    
    # Identify duplicates by exact question match
    duplicates_to_remove = [
        "Tell me about NIREL DIGITALS",
        "Show me invoices with sticker products", 
        "Do we have invoices from NIREL DIGITALS?",
        "Are there any invoices with GSTIN 36ARKPC6820F1ZZ?",
        "Show me all invoices from NIREL DIGITALS"
    ]
    
    # Find indices of duplicates
    indices_to_remove = []
    for i, test_case in enumerate(TEST_CASES):
        question = test_case.get("question", "")
        if question in duplicates_to_remove:
            indices_to_remove.append(i)
            print(f"🎯 Found duplicate #{i}: {question}")
    
    print(f"\n📊 Analysis:")
    print(f"  Original test count: {len(TEST_CASES)}")
    print(f"  Duplicates to remove: {len(indices_to_remove)}")
    print(f"  New test count: {len(TEST_CASES) - len(indices_to_remove)}")
    print(f"  Time savings: ~{len(indices_to_remove) * 1.5:.1f} minutes")
    
    if len(indices_to_remove) != 5:
        print(f"⚠️  Warning: Expected 5 duplicates, found {len(indices_to_remove)}")
        print("  Proceeding anyway...")
    
    # Create new test cases list without duplicates
    new_test_cases = []
    removed_questions = []
    
    for i, test_case in enumerate(TEST_CASES):
        if i in indices_to_remove:
            removed_questions.append(test_case["question"])
            print(f"  ❌ Removing index {i}: {test_case['question']}")
        else:
            new_test_cases.append(test_case)
    
    print(f"\n✅ Removed {len(removed_questions)} duplicate test cases")
    print(f"✅ Final test suite size: {len(new_test_cases)} tests")
    
    # Now reconstruct the file content with the new list
    # We'll build a new TEST_CASES string representation
    def format_test_case(tc, indent=4):
        """Format a test case as Python dict string"""
        spaces = " " * indent
        lines = [f"{spaces}{{"]
        for key, value in tc.items():
            if isinstance(value, str):
                lines.append(f'{spaces}    "{key}": "{value}",')
            elif isinstance(value, list):
                if value:
                    if all(isinstance(v, str) for v in value):
                        value_str = '["' + '", "'.join(value) + '"]'
                    else:
                        value_str = str(value)
                else:
                    value_str = "[]"
                lines.append(f'{spaces}    "{key}": {value_str},')
            elif value is None:
                lines.append(f'{spaces}    "{key}": None,')
            else:
                lines.append(f'{spaces}    "{key}": {value},')
        lines.append(f"{spaces}}},")
        return '\n'.join(lines)
    
    # Build new TEST_CASES string
    new_content_lines = lines[:start_line]
    new_content_lines.append('TEST_CASES: List[Dict[str, Any]] = [')
    
    for test_case in new_test_cases:
        new_content_lines.extend(format_test_case(test_case).split('\n'))
    
    new_content_lines.append(']')
    new_content_lines.extend(lines[end_line+1:])
    
    # Update the docstring count
    for i, line in enumerate(new_content_lines):
        if 'Extended RAG Evaluation Test Suite —' in line and 'test cases' in line:
            new_content_lines[i] = f'Extended RAG Evaluation Test Suite — {len(new_test_cases)} test cases'
            break
    
    # Write the modified file
    new_content = '\n'.join(new_content_lines)
    
    # Create backup
    backup_file = test_file.with_suffix('.py.backup')
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Created backup: {backup_file}")
    
    # Write new version
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Updated {test_file}")
    print(f"📦 Backup saved as {backup_file}")
    
    print(f"\n🎉 DUPLICATE REMOVAL COMPLETE")
    print(f"   Tests reduced: {len(TEST_CASES)} → {len(new_test_cases)} (-{len(indices_to_remove)})")
    print(f"   Time saved: ~{len(indices_to_remove) * 1.5:.1f} minutes")
    print(f"   Runtime: ~{len(TEST_CASES) * 1.5:.1f} min → ~{len(new_test_cases) * 1.5:.1f} min")
    
    return True

if __name__ == "__main__":
    success = remove_duplicates()
    exit(0 if success else 1)