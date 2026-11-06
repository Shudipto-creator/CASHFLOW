"""Saved FINNDB customers for person-to-person sandbox transfers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import get_current_user
from app.services import finn_bank

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ContactCreate(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=36)


class ContactUserIdCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=36)


def _contact_dict(contact: models.FinnContact, target: dict) -> dict:
    return {
        "id": contact.contact_id,
        "customer_id": target["customer_id"],
        "name": target["name"],
        "created_at": contact.created_at,
    }


def _save_contact(user: models.User, target: dict, db: Session) -> dict:
    own_customer_id = finn_bank.customer_id_for(user)
    if target["customer_id"] == own_customer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot add your own account as a contact.",
        )
    existing = db.query(models.FinnContact).filter_by(
        user_id=user.user_id,
        customer_id=target["customer_id"],
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That contact is already saved.")

    contact = models.FinnContact(user_id=user.user_id, customer_id=target["customer_id"])
    db.add(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That contact is already saved.") from exc
    db.refresh(contact)
    return _contact_dict(contact, target)


def _recipient_for_user_id(user_id: str, db: Session) -> tuple[models.User, dict]:
    recipient_user = db.query(models.User).filter_by(user_id=user_id.strip()).first()
    if recipient_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No FINN account was found with that user ID.")
    target_customer_id = finn_bank.customer_id_for(recipient_user)
    return recipient_user, finn_bank.transfer_customer(target_customer_id)


@router.get("")
def list_contacts(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contacts = (
        db.query(models.FinnContact)
        .filter(models.FinnContact.user_id == user.user_id)
        .order_by(models.FinnContact.contact_id)
        .all()
    )
    items = []
    for contact in contacts:
        try:
            target = finn_bank.transfer_customer(contact.customer_id)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                continue
            raise
        items.append(_contact_dict(contact, target))
    items.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    return {"items": items}


@router.get("/search")
def search_customers(
    name: str = Query(..., min_length=2, max_length=100),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_customer_id = finn_bank.customer_id_for(user)
    existing_ids = {
        row[0] for row in db.query(models.FinnContact.customer_id)
        .filter(models.FinnContact.user_id == user.user_id)
        .all()
    }
    search_term = name.strip()
    if len(search_term) < 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter at least 2 characters to search.")
    matches = finn_bank.search_transfer_customers(
        search_term,
        exclude_customer_id=owner_customer_id,
    )
    return {"items": [match for match in matches if match["customer_id"] not in existing_ids]}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_contact(
    payload: ContactCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = finn_bank.transfer_customer(payload.customer_id)
    return _save_contact(user, target, db)


@router.post("/by-user-id", status_code=status.HTTP_201_CREATED)
def add_contact_by_user_id(
    payload: ContactUserIdCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipient_id = payload.user_id.strip()
    if recipient_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot add yourself as a contact.",
        )
    _, target = _recipient_for_user_id(recipient_id, db)
    return _save_contact(user, target, db)


@router.post("/by-user-id/preview")
def preview_contact_by_user_id(
    payload: ContactUserIdCreate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipient_id = payload.user_id.strip()
    if recipient_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot add yourself as a contact.",
        )
    recipient_user, target = _recipient_for_user_id(recipient_id, db)
    if target["customer_id"] == finn_bank.customer_id_for(user):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This FINN account resolves to your own account and cannot be added.",
        )
    existing = db.query(models.FinnContact).filter_by(
        user_id=user.user_id,
        customer_id=target["customer_id"],
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That contact is already saved.")
    return {"user_id": recipient_user.user_id, "name": target["name"]}


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_contact(
    customer_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.query(models.FinnContact).filter_by(
        user_id=user.user_id,
        customer_id=customer_id,
    ).first()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved contact was not found.")
    db.delete(contact)
    db.commit()
