"""Document management API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.config import get_settings
from app.utils.pdf_parser import extract_text_from_pdf
from app.utils.excel_parser import extract_data_from_excel
from typing import List, Optional
import os
import shutil
import logging
import json

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/documents", tags=["documents"])


def validate_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """Validate uploaded file"""
    # Check file extension
    ext = file.filename.split(".")[-1].lower()

    if ext not in settings.allowed_extensions:
        return False, f"File type .{ext} not supported. Allowed types: {', '.join(settings.allowed_extensions)}"

    # Check file size (read first chunk to check)
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    max_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    if size > max_size_bytes:
        return False, f"File size exceeds limit of {settings.max_upload_size_mb}MB"

    return True, None


@router.post("/upload", response_model=schemas.DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: List[UploadFile] = File(...),
    document_type: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload financial documents for analysis

    Args:
        files: One or more files (PDF or Excel)
        document_type: Optional document type
        current_user: Authenticated user
        db: Database session

    Returns:
        Upload confirmation with document IDs

    Raises:
        HTTPException: If upload fails or validation errors
    """
    logger.info(f"Upload request from user {current_user.user_id}: {len(files)} files")

    if len(files) > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 5 files per request")

    uploaded_docs = []

    for file in files:
        # Validate file
        is_valid, error_msg = validate_file(file)

        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        # Generate document ID explicitly so it's available before DB insert
        import uuid
        doc_id = str(uuid.uuid4())
        doc = models.Document(document_id=doc_id, user_id=current_user.user_id, filename=file.filename, document_type=document_type)

        # Create directory for user and document
        doc_dir = os.path.join(settings.upload_dir, current_user.user_id, doc_id)
        os.makedirs(doc_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(doc_dir, file.filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"File saved: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save file: {str(e)}"
            )

        # Get file size
        doc.size_bytes = os.path.getsize(file_path)
        doc.file_path = file_path
        doc.processed = False

        # Add to database
        db.add(doc)
        db.commit()
        db.refresh(doc)

        uploaded_docs.append(doc)

    logger.info(f"Successfully uploaded {len(uploaded_docs)} documents")

    return schemas.DocumentUploadResponse(
        document_ids=[doc.document_id for doc in uploaded_docs],
        uploaded_count=len(uploaded_docs),
        documents=[
            schemas.DocumentResponse(
                document_id=doc.document_id,
                filename=doc.filename,
                document_type=doc.document_type,
                size_bytes=doc.size_bytes,
                uploaded_at=doc.uploaded_at,
                processed=doc.processed,
            )
            for doc in uploaded_docs
        ],
    )


@router.get("", response_model=schemas.DocumentListResponse)
async def list_documents(
    page: int = 1,
    limit: int = 20,
    document_type: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all documents for authenticated user

    Args:
        page: Page number (1-indexed)
        limit: Items per page (max 100)
        document_type: Optional filter by document type
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of documents
    """
    if limit > 100:
        limit = 100

    offset = (page - 1) * limit

    # Build query
    query = db.query(models.Document).filter(models.Document.user_id == current_user.user_id)

    if document_type:
        query = query.filter(models.Document.document_type == document_type)

    # Get total count
    total = query.count()

    # Get paginated results
    documents = query.order_by(models.Document.uploaded_at.desc()).offset(offset).limit(limit).all()

    return schemas.DocumentListResponse(
        documents=[
            schemas.DocumentResponse(
                document_id=doc.document_id,
                filename=doc.filename,
                document_type=doc.document_type,
                size_bytes=doc.size_bytes,
                uploaded_at=doc.uploaded_at,
                processed=doc.processed,
            )
            for doc in documents
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{document_id}", response_model=schemas.DocumentDetail)
async def get_document(
    document_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get details of specific document

    Args:
        document_id: Document ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Document details

    Raises:
        HTTPException: If document not found or access denied
    """
    document = db.query(models.Document).filter(models.Document.document_id == document_id).first()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return schemas.DocumentDetail(
        document_id=document.document_id,
        filename=document.filename,
        document_type=document.document_type,
        size_bytes=document.size_bytes,
        uploaded_at=document.uploaded_at,
        processed=document.processed,
        metadata=document.doc_metadata,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Delete document and associated data

    Args:
        document_id: Document ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: If document not found or access denied
    """
    document = db.query(models.Document).filter(models.Document.document_id == document_id).first()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Delete file from filesystem
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # Try to remove parent directory if empty
        doc_dir = os.path.dirname(document.file_path)
        if os.path.exists(doc_dir) and not os.listdir(doc_dir):
            os.rmdir(doc_dir)

    except Exception as e:
        logger.warning(f"Failed to delete file: {str(e)}")

    # Delete from database
    db.delete(document)
    db.commit()

    logger.info(f"Document deleted: {document_id}")

    return {"message": "Document deleted successfully", "document_id": document_id}
