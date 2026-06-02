from handlers.ai_filter import detect_toxic, detect_spam

if detect_toxic(text):
    await update.message.delete()
    return

if detect_spam(text):
    await update.message.delete()
    return
