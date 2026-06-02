import re

BADWORDS = [
    "kontol", "anjing", "bangsat", "tolol"
]

SPAM_PATTERN = r"(https?://|t\.me/|@)"

def detect_toxic(text: str):
    text = text.lower()
    return any(w in text for w in BADWORDS)

def detect_spam(text: str):
    return bool(re.search(SPAM_PATTERN, text))
