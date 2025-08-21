from fastapi import FastAPI

from app.api.v1.scraping import router as scraping_router

app = FastAPI(title="Restaurant Review Sentiment Analysis API")

# Include routers
app.include_router(scraping_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
