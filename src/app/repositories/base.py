# Base Repository Pattern - SQLAlchemy 2.0 Async
"""
Base repository implementation for async SQLAlchemy 2.0 with FastAPI integration.
Provides common CRUD operations and query patterns for all domain repositories.
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar, Union
import uuid

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql import Select as SelectType

from app.db.models import Base


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository class with common async database operations.

    Provides type-safe CRUD operations and query builders that can be
    extended by domain-specific repositories.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository with model type and async session.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def get(self, id: uuid.UUID, **kwargs) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: UUID primary key
            **kwargs: Additional filter criteria

        Returns:
            Model instance or None if not found
        """
        query = select(self.model).where(self.model.id == id)

        # Apply additional filters
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_relations(
        self,
        id: uuid.UUID,
        relations: List[str] = None
    ) -> Optional[ModelType]:
        """
        Get a record by ID with specified relationships loaded.

        Args:
            id: UUID primary key
            relations: List of relationship names to eager load

        Returns:
            Model instance with loaded relations or None
        """
        query = select(self.model).where(self.model.id == id)

        if relations:
            for relation in relations:
                if hasattr(self.model, relation):
                    query = query.options(selectinload(getattr(self.model, relation)))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        **filters
    ) -> List[ModelType]:
        """
        Get multiple records with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field name to order by (prefix with '-' for desc)
            **filters: Filter criteria as field=value pairs

        Returns:
            List of model instances
        """
        query = select(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                if isinstance(value, list):
                    query = query.where(getattr(self.model, key).in_(value))
                else:
                    query = query.where(getattr(self.model, key) == value)

        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                field_name = order_by[1:]
                if hasattr(self.model, field_name):
                    query = query.order_by(getattr(self.model, field_name).desc())
            else:
                if hasattr(self.model, order_by):
                    query = query.order_by(getattr(self.model, order_by))

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, **filters) -> int:
        """
        Count records matching the given filters.

        Args:
            **filters: Filter criteria as field=value pairs

        Returns:
            Number of matching records
        """
        query = select(func.count(self.model.id))

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                if isinstance(value, list):
                    query = query.where(getattr(self.model, key).in_(value))
                else:
                    query = query.where(getattr(self.model, key) == value)

        result = await self.session.execute(query)
        return result.scalar()

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Pydantic model with creation data

        Returns:
            Created model instance
        """
        if hasattr(obj_in, 'model_dump'):
            obj_data = obj_in.model_dump()
        else:
            obj_data = obj_in.dict()

        db_obj = self.model(**obj_data)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def create_bulk(self, objs_in: List[CreateSchemaType]) -> List[ModelType]:
        """
        Create multiple records in a single transaction.

        Args:
            objs_in: List of Pydantic models with creation data

        Returns:
            List of created model instances
        """
        db_objs = []
        for obj_in in objs_in:
            if hasattr(obj_in, 'model_dump'):
                obj_data = obj_in.model_dump()
            else:
                obj_data = obj_in.dict()

            db_obj = self.model(**obj_data)
            db_objs.append(db_obj)

        self.session.add_all(db_objs)
        await self.session.flush()

        # Refresh all objects to get IDs and updated fields
        for db_obj in db_objs:
            await self.session.refresh(db_obj)

        return db_objs

    async def update(
        self,
        id: uuid.UUID,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: UUID primary key
            obj_in: Pydantic model or dict with update data

        Returns:
            Updated model instance or None if not found
        """
        db_obj = await self.get(id)
        if not db_obj:
            return None

        if hasattr(obj_in, 'model_dump'):
            update_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, 'dict'):
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = obj_in

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def update_bulk(
        self,
        updates: List[Dict[str, Any]],
        id_field: str = "id"
    ) -> int:
        """
        Update multiple records efficiently.

        Args:
            updates: List of dicts with update data including ID field
            id_field: Name of the ID field (default: "id")

        Returns:
            Number of records updated
        """
        if not updates:
            return 0

        stmt = update(self.model)
        result = await self.session.execute(stmt, updates)
        return result.rowcount

    async def delete(self, id: uuid.UUID) -> bool:
        """
        Delete a record by ID.

        Args:
            id: UUID primary key

        Returns:
            True if record was deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def delete_multi(self, ids: List[uuid.UUID]) -> int:
        """
        Delete multiple records by IDs.

        Args:
            ids: List of UUID primary keys

        Returns:
            Number of records deleted
        """
        stmt = delete(self.model).where(self.model.id.in_(ids))
        result = await self.session.execute(stmt)
        return result.rowcount

    async def exists(self, id: uuid.UUID) -> bool:
        """
        Check if a record exists by ID.

        Args:
            id: UUID primary key

        Returns:
            True if record exists, False otherwise
        """
        query = select(self.model.id).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    def build_query(self) -> Select:
        """
        Build a base query for this model.

        Returns:
            SQLAlchemy select statement for the model
        """
        return select(self.model)

    async def execute_query(self, query: SelectType) -> List[ModelType]:
        """
        Execute a custom query and return results.

        Args:
            query: SQLAlchemy select statement

        Returns:
            List of model instances
        """
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def execute_scalar_query(self, query: SelectType) -> Optional[Any]:
        """
        Execute a custom query and return a scalar result.

        Args:
            query: SQLAlchemy select statement

        Returns:
            Scalar result or None
        """
        result = await self.session.execute(query)
        return result.scalar_one_or_none()