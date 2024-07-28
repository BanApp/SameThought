from fastapi import FastAPI
from api import account,chat
import uvicorn

app = FastAPI()

app.include_router(account.router)
app.include_router(chat.router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
