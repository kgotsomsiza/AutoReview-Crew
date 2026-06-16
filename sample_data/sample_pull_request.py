"""A tiny pretend 'pull request' for the crew to review in the demo.

In the real build you'll fetch this from a GitHub PR or read a .diff file. For now
it's just a string so you can run the whole flow without any setup. It contains
two planted problems (a hardcoded secret and a division-by-zero) so the reviewers
have something to find.
"""

SAMPLE_DIFF = '''
# calc.py  (new file)
API_KEY = "sk-live-1234567890abcdef"   # <-- hardcoded secret

def average(items):
    total = 0
    for x in items:
        total += x
    return total / len(items)          # <-- crashes on an empty list
'''
