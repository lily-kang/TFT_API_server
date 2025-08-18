from fastapi import FastAPI
from api.pipeline import router as pipeline_router
from api.analyzer import router as analyzer_router
from utils.logging import setup_logging
from config.settings import settings

# 로깅 초기화
logger = setup_logging()

app = FastAPI(
    title="Text Processing Pipeline API",
    description="텍스트 품질 검수 파이프라인 API - 구문/어휘 수정 자동화 시스템",
    version="1.0.0"
)

# 라우터 등록
app.include_router(pipeline_router)
app.include_router(analyzer_router)


@app.get("/", include_in_schema=False)
async def read_root():
    return {
        "message": "Text Processing Pipeline API가 실행 중입니다.",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "settings": {
            "debug": settings.debug,
            "external_api": settings.external_analyzer_api_url,
            "llm_model": settings.openai_model
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
