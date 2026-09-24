import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 Launching E.V Personal Assistant Backend on {settings.HOST}:{settings.PORT}")
    print(f"📖 OpenAPI / Swagger Docs: http://localhost:{settings.PORT}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
