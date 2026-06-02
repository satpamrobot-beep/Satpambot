lang_db = {}

translations = {
    "en": {
        "welcome": "Welcome {name}",
        "banned": "User banned"
    },
    "id": {
        "welcome": "Selamat datang {name}",
        "banned": "User diban"
    }
}

def get_lang(chat_id):
    return lang_db.get(chat_id, "en")

def set_lang(chat_id, lang):
    lang_db[chat_id] = lang

def t(chat_id, key, **kwargs):
    lang = get_lang(chat_id)
    text = translations.get(lang, translations["en"]).get(key, key)
    return text.format(**kwargs)
