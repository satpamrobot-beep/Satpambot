import openai

openai.api_key = "API_KEY"

def ai_moderate(text):
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a strict moderation AI."},
            {"role": "user", "content": text}
        ]
    )

    result = response["choices"][0]["message"]["content"]
    return "ALLOW" not in result.upper()
