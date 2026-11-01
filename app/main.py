"""FastAPI main application for CASHFLOW"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import init_db
from app.middleware.cors import setup_cors
from app.middleware.error_handler import http_exception_handler, general_exception_handler
from app.routers import auth, documents, analysis, ask_cfo, dashboard, settings as settings_router, billflow, portfolio, banking
from app.services.llm_factory import get_embedding_client, get_llm_client
from app.services.mode_service import get_processing_mode
from app.services.embeddings import VectorStore
from app.core.security.keys import load_private_key
from app.core.security.audit_ledger import init_ledger
from app.core.security.mtls import check_mtls_readiness, build_mtls_client
from banking_agent.wecom_bot import get_wecom_bot, is_wecom_available
from pathlib import Path
from datetime import datetime
import logging
import os
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="CASHFLOW API",
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
app.include_router(billflow.router)
app.include_router(portfolio.router)
app.include_router(banking.router)


# Signing key is stored on app.state.signing_private_key at startup.


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting CASHFLOW application...")

    # Create required directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/vector_store", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("app/secrets", exist_ok=True)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Load Ed25519 signing key into memory (encrypted at rest, decrypted here)
    passphrase = os.environ.get("KEY_PASSPHRASE")
    enc_key_path = Path("app/secrets/signing_key.enc")
    if passphrase and enc_key_path.exists():
        try:
            signing_key = load_private_key(passphrase, enc_key_path)
            app.state.signing_private_key = signing_key
            logger.info("Ed25519 signing key loaded into memory")
        except Exception as exc:
            logger.warning(f"Failed to load signing key: {exc}")
            app.state.signing_private_key = None
    else:
        logger.warning(
            "KEY_PASSPHRASE not set or signing_key.enc missing — "
            "banking request signing will be disabled"
        )
        app.state.signing_private_key = None

    # Initialize the tamper-evident decision ledger
    ledger_path = Path("data/banking_decision_ledger.jsonl")
    init_ledger(ledger_path)
    logger.info("Banking decision ledger initialized")

    # Initialize mTLS client for backend->bank channel
    mtls_client = build_mtls_client()
    if mtls_client:
        app.state.mtls_client = mtls_client
        logger.info("mTLS client initialized for backend->bank channel")
    elif check_mtls_readiness():
        app.state.mtls_client = build_mtls_client()
        logger.info("mTLS client initialized for backend->bank channel")
    else:
        logger.warning(
            "mTLS not configured for backend->bank channel. "
            "Set BANK_CLIENT_CERT_PATH, BANK_CLIENT_KEY_PATH, BANK_CA_CERT_PATH "
            "in .env to enable mTLS."
        )
        app.state.mtls_client = None

    # Initialize WeCom bot for IM channel
    wecom_bot = get_wecom_bot()
    if wecom_bot and wecom_bot._bot:
        try:
            await wecom_bot.initialize()
            app.state.wecom_bot = wecom_bot
            logger.info("WeCom bot initialized for IM channel")
            # Start WeCom polling in background
            asyncio.create_task(wecom_bot.start())
        except Exception as exc:
            logger.warning(f"Failed to initialize WeCom bot: {exc}")
            app.state.wecom_bot = None
    else:
        logger.info(
            "WeCom bot not configured. Set WECOM_BOT_ID and WECOM_BOT_SECRET "
            "in .env to enable IM channel."
        )
        app.state.wecom_bot = None

    logger.info("CASHFLOW application started successfully")


@app.on_event("shutdown")
async def shutdown_event(): 
    """Cleanup on shutdown"""
    logger.info("Shutting down CASHFLOW application...")


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
        "message": "CASHFLOW API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
