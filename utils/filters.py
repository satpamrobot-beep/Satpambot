import re

def contains_link(text: str):
    if not text:
        return False

    pattern = r"http[s]?://|t\.me/|www\."
    return bool(re.search(pattern, text))
