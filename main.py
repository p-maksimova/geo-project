import uvicorn
from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    uvicorn.run(
        "main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
