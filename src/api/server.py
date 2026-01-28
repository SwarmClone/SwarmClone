import uvicorn
from fastapi import FastAPI
from api.routers.root import roots

app = FastAPI()
app.include_router(roots)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=4927)
