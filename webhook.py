from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    order_id = data.get("order_id")
    status = data.get("status")
    amount = data.get("amount")

    if status == "paid":
        print("💰 PAYMENT SUCCESS:", order_id, amount)

        # nanti kita sambungkan ke:
        # - wallet
        # - unlock code
        # - database update

    return {"ok": True}
