import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from app.api.deps import get_current_user, get_db
from app.users.model import User
from app.people.model import Person

logger = logging.getLogger(__name__)

router = APIRouter()


class PersonSearchRequest(BaseModel):
    """Person search request."""
    company_id: Optional[str] = None
    name: Optional[str] = None
    job_title: Optional[str] = None


class PersonCreateRequest(BaseModel):
    """Person create request."""
    first_name: str
    last_name: str
    email: Optional[str] = None
    company_id: Optional[str] = None
    job_title: Optional[str] = None
    linkedin_url: Optional[str] = None


@router.get("/")
async def list_people(
    company_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List people with optional filters."""
    try:
        query = select(Person)
        
        if company_id:
            query = query.where(Person.company_id == company_id)
        
        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        people = result.scalars().all()
        
        return {
            "people": [
                {
                    "id": p.id,
                    "first_name": p.first_name,
                    "last_name": p.last_name,
                    "full_name": p.full_name,
                    "title": p.title,
                    "company_id": p.company_id,
                    "linkedin_url": p.linkedin_url,
                }
                for p in people
            ],
            "count": len(people),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"List people error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list people",
        )


@router.get("/{person_id}")
async def get_person(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get person by ID."""
    try:
        result = await db.execute(
            select(Person).where(Person.id == person_id)
        )
        person = result.scalars().first()
        
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )
        
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "full_name": person.full_name,
            "title": person.title,
            "company_id": person.company_id,
            "linkedin_url": person.linkedin_url,
            "twitter_url": person.twitter_url,
            "department": person.department,
            "seniority": person.seniority,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get person error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get person",
        )


@router.post("/")
async def create_person(
    req: PersonCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new person."""
    try:
        person = Person(
            id=str(uuid.uuid4()),
            first_name=req.first_name,
            last_name=req.last_name,
            full_name=f"{req.first_name} {req.last_name}",
            title=req.job_title,
            company_id=req.company_id,
            linkedin_url=req.linkedin_url,
        )
        db.add(person)
        await db.commit()
        
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "full_name": person.full_name,
            "title": person.title,
            "company_id": person.company_id,
        }
    except Exception as e:
        logger.error(f"Create person error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create person",
        )


@router.delete("/{person_id}")
async def delete_person(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a person."""
    try:
        result = await db.execute(
            select(Person).where(Person.id == person_id)
        )
        person = result.scalars().first()
        
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )
        
        await db.delete(person)
        await db.commit()
        return {"message": "Person deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete person error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete person",
        )
