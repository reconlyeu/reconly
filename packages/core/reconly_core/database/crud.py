"""CRUD operations for digest database."""
import asyncio
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict
from sqlalchemy import create_engine, or_, desc
from sqlalchemy.orm import Session, sessionmaker

from reconly_core.database.models import Base, Digest, Tag, DigestTag

logger = logging.getLogger(__name__)

# Default database URL - consistent with FastAPI config
DEFAULT_DATABASE_URL = 'postgresql://reconly:reconly@localhost:5432/reconly'


class DigestDB:
    """Database operations for digests."""

    def __init__(self, database_url: str = None, session: Session = None):
        """
        Initialize database connection.

        Args:
            database_url: Database URL (default: from DATABASE_URL env or PostgreSQL localhost)
            session: Optional SQLAlchemy session for dependency injection (for testing)
        """
        if session is not None:
            # Use provided session (for testing/dependency injection)
            self.session = session
            self.database_url = None
        else:
            # Create new session from database URL
            if database_url is None:
                database_url = os.getenv('DATABASE_URL', DEFAULT_DATABASE_URL)

            self.database_url = database_url
            engine = create_engine(database_url, echo=False)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine)
            self.session = SessionLocal()

    def create_digest(
        self,
        url: str,
        title: str = None,
        content: str = None,
        summary: str = None,
        source_type: str = None,
        feed_url: str = None,
        feed_title: str = None,
        author: str = None,
        published_at: datetime = None,
        provider: str = None,
        language: str = None,
        estimated_cost: float = 0.0,
        tags: List[str] = None,
        user_id: Optional[int] = None
    ) -> Digest:
        """
        Create a new digest.

        Args:
            url: Digest URL (required, unique)
            title: Digest title
            content: Full content
            summary: AI-generated summary
            source_type: Type of source (website, youtube, rss)
            feed_url: RSS feed URL (if from RSS)
            feed_title: RSS feed title
            author: Content author
            published_at: Publication date
            provider: LLM provider used
            language: Content language
            estimated_cost: Cost of summarization
            tags: List of tag names
            user_id: User ID (for multi-tenancy)

        Returns:
            Created Digest object
        """
        digest = Digest(
            url=url,
            title=title,
            content=content,
            summary=summary,
            source_type=source_type,
            feed_url=feed_url,
            feed_title=feed_title,
            author=author,
            published_at=published_at,
            provider=provider,
            language=language,
            estimated_cost=estimated_cost
        )
        self.session.add(digest)
        self.session.flush()  # Get digest ID

        # Handle tags
        if tags:
            for tag_name in tags:
                tag = self.session.query(Tag).filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.session.add(tag)
                    self.session.flush()  # Get tag ID

                digest_tag = DigestTag(digest_id=digest.id, tag_id=tag.id)
                self.session.add(digest_tag)

        self.session.commit()
        return digest

    def save_digest(
        self,
        digest_data: Dict,
        tags: List[str] = None,
        auto_embed: bool = False,
    ) -> Digest:
        """
        Save a digest to the database.

        Args:
            digest_data: Dictionary with digest information
            tags: List of tag names
            auto_embed: If True, trigger embedding after save (default: False)

        Returns:
            Created or updated Digest object
        """
        # Check if digest already exists (by URL)
        existing = self.session.query(Digest).filter_by(url=digest_data['url']).first()

        if existing:
            # Update existing
            for key, value in digest_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            digest = existing
        else:
            # Create new
            digest = Digest(**digest_data)
            self.session.add(digest)

        # Handle tags
        if tags:
            # Remove old tags
            self.session.query(DigestTag).filter_by(digest_id=digest.id).delete()

            # Add new tags
            for tag_name in tags:
                tag = self.session.query(Tag).filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.session.add(tag)
                    self.session.flush()  # Get tag ID

                digest_tag = DigestTag(digest_id=digest.id, tag_id=tag.id)
                self.session.add(digest_tag)

        self.session.commit()

        # Trigger embedding if requested
        if auto_embed:
            self._trigger_embedding(digest)

        return digest

    def _trigger_embedding(self, digest: Digest) -> None:
        """
        Trigger embedding generation for a digest.

        This runs the embedding process synchronously. For async contexts,
        use the EmbeddingService directly.

        Args:
            digest: Digest to embed
        """
        try:
            from reconly_core.rag.embedding_service import (
                EmbeddingService,
                EMBEDDING_STATUS_PENDING,
            )

            # Set status to pending before starting
            digest.embedding_status = EMBEDDING_STATUS_PENDING
            digest.embedding_error = None
            self.session.commit()

            # Create embedding service and run synchronously
            service = EmbeddingService(self.session)

            # Run async code in event loop
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    service.embed_digest(digest, update_status=True)
                )
                self.session.commit()
            finally:
                loop.close()

            logger.info(f"Successfully embedded digest {digest.id}")

        except Exception as e:
            # Log error but don't fail the save operation
            logger.error(f"Failed to embed digest {digest.id}: {e}")
            # Status is already set to failed by EmbeddingService
            self.session.commit()

    def get_digest_by_url(self, url: str) -> Optional[Digest]:
        """
        Get digest by URL.

        Args:
            url: Digest URL

        Returns:
            Digest object or None
        """
        return self.session.query(Digest).filter_by(url=url).first()

    def get_digest_by_id(self, digest_id: int, user_id: Optional[int] = None) -> Optional[Digest]:
        """
        Get digest by ID.

        Args:
            digest_id: Digest ID
            user_id: User ID for filtering (optional)

        Returns:
            Digest object or None
        """
        q = self.session.query(Digest).filter_by(id=digest_id)
        if user_id is not None:
            q = q.filter_by(user_id=user_id)
        return q.first()

    def get_digests_by_ids(self, digest_ids: List[int]) -> List[Digest]:
        """
        Get multiple digests by IDs.

        Args:
            digest_ids: List of digest IDs

        Returns:
            List of Digest objects (in same order as IDs if found)
        """
        if not digest_ids:
            return []

        # Query all digests with given IDs
        digests = self.session.query(Digest).filter(Digest.id.in_(digest_ids)).all()

        # Sort by the order of input IDs
        digest_map = {d.id: d for d in digests}
        return [digest_map[digest_id] for digest_id in digest_ids if digest_id in digest_map]

    def list_digests(
        self,
        limit: int = 10,
        offset: int = 0,
        tags: List[str] = None,
        source_type: str = None,
        user_id: Optional[int] = None
    ) -> List[Digest]:
        """
        List digests with optional filtering.

        Args:
            limit: Maximum results
            offset: Skip first N results
            tags: Filter by tags
            source_type: Filter by source type
            user_id: User ID for filtering (optional)

        Returns:
            List of Digest objects
        """
        return self.search_digests(
            query=None,
            tags=tags,
            source_type=source_type,
            limit=limit,
            offset=offset,
            user_id=user_id
        )

    def search_digests(
        self,
        query: str = None,
        tags: List[str] = None,
        source_type: str = None,
        limit: int = 10,
        offset: int = 0,
        user_id: Optional[int] = None
    ) -> List[Digest]:
        """
        Search digests.

        Args:
            query: Search query (searches in title, content, summary)
            tags: Filter by tags
            source_type: Filter by source type
            limit: Maximum results
            offset: Skip first N results
            user_id: User ID for filtering (optional)

        Returns:
            List of Digest objects
        """
        q = self.session.query(Digest)

        # Filter by user_id
        if user_id is not None:
            q = q.filter(Digest.user_id == user_id)

        # Text search
        if query:
            q = q.filter(
                or_(
                    Digest.title.ilike(f'%{query}%'),
                    Digest.content.ilike(f'%{query}%'),
                    Digest.summary.ilike(f'%{query}%')
                )
            )

        # Filter by source type
        if source_type:
            q = q.filter(Digest.source_type == source_type)

        # Filter by tags
        if tags:
            for tag_name in tags:
                q = q.join(DigestTag).join(Tag).filter(Tag.name == tag_name)

        # Order by created date (newest first)
        q = q.order_by(desc(Digest.created_at))

        # Pagination
        q = q.offset(offset).limit(limit)

        return q.all()

    def get_all_digests(self, limit: int = 100, offset: int = 0) -> List[Digest]:
        """
        Get all digests.

        Args:
            limit: Maximum results
            offset: Skip first N results

        Returns:
            List of Digest objects
        """
        return self.session.query(Digest).order_by(
            desc(Digest.created_at)
        ).offset(offset).limit(limit).all()

    def get_all_tags(self) -> List[Tag]:
        """
        Get all tags.

        Returns:
            List of Tag objects
        """
        return self.session.query(Tag).all()

    def get_statistics(self, user_id: Optional[int] = None) -> Dict:
        """
        Get database statistics.

        Args:
            user_id: User ID for filtering (optional)

        Returns:
            Dictionary with statistics
        """
        # Base query with optional user filtering
        base_q = self.session.query(Digest)
        if user_id is not None:
            base_q = base_q.filter(Digest.user_id == user_id)

        total_digests = base_q.count()
        total_cost = base_q.with_entities(Digest.estimated_cost).all()
        total_cost = sum(c[0] for c in total_cost if c[0] is not None)

        by_type = {}
        for source_type in ['website', 'youtube', 'rss']:
            q = base_q.filter_by(source_type=source_type)
            count = q.count()
            by_type[source_type] = count

        return {
            'total_digests': total_digests,
            'total_cost': total_cost,
            'by_source_type': by_type,
            'total_tags': self.session.query(Tag).count()
        }

    def delete_digest(self, digest_id: int) -> bool:
        """
        Delete a digest.

        Args:
            digest_id: Digest ID

        Returns:
            True if deleted, False if not found
        """
        digest = self.get_digest_by_id(digest_id)
        if digest:
            self.session.delete(digest)
            self.session.commit()
            return True
        return False

    def export_to_dict(self, digests: List[Digest]) -> List[Dict]:
        """
        Export digests to list of dictionaries.

        Args:
            digests: List of Digest objects

        Returns:
            List of dictionaries
        """
        return [digest.to_dict() for digest in digests]

    def close(self):
        """Close database session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
