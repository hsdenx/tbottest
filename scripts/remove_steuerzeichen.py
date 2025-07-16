import re
import sys

ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def remove_ansi(text):
    return ansi_escape.sub('', text)

def clean_replacement_chars(text):
    return text.replace('\uFFFD', '')

def clean_windows_m(text):
    return text.replace('\r', '')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'rb') as f:
            raw = f.read()
        decoded = raw.decode('utf-8', errors='replace')
    else:
        raw = sys.stdin.buffer.read()
        decoded = raw.decode('utf-8', errors='replace')

    cleaned = remove_ansi(decoded)
    cleaned = clean_replacement_chars(cleaned)
    cleaned = clean_windows_m(cleaned)
    print(cleaned)

