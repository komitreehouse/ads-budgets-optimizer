"""
Vector Store Interface for RAG

Provides swappable vector store implementation.
Currently uses ChromaDB (local) but can be swapped for Pinecone or others.
"""

from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime
import json

from src.bandit_ads.utils import get_logger

logger = get_logger('vector_store')


class VectorStoreInterface(ABC):
    """Abstract interface for vector stores."""
    
    @abstractmethod
    def add_document(self, document_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Add a document to the vector store."""
        pass
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        pass
    
    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        pass
    
    @abstractmethod
    def clear_collection(self) -> bool:
        """Clear all documents."""
        pass


class ChromaDBStore(VectorStoreInterface):
    """ChromaDB implementation (local)."""
    
    def __init__(self, collection_name: str = "optimizer_decisions", persist_directory: str = "./data/vector_store"):
        """
        Initialize ChromaDB store.
        
        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist data
        """
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Optimizer decisions and explanations"}
            )
            
            # Initialize embeddings (using default ChromaDB embeddings)
            # Can be swapped for OpenAI embeddings later
            logger.info(f"ChromaDB initialized: {collection_name} at {persist_directory}")
            
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )
    
    def add_document(self, document_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Add document to ChromaDB."""
        try:
            # ChromaDB handles embeddings automatically
            self.collection.add(
                ids=[document_id],
                documents=[text],
                metadatas=[metadata]
            )
            logger.debug(f"Added document {document_id} to vector store")
            return True
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            return False
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search ChromaDB."""
        try:
            # Build where clause from filters
            where = None
            if filters:
                where = filters
            
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where
            )
            
            # Format results
            formatted_results = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return []
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document from ChromaDB."""
        try:
            self.collection.delete(ids=[document_id])
            logger.debug(f"Deleted document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return False
    
    def clear_collection(self) -> bool:
        """Clear all documents."""
        try:
            self.collection.delete()
            logger.info("Cleared vector store collection")
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {str(e)}")
            return False


class PineconeStore(VectorStoreInterface):
    """Pinecone implementation (cloud)."""
    
    def __init__(self, api_key: str, index_name: str, environment: str = "us-east1-gcp"):
        """
        Initialize Pinecone store.
        
        Args:
            api_key: Pinecone API key
            index_name: Index name
            environment: Pinecone environment
        """
        try:
            import pinecone
            from pinecone import Pinecone, ServerlessSpec
            
            self.pc = Pinecone(api_key=api_key)
            self.index = self.pc.Index(index_name)
            self.index_name = index_name
            
            logger.info(f"Pinecone initialized: {index_name}")
        except ImportError:
            raise ImportError(
                "Pinecone not installed. Install with: pip install pinecone-client"
            )
    
    def add_document(self, document_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Add document to Pinecone."""
        # Would need embeddings - placeholder
        logger.warning("Pinecone implementation incomplete - needs embedding function")
        return False
    
    def search(self, query: str, top_k: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search Pinecone."""
        # Would need embeddings - placeholder
        logger.warning("Pinecone implementation incomplete - needs embedding function")
        return []
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document from Pinecone."""
        try:
            self.index.delete(ids=[document_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return False
    
    def clear_collection(self) -> bool:
        """Clear all documents."""
        logger.warning("Pinecone clear_collection not implemented")
        return False


class VectorStoreManager:
    """
    Manages vector store with swappable backends.
    
    Default: ChromaDB (local)
    Can be swapped for Pinecone or other implementations.
    """
    
    def __init__(self, store_type: str = "chromadb", **kwargs):
        """
        Initialize vector store manager.
        
        Args:
            store_type: "chromadb" or "pinecone"
            **kwargs: Store-specific configuration
        """
        self.store_type = store_type
        
        if store_type == "chromadb":
            self.store = ChromaDBStore(**kwargs)
        elif store_type == "pinecone":
            self.store = PineconeStore(**kwargs)
        else:
            raise ValueError(f"Unknown store type: {store_type}")
        
        logger.info(f"Vector store manager initialized with {store_type}")
    
    def add_decision_explanation(
        self,
        campaign_id: int,
        arm_id: int,
        change_type: str,
        explanation: str,
        factors: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Add a decision explanation to the vector store.
        
        Args:
            campaign_id: Campaign ID
            arm_id: Arm ID
            change_type: Type of change (allocation_increase, etc.)
            explanation: Human-readable explanation
            factors: Dictionary of contributing factors
            timestamp: When the decision was made
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        document_id = f"decision_{campaign_id}_{arm_id}_{timestamp.isoformat()}"
        
        # Create searchable text
        text = f"""
        Campaign {campaign_id}, Arm {arm_id}
        Change Type: {change_type}
        Explanation: {explanation}
        Factors: {json.dumps(factors)}
        Timestamp: {timestamp.isoformat()}
        """
        
        metadata = {
            "campaign_id": campaign_id,
            "arm_id": arm_id,
            "change_type": change_type,
            "timestamp": timestamp.isoformat(),
            "factors": json.dumps(factors)
        }
        
        return self.store.add_document(document_id, text, metadata)
    
    def search_similar_decisions(
        self,
        query: str,
        campaign_id: Optional[int] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar past decisions.
        
        Args:
            query: Search query
            campaign_id: Optional campaign filter
            top_k: Number of results
        
        Returns:
            List of similar decisions
        """
        filters = None
        if campaign_id:
            filters = {"campaign_id": campaign_id}
        
        return self.store.search(query, top_k=top_k, filters=filters)
    
    def swap_store(self, store_type: str, **kwargs):
        """
        Swap to a different vector store implementation.
        
        Args:
            store_type: "chromadb" or "pinecone"
            **kwargs: Store-specific configuration
        """
        logger.info(f"Swapping vector store from {self.store_type} to {store_type}")
        self.store_type = store_type
        
        if store_type == "chromadb":
            self.store = ChromaDBStore(**kwargs)
        elif store_type == "pinecone":
            self.store = PineconeStore(**kwargs)
        else:
            raise ValueError(f"Unknown store type: {store_type}")


# Global store instance
_store_instance: Optional[VectorStoreManager] = None


def get_vector_store(store_type: str = "chromadb", **kwargs) -> VectorStoreManager:
    """
    Get or create global vector store instance.
    
    Args:
        store_type: "chromadb" or "pinecone"
        **kwargs: Store-specific configuration
    
    Returns:
        VectorStoreManager instance
    """
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStoreManager(store_type=store_type, **kwargs)
    return _store_instance
