import os

from dotenv import load_dotenv
from fastapi import FastAPI


load_dotenv()

app = FastAPI(
    title="VR-Based Real-Time Agent API",
    debug=os.getenv("DEBUG", "false").lower() == "true",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
    )
