from fastapi import FastAPI

from app.settings import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/catalog")
def get_catalog() -> dict[str, list[str]]:
    return {"items": settings.catalog_items}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
