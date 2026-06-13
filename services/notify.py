from aiogram import Bot

# bot instance nanti kita inject dari main.py
bot: Bot | None = None


def set_bot(instance: Bot):
    global bot
    bot = instance


async def send_user_payment(user_id: int, amount: int):
    if not bot:
        return

    try:
        await bot.send_message(
            user_id,
            f"💰 <b>Payment Success</b>\n\n"
            f"Saldo masuk: <b>Rp {amount:,.0f}</b>\n"
            f"Status: <b>SUCCESS</b>",
            parse_mode="HTML"
        )
    except:
        pass
