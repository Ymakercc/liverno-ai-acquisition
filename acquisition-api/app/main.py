"""FastAPI 应用入口。"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import profiles, strategies
from app.config import get_settings
from app.core.errors import AppError

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

# 开发期允许本机前端跨域；生产由反向代理同源处理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """业务异常统一为 {code, message}，前端按 code 判断场景。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.get(f"{settings.api_prefix}/health")
def health() -> dict:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "service": settings.app_name,
            "deepseek_configured": settings.deepseek_configured,
        },
    }


app.include_router(profiles.router, prefix=settings.api_prefix)
app.include_router(strategies.router, prefix=settings.api_prefix)
