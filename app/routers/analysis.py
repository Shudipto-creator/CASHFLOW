"""Analysis API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.services.nova_client import NovaClient
from app.services.embeddings import VectorStore
from app.agents.financial_analyzer import FinancialAnalyzer
from app.agents.cashflow_forecaster import CashFlowForecaster
from app.agents.risk_detector import RiskDetector
from app.agents.automation_agent import AutomationAgent
from app.agents.explainability_agent import ExplainabilityAgent
from app.utils.pdf_parser import extract_text_from_pdf
from app.utils.excel_parser import extract_data_from_excel
from app.utils.financial_metrics import compute_loan_readiness_score
from datetime import datetime, timedelta
from typing import List, Optional
import logging
import os
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def process_analysis(analysis_id: str, document_ids: List[str], db_path: str):
    """
    Background task to process analysis

    Args:
        analysis_id: Analysis ID
        document_ids: List of document IDs to analyze
        db_path: Database connection string
    """
    # Create new database session for background task
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_path, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        logger.info(f"Starting analysis processing: {analysis_id}")

        # Get analysis record
        analysis = db.query(models.Analysis).filter(models.Analysis.analysis_id == analysis_id).first()

        if not analysis:
            logger.error(f"Analysis not found: {analysis_id}")
            return

        # Get documents
        documents = db.query(models.Document).filter(models.Document.document_id.in_(document_ids)).all()

        if not documents:
            analysis.status = "failed"
            analysis.error_message = "No documents found"
            db.commit()
            return

        # Initialize services
        nova_client = NovaClient()
        vector_store = VectorStore(nova_client)

        # Extract and process documents
        all_text = []
        doc_types = []

        for doc in documents:
            try:
                # Check if file exists
                if not os.path.exists(doc.file_path):
                    logger.warning(f"File not found: {doc.file_path}")
                    continue

                # Parse document based on type
                if doc.filename.endswith(".pdf"):
                    parsed_data = extract_text_from_pdf(doc.file_path)

                    if "error" in parsed_data:
                        logger.warning(f"PDF parsing error: {parsed_data['error']}")
                        continue

                    all_text.append(parsed_data.get("text", ""))
                    doc.doc_metadata = {"page_count": parsed_data.get("page_count"), "tables": len(parsed_data.get("tables", []))}

                elif doc.filename.endswith((".xlsx", ".xls")):
                    parsed_data = extract_data_from_excel(doc.file_path)

                    if "error" in parsed_data:
                        logger.warning(f"Excel parsing error: {parsed_data['error']}")
                        continue

                    # Convert Excel data to text
                    excel_text = json.dumps(parsed_data.get("sheets", []), indent=2)
                    all_text.append(excel_text)
                    doc.doc_metadata = parsed_data.get("metadata", {})

                doc_types.append(doc.document_type or "financial_document")
                doc.processed = True

                # Add to vector store
                metadata = {"document_id": doc.document_id, "user_id": doc.user_id, "filename": doc.filename}

                vector_store.add_document(doc.document_id, all_text[-1] if all_text else "", metadata)

            except Exception as e:
                logger.error(f"Error processing document {doc.document_id}: {str(e)}")

        db.commit()

        if not all_text:
            analysis.status = "failed"
            analysis.error_message = "No text extracted from documents"
            db.commit()
            return

        # Combine all document text
        combined_text = "\n\n".join(all_text)

        # Initialize agents
        agent1 = FinancialAnalyzer(nova_client)
        agent2 = CashFlowForecaster(nova_client)
        agent3 = RiskDetector(nova_client)
        agent4 = AutomationAgent(nova_client)
        agent5 = ExplainabilityAgent(nova_client)

        # Execute agents sequentially
        logger.info("Executing Agent 1: Financial Analyzer")
        context1 = {"documents_text": combined_text, "document_types": doc_types}

        result1 = agent1.execute(context1)

        # Store Agent 1 result
        agent_result_1 = models.AgentResult(
            analysis_id=analysis_id, agent_name="Financial Analyzer", result_data=result1, execution_time_ms=1000
        )
        db.add(agent_result_1)
        db.commit()

        logger.info("Executing Agent 2: Cash Flow Forecaster")
        context2 = {"financial_data": result1}

        result2 = agent2.execute(context2)

        # Store Agent 2 result
        agent_result_2 = models.AgentResult(
            analysis_id=analysis_id, agent_name="Cash Flow Forecaster", result_data=result2, execution_time_ms=1000
        )
        db.add(agent_result_2)
        db.commit()

        logger.info("Executing Agent 3: Risk Detector")
        context3 = {"financial_data": result1, "cashflow_data": result2}

        result3 = agent3.execute(context3)

        # Store Agent 3 result
        agent_result_3 = models.AgentResult(
            analysis_id=analysis_id, agent_name="Risk Detector", result_data=result3, execution_time_ms=1000
        )
        db.add(agent_result_3)
        db.commit()

        # Compute deterministic loan readiness score from agents 1-3
        # Extract metrics from agent results
        profit_margin = 0.0
        runway_months = 0.0
        burn_rate = 0.0
        risk_score = 0.0

        try:
            # Extract profit margin from FinancialAnalyzer result
            if isinstance(result1, dict):
                metrics = result1.get("metrics", {})
                profit_margin = float(metrics.get("net_profit_margin", 0.0) or 0.0)
        except (ValueError, TypeError, AttributeError):
            logger.warning("Failed to extract profit_margin from Agent 1 result")

        try:
            # Extract runway and burn rate from CashFlowForecaster result
            if isinstance(result2, dict):
                runway_months = float(result2.get("runway_months", 0.0) or 0.0)
                burn_rate = float(result2.get("monthly_burn_rate", 0.0) or 0.0)
        except (ValueError, TypeError, AttributeError):
            logger.warning("Failed to extract runway_months/burn_rate from Agent 2 result")

        try:
            # Extract risk score from RiskDetector result
            if isinstance(result3, dict):
                risk_score = float(result3.get("risk_score", 0.0) or 0.0)
        except (ValueError, TypeError, AttributeError):
            logger.warning("Failed to extract risk_score from Agent 3 result")

        # Compute loan readiness score using deterministic formula
        loan_readiness_score = compute_loan_readiness_score(
            profit_margin=profit_margin,
            runway_months=runway_months,
            burn_rate=burn_rate,
            risk_score=risk_score
        )

        logger.info(
            f"Loan readiness score computed: {loan_readiness_score} "
            f"(profit_margin={profit_margin}, runway_months={runway_months}, "
            f"burn_rate={burn_rate}, risk_score={risk_score})"
        )

        logger.info("Executing Agent 4: Automation Agent")
        context4 = {"financial_data": result1}

        result4 = agent4.execute(context4)

        # Store Agent 4 result
        agent_result_4 = models.AgentResult(
            analysis_id=analysis_id, agent_name="Automation Agent", result_data=result4, execution_time_ms=1000
        )
        db.add(agent_result_4)
        db.commit()

        logger.info("Executing Agent 5: Explainability Agent")
        context5 = {"financial_data": result1, "cashflow_data": result2, "risk_data": result3, "compliance_data": result4}

        result5 = agent5.execute(context5)

        # Store Agent 5 result
        agent_result_5 = models.AgentResult(
            analysis_id=analysis_id, agent_name="Explainability Agent", result_data=result5, execution_time_ms=1000
        )
        db.add(agent_result_5)
        db.commit()

        # Aggregate final report
        report_data = {
            "section_1_financial_health": result1,
            "section_2_cash_flow_forecast": result2,
            "section_3_risk_alerts": result3,
            "section_4_compliance_automation": result4,
            "section_5_loan_readiness_score": loan_readiness_score,
            "section_6_recommended_actions": result5,
            "loan_readiness_score": loan_readiness_score,
        }

        # Create report
        report = models.Report(analysis_id=analysis_id, report_data=report_data)

        db.add(report)

        # Update analysis status
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()

        db.commit()

        logger.info(f"Analysis completed successfully: {analysis_id}")

    except Exception as e:
        logger.error(f"Analysis processing failed: {str(e)}")

        analysis = db.query(models.Analysis).filter(models.Analysis.analysis_id == analysis_id).first()

        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            db.commit()

    finally:
        db.close()


@router.post("/run", response_model=schemas.AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_analysis(
    data: schemas.AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run financial analysis on uploaded documents

    Args:
        data: Analysis request data
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        db: Database session

    Returns:
        Analysis ID and status

    Raises:
        HTTPException: If no documents found or validation fails
    """
    logger.info(f"Analysis request from user {current_user.user_id}")

    # Get document IDs
    document_ids = data.document_ids

    if not document_ids:
        # Use all user documents
        documents = db.query(models.Document).filter(models.Document.user_id == current_user.user_id).all()

        document_ids = [doc.document_id for doc in documents]

    if not document_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents found for analysis")

    # Verify all documents belong to user
    documents = (
        db.query(models.Document)
        .filter(models.Document.document_id.in_(document_ids), models.Document.user_id == current_user.user_id)
        .all()
    )

    if len(documents) != len(document_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Some documents not found")

    # Create analysis record
    analysis = models.Analysis(user_id=current_user.user_id, status="processing")

    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Create analysis-document associations
    for doc_id in document_ids:
        assoc = models.AnalysisDocument(analysis_id=analysis.analysis_id, document_id=doc_id)
        db.add(assoc)

    db.commit()

    # Start background processing
    from app.config import get_settings

    settings = get_settings()
    background_tasks.add_task(process_analysis, analysis.analysis_id, document_ids, settings.database_url)

    logger.info(f"Analysis started: {analysis.analysis_id}")

    return schemas.AnalysisResponse(
        analysis_id=analysis.analysis_id,
        status="processing",
        estimated_completion=datetime.utcnow() + timedelta(minutes=5),
        message="Analysis started successfully",
    )


@router.get("/{analysis_id}", response_model=schemas.ReportResponse)
async def get_analysis(
    analysis_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get analysis report by ID

    Args:
        analysis_id: Analysis ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Analysis report

    Raises:
        HTTPException: If analysis not found or access denied
    """
    analysis = db.query(models.Analysis).filter(models.Analysis.analysis_id == analysis_id).first()

    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    if analysis.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Get report if completed
    report = None

    if analysis.status == "completed":
        report_record = db.query(models.Report).filter(models.Report.analysis_id == analysis_id).first()

        if report_record:
            report = report_record.report_data

    return schemas.ReportResponse(
        analysis_id=analysis.analysis_id,
        user_id=analysis.user_id,
        status=analysis.status,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        report=report,
    )


@router.get("", response_model=schemas.AnalysisListResponse)
async def list_analyses(
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all analyses for authenticated user

    Args:
        page: Page number
        limit: Items per page
        status_filter: Optional status filter
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of analyses
    """
    if limit > 100:
        limit = 100

    offset = (page - 1) * limit

    # Build query
    query = db.query(models.Analysis).filter(models.Analysis.user_id == current_user.user_id)

    if status_filter:
        query = query.filter(models.Analysis.status == status_filter)

    # Get total count
    total = query.count()

    # Get paginated results
    analyses = query.order_by(models.Analysis.created_at.desc()).offset(offset).limit(limit).all()

    # Get document counts
    analyses_with_counts = []

    for analysis in analyses:
        doc_count = (
            db.query(models.AnalysisDocument).filter(models.AnalysisDocument.analysis_id == analysis.analysis_id).count()
        )

        analyses_with_counts.append(
            schemas.AnalysisStatus(
                analysis_id=analysis.analysis_id,
                user_id=analysis.user_id,
                status=analysis.status,
                created_at=analysis.created_at,
                completed_at=analysis.completed_at,
                document_count=doc_count,
            )
        )

    return schemas.AnalysisListResponse(analyses=analyses_with_counts, total=total, page=page, limit=limit)
