#!/usr/bin/env python3
import subprocess
import sys

# Run the test script
result = subprocess.run([sys.executable, "test_line_item_search.py"], 
                       cwd='C:\\Users\\kmgs4\\Documents\\Christ Uni\\invoice-extraction',
                       capture_output=True,
                       text=True)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print("Return code:", result.returncode)
