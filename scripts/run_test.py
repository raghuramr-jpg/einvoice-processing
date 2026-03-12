import traceback
import sys
import codecs

try:
    with open('scripts/test_val_agent.py', 'r', encoding='utf-8') as f:
        code = f.read()
    exec(code)
except Exception as e:
    with codecs.open('test_output.txt', 'w', 'utf-8') as out:
        traceback.print_exc(file=out)
