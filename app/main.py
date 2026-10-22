"""FastAPI main application for CFOne"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import init_db
from app.middleware.cors import setup_cors
from app.middleware.error_handler import http_exception_handler, general_exception_handler
from app.routers import auth, documents, analysis, ask_cfo, dashboard, settings as settings_router, wilson, portfolio
from app.services.llm_factory import get_embedding_client, get_llm_client
from app.services.mode_service import get_processing_mode
from app.services.embeddings import VectorStore
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="CFOne API",
    description="AI Chief Financial Officer for small and medium enterprises",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup CORS
setup_cors(app)

# Add exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(ask_cfo.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(wilson.router)
app.include_router(portfolio.router)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting CFOne application...")

    # Create required directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/vector_store", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    logger.info("CFOne application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down CFOne application...")


@app.get("/api/health")
async def health_check():
    """
    Check API health status

    Returns:
        Health status information
    """
    active_mode = get_processing_mode()

    # Check active LLM provider
    llm_status = "unknown"
    try:
        llm_client = get_llm_client(active_mode)
        if llm_client.check_connection():
            llm_status = "connected"
        else:
            llm_status = "disconnected"
    except Exception:
        llm_status = "error"

    # Keep AWS probe for visibility even in local mode
    bedrock_status = "unknown"
    try:
        aws_client = get_llm_client("aws")
        bedrock_status = "connected" if aws_client.check_connection() else "disconnected"
    except Exception:
        bedrock_status = "error"

    ollama_status = "unknown"
    try:
        local_client = get_llm_client("local")
        ollama_status = "connected" if local_client.check_connection() else "disconnected"
    except Exception:
        ollama_status = "error"

    # Check vector store
    vector_store_status = "unknown"
    try:
        embedding_client = get_embedding_client(active_mode)
        vector_store = VectorStore(embedding_client)
        if vector_store.check_connection():
            vector_store_status = "connected"
        else:
            vector_store_status = "disconnected"
    except Exception:
        vector_store_status = "error"

    # Check database
    database_status = "unknown"
    try:
        from app.database import engine

        with engine.connect() as conn:
            database_status = "connected"
    except Exception:
        database_status = "error"

    return JSONResponse(
        content={
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "processing_mode": active_mode,
            "services": {
                "database": database_status,
                "llm": llm_status,
                "aws_bedrock": bedrock_status,
                "ollama": ollama_status,
                "vector_store": vector_store_status,
            },
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CFOne API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
