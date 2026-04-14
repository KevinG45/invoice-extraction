import re

gstin = '36ARKPC6820F1ZZ'
pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b'

print(f'GSTIN: {gstin}')
print(f'Pattern: {pattern}')

match = re.search(pattern, gstin.upper())
print(f'Match: {match.group(0) if match else "No match"}')

# Let's also test the query format
query = "Find the invoice with GSTIN 36ARKPC6820F1ZZ"
match_in_query = re.search(pattern, query.upper())
print(f'Query: {query}')
print(f'Match in query: {match_in_query.group(0) if match_in_query else "No match"}')

# Let's debug the GSTIN format
print(f'GSTIN breakdown:')
print(f'  36 (digits): {gstin[:2]}')
print(f'  ARKPC (5 letters): {gstin[2:7]}') 
print(f'  6820 (4 digits): {gstin[7:11]}')
print(f'  F (letter): {gstin[11]}')
print(f'  1 (digit): {gstin[12]}')
print(f'  Z (Z): {gstin[13]}')
print(f'  Z (letter/digit): {gstin[14]}')