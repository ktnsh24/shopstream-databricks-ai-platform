from fastapi import FastAPI
from loguru import logger

from src.routes import alerts, ask, forecast, health, metrics, report, visualize

app = FastAPI(
    title="ShopStream API Gateway",
    description="AI-powered gateway for ShopStream business intelligence queries",
    version="1.0.0",
)

app.include_router(ask.router)
app.include_router(forecast.router)
app.include_router(metrics.router)
app.include_router(health.router)
app.include_router(alerts.router)
app.include_router(report.router)
app.include_router(visualize.router)

logger.info("ShopStream API Gateway started")
