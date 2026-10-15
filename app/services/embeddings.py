"""Vector store service for document embeddings"""

import chromadb
from chromadb.config import Settings as ChromaSettings
import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings
import os

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStore:
    """Manage document embeddings and semantic search using ChromaDB"""

    def __init__(self, nova_client):
        """
        Initialize vector store

        Args:
            nova_client: NovaClient instance for generating embeddings
        """
        self.nova_client = nova_client

        # Create vector store directory if it doesn't exist
        os.makedirs(settings.vector_store_path, exist_ok=True)

        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=settings.vector_store_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="financial_documents", metadata={"hnsw:space": "cosine"}
            )

            logger.info("Vector store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {str(e)}")
            raise

    def _chunk_text(self, text: str, chunk_size_words: int = 500, overlap_words: int = 50) -> List[str]:
        """
        Split text into overlapping chunks

        Args:
            text: Text to chunk
            chunk_size_words: Number of words per chunk
            overlap_words: Number of overlapping words between chunks

        Returns:
            List of text chunks
        """
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size_words - overlap_words):
            chunk = " ".join(words[i : i + chunk_size_words])
            if chunk.strip():
                chunks.append(chunk)

        return chunks

    def add_document(
        self, document_id: str, text: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Add document embeddings to vector store

        Args:
            document_id: Unique document identifier
            text: Document text content
            metadata: Document metadata (user_id, filename, etc.)

        Returns:
            True on success, False on failure
        """
        try:
            # Split text into chunks
            chunks = self._chunk_text(
                text,
                chunk_size_words=settings.chunk_size_words,
                overlap_words=settings.chunk_overlap_words,
            )

            if not chunks:
                logger.warning(f"No text chunks generated for document {document_id}")
                return False

            logger.info(f"Adding {len(chunks)} chunks for document {document_id}")

            # Generate embeddings for each chunk
            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for idx, chunk in enumerate(chunks):
                chunk_id = f"{document_id}_chunk_{idx}"

                # Generate embedding
                embedding = self.nova_client.generate_embeddings(chunk)

                if not embedding:
                    logger.warning(f"Failed to generate embedding for chunk {idx}")
                    continue

                ids.append(chunk_id)
                embeddings.append(embedding)
                documents.append(chunk)

                # Add chunk index to metadata
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = idx
                chunk_metadata["total_chunks"] = len(chunks)
                metadatas.append(chunk_metadata)

            if not ids:
                logger.error(f"No valid embeddings generated for document {document_id}")
                return False

            # Add to collection
            self.collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

            logger.info(f"Successfully added {len(ids)} chunks to vector store")
            return True

        except Exception as e:
            logger.error(f"Failed to add document to vector store: {str(e)}")
            return False

    def search_similar(
        self, query: str, top_k: int = 10, filter_metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant document chunks

        Args:
            query: Search query text
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"user_id": "123"})

        Returns:
            List of matching chunks with metadata and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.nova_client.generate_embeddings(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Perform search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata if filter_metadata else None,
            )

            # Format results
            formatted_results = []

            if results and results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    formatted_results.append(
                        {
                            "id": results["ids"][0][i],
                            "document_id": results["metadatas"][0][i].get("document_id"),
                            "chunk_text": results["documents"][0][i],
                            "similarity_score": 1 - results["distances"][0][i],  # Convert distance to similarity
                            "metadata": results["metadatas"][0][i],
                        }
                    )

            logger.info(f"Found {len(formatted_results)} similar chunks")
            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search vector store: {str(e)}")
            return []

    def delete_document(self, document_id: str) -> bool:
        """
        Remove all embeddings for a document

        Args:
            document_id: Document identifier

        Returns:
            True on success
        """
        try:
            # Find all chunks for this document
            results = self.collection.get(where={"document_id": document_id})

            if results and results["ids"]:
                # Delete all chunks
                self.collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} chunks for document {document_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete document from vector store: {str(e)}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics

        Returns:
            Dictionary with stats
        """
        try:
            count = self.collection.count()

            # Get unique document count
            all_data = self.collection.get()
            unique_docs = set()
            if all_data and all_data["metadatas"]:
                for metadata in all_data["metadatas"]:
                    if "document_id" in metadata:
                        unique_docs.add(metadata["document_id"])

            return {
                "total_documents": len(unique_docs),
                "total_chunks": count,
                "storage_path": settings.vector_store_path,
            }

        except Exception as e:
            logger.error(f"Failed to get vector store stats: {str(e)}")
            return {"total_documents": 0, "total_chunks": 0}

    def check_connection(self) -> bool:
        """
        Check if vector store is accessible

        Returns:
            True if connected
        """
        try:
            self.collection.count()
            return True
        except:
            return False
