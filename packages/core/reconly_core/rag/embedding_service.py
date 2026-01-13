"""High-level embedding service for RAG knowledge system.

Orchestrates chunking and embedding for digests, creating DigestChunk
records in the database. Tracks embedding status on digests.

Uses PostgreSQL with pgvector for efficient vector storage and similarity search.
"""
import asyncio
import logging
from typing import Callable, List, Optional, TYPE_CHECKING

from reconly_core.rag.chunking import ChunkingService
from reconly_core.rag.embeddings import get_embedding_provider, EmbeddingProvider

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from reconly_core.database.models import Digest, DigestChunk

logger = logging.getLogger(__name__)

# Embedding status constants
EMBEDDING_STATUS_PENDING = "pending"
EMBEDDING_STATUS_COMPLETED = "completed"
EMBEDDING_STATUS_FAILED = "failed"


class EmbeddingService:
    """Service for creating embeddings from digests.

    Combines ChunkingService and EmbeddingProvider to:
    1. Split digest content into semantic chunks
    2. Generate embeddings for each chunk
    3. Store chunks with embeddings in the database

    Example:
        >>> from reconly_core.rag import EmbeddingService
        >>> service = EmbeddingService(db)
        >>> chunks = await service.embed_digest(digest)
        >>> print(f"Created {len(chunks)} chunks with embeddings")
    """

    def __init__(
        self,
        db: "Session",
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunking_service: Optional[ChunkingService] = None,
        batch_size: int = 32,
    ):
        """
        Initialize the embedding service.

        Args:
            db: Database session for storing chunks
            embedding_provider: Provider for generating embeddings (auto-configured if None)
            chunking_service: Service for text chunking (auto-configured if None)
            batch_size: Number of texts to embed per batch
        """
        self.db = db
        self.batch_size = batch_size

        # Auto-configure provider if not provided
        if embedding_provider is None:
            self.provider = get_embedding_provider(db=db)
        else:
            self.provider = embedding_provider

        # Auto-configure chunking service if not provided
        if chunking_service is None:
            self.chunker = ChunkingService(db=db)
        else:
            self.chunker = chunking_service

    async def embed_digest(
        self,
        digest: "Digest",
        replace_existing: bool = True,
        include_summary: bool = True,
        update_status: bool = True,
    ) -> List["DigestChunk"]:
        """
        Chunk and embed a single digest.

        Creates DigestChunk records in the database with embeddings.
        Updates the digest's embedding_status to track progress.

        Args:
            digest: Digest model instance to embed
            replace_existing: If True, delete existing chunks before creating new ones
            include_summary: If True, include summary as a separate chunk
            update_status: If True, update digest.embedding_status (default: True)

        Returns:
            List of created DigestChunk records

        Example:
            >>> chunks = await service.embed_digest(digest)
            >>> print(f"Embedded {len(chunks)} chunks for digest {digest.id}")
        """
        from reconly_core.database.models import DigestChunk

        logger.info(f"Embedding digest {digest.id}: {digest.title[:50] if digest.title else 'Untitled'}...")

        # Set status to pending
        if update_status:
            digest.embedding_status = EMBEDDING_STATUS_PENDING
            digest.embedding_error = None
            self.db.flush()

        try:
            # Delete existing chunks if requested
            if replace_existing:
                existing_chunks = self.db.query(DigestChunk).filter(
                    DigestChunk.digest_id == digest.id
                ).all()
                for chunk in existing_chunks:
                    self.db.delete(chunk)
                self.db.flush()
                logger.debug(f"Deleted {len(existing_chunks)} existing chunks for digest {digest.id}")

            # Create text chunks
            text_chunks = self.chunker.chunk_digest(
                digest,
                include_title=True,
                include_summary=include_summary,
            )

            if not text_chunks:
                logger.warning(f"No chunks created for digest {digest.id}")
                if update_status:
                    digest.embedding_status = EMBEDDING_STATUS_COMPLETED
                    self.db.flush()
                return []

            logger.debug(f"Created {len(text_chunks)} text chunks for digest {digest.id}")

            # Generate embeddings in batches
            all_texts = [chunk.text for chunk in text_chunks]
            embeddings = await self._embed_with_batching(all_texts)

            # Create DigestChunk records
            db_chunks = []
            for i, (text_chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
                # pgvector handles embedding storage directly
                db_chunk = DigestChunk(
                    digest_id=digest.id,
                    chunk_index=i,
                    text=text_chunk.text,
                    embedding=embedding,
                    token_count=text_chunk.token_count,
                    start_char=text_chunk.start_char,
                    end_char=text_chunk.end_char,
                    extra_data=text_chunk.extra_data if text_chunk.extra_data else None,
                )
                self.db.add(db_chunk)
                db_chunks.append(db_chunk)

            # Mark as completed
            if update_status:
                digest.embedding_status = EMBEDDING_STATUS_COMPLETED
                digest.embedding_error = None

            self.db.flush()
            logger.info(f"Created {len(db_chunks)} chunks with embeddings for digest {digest.id}")

            return db_chunks

        except Exception as e:
            # Mark as failed and store error
            if update_status:
                digest.embedding_status = EMBEDDING_STATUS_FAILED
                digest.embedding_error = str(e)[:1000]  # Truncate error message
                self.db.flush()
            logger.error(f"Failed to embed digest {digest.id}: {e}")
            raise

    async def embed_digests(
        self,
        digests: List["Digest"],
        replace_existing: bool = True,
        include_summary: bool = True,
        progress_callback: Optional[Callable[[int, int, "Digest"], None]] = None,
    ) -> dict[int, List["DigestChunk"]]:
        """
        Chunk and embed multiple digests.

        Args:
            digests: List of Digest model instances
            replace_existing: If True, delete existing chunks before creating new ones
            include_summary: If True, include summary as a separate chunk
            progress_callback: Optional callback(current, total, digest) for progress updates

        Returns:
            Dictionary mapping digest_id -> list of created chunks
        """
        results = {}
        total = len(digests)

        for i, digest in enumerate(digests):
            if progress_callback:
                progress_callback(i + 1, total, digest)

            try:
                chunks = await self.embed_digest(
                    digest,
                    replace_existing=replace_existing,
                    include_summary=include_summary,
                    update_status=True,
                )
                results[digest.id] = chunks
            except Exception as e:
                # Error is already logged and status updated in embed_digest
                logger.error(f"Failed to embed digest {digest.id}: {e}")
                results[digest.id] = []

        return results

    async def embed_unembedded_digests(
        self,
        limit: Optional[int] = None,
        include_failed: bool = False,
        progress_callback: Optional[Callable[[int, int, "Digest"], None]] = None,
    ) -> dict[int, List["DigestChunk"]]:
        """
        Find and embed all digests that don't have embeddings yet.

        Uses embedding_status column for efficient querying. Digests with:
        - NULL status (legacy/never attempted)
        - 'failed' status (optionally, if include_failed=True)

        Args:
            limit: Maximum number of digests to process (None = all)
            include_failed: If True, also retry digests that previously failed
            progress_callback: Optional callback(current, total, digest) for progress updates

        Returns:
            Dictionary mapping digest_id -> list of created chunks
        """
        from reconly_core.database.models import Digest, DigestChunk
        from sqlalchemy import or_

        # Build filter for unembedded digests
        # NULL status = never attempted (legacy digests)
        # Also check for digests without chunks (backward compatibility)
        subquery = self.db.query(DigestChunk.digest_id).distinct()

        status_conditions = [
            Digest.embedding_status.is_(None),  # Never attempted
        ]
        if include_failed:
            status_conditions.append(Digest.embedding_status == EMBEDDING_STATUS_FAILED)

        # Find digests that either:
        # 1. Have no embedding_status set (NULL - legacy or never attempted)
        # 2. Have failed status (if include_failed=True)
        # 3. Have no chunks (backward compatibility for digests before status tracking)
        query = self.db.query(Digest).filter(
            or_(
                or_(*status_conditions),
                ~Digest.id.in_(subquery)
            )
        ).filter(
            # Exclude digests already completed
            or_(
                Digest.embedding_status.is_(None),
                Digest.embedding_status != EMBEDDING_STATUS_COMPLETED
            )
        )

        if limit:
            query = query.limit(limit)

        digests = query.all()

        logger.info(f"Found {len(digests)} digests without embeddings")

        if not digests:
            return {}

        return await self.embed_digests(
            digests,
            progress_callback=progress_callback,
        )

    async def _embed_with_batching(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        """Generate embeddings with batching."""
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            logger.debug(f"Embedding batch {i // self.batch_size + 1}/{(len(texts) - 1) // self.batch_size + 1}")

            try:
                batch_embeddings = await self.provider.embed(batch)
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Error embedding batch: {e}")
                # Add empty embeddings for failed batch
                all_embeddings.extend([[] for _ in batch])

        return all_embeddings

    def get_digest_chunks(
        self,
        digest_id: int,
    ) -> List["DigestChunk"]:
        """
        Get all chunks for a specific digest.

        Args:
            digest_id: ID of the digest

        Returns:
            List of DigestChunk records ordered by chunk_index
        """
        from reconly_core.database.models import DigestChunk

        return self.db.query(DigestChunk).filter(
            DigestChunk.digest_id == digest_id
        ).order_by(DigestChunk.chunk_index).all()

    def delete_digest_chunks(
        self,
        digest_id: int,
    ) -> int:
        """
        Delete all chunks for a specific digest.

        Args:
            digest_id: ID of the digest

        Returns:
            Number of chunks deleted
        """
        from reconly_core.database.models import DigestChunk

        count = self.db.query(DigestChunk).filter(
            DigestChunk.digest_id == digest_id
        ).delete()

        self.db.flush()
        return count

    def get_chunk_statistics(self) -> dict:
        """
        Get statistics about chunks in the database.

        Returns:
            Dictionary with statistics including embedding status breakdown
        """
        from reconly_core.database.models import DigestChunk, Digest
        from sqlalchemy import func

        # Total chunks
        total_chunks = self.db.query(func.count(DigestChunk.id)).scalar() or 0

        # Digests with chunks
        digests_with_chunks = self.db.query(
            func.count(func.distinct(DigestChunk.digest_id))
        ).scalar() or 0

        # Total digests
        total_digests = self.db.query(func.count(Digest.id)).scalar() or 0

        # Average chunks per digest
        avg_chunks = total_chunks / max(digests_with_chunks, 1)

        # Average tokens per chunk
        avg_tokens = self.db.query(
            func.avg(DigestChunk.token_count)
        ).scalar() or 0

        # Embedding status breakdown
        status_counts = {
            'pending': self.db.query(func.count(Digest.id)).filter(
                Digest.embedding_status == EMBEDDING_STATUS_PENDING
            ).scalar() or 0,
            'completed': self.db.query(func.count(Digest.id)).filter(
                Digest.embedding_status == EMBEDDING_STATUS_COMPLETED
            ).scalar() or 0,
            'failed': self.db.query(func.count(Digest.id)).filter(
                Digest.embedding_status == EMBEDDING_STATUS_FAILED
            ).scalar() or 0,
            'not_started': self.db.query(func.count(Digest.id)).filter(
                Digest.embedding_status.is_(None)
            ).scalar() or 0,
        }

        return {
            'total_chunks': total_chunks,
            'total_digests': total_digests,
            'digests_with_chunks': digests_with_chunks,
            'digests_without_chunks': total_digests - digests_with_chunks,
            'avg_chunks_per_digest': round(avg_chunks, 2),
            'avg_tokens_per_chunk': round(float(avg_tokens), 2),
            'embedding_status': status_counts,
            'embedding_provider': self.provider.get_provider_name(),
            'embedding_dimension': self.provider.get_dimension(),
        }


def chunk_and_embed_sync(
    db: "Session",
    digest: "Digest",
    **kwargs
) -> List["DigestChunk"]:
    """
    Synchronous wrapper for embedding a digest.

    Convenience function for use in non-async contexts.

    Args:
        db: Database session
        digest: Digest to embed
        **kwargs: Additional arguments for EmbeddingService.embed_digest

    Returns:
        List of created DigestChunk records
    """
    service = EmbeddingService(db)

    # Run async code in event loop
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(service.embed_digest(digest, **kwargs))
    finally:
        loop.close()
