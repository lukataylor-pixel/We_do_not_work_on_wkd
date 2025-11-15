"""NLP-based safety classifier for detecting sensitive information leakage."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.metrics.pairwise import cosine_similarity
import os
import pickle


class SafetyClassifier:
    """
    Probabilistic NLP-based safety classifier using sentence embeddings
    and cosine similarity to detect potential sensitive information leakage.
    """
    
    def __init__(
        self, 
        knowledge_base_path: str = "do_not_share.csv", 
        threshold: float = 0.7,
        precomputed_embeddings_path: Optional[str] = "precomputed_embeddings.pkl"
    ):
        """
        Initialize the safety classifier.
        
        Args:
            knowledge_base_path: Path to the CSV file containing sensitive information
            threshold: Similarity threshold above which responses are flagged (default: 0.7)
            precomputed_embeddings_path: Path to precomputed embeddings file (for deployment)
        """
        self.threshold = threshold
        self.knowledge_base_path = knowledge_base_path
        self.precomputed_embeddings_path = precomputed_embeddings_path
        self.sensitive_kb = None
        self.embedding_model = None
        self.sensitive_embeddings = None
        
        self._load_knowledge_base()
        self._initialize_embeddings()
    
    def _load_knowledge_base(self):
        """Load the sensitive information knowledge base from CSV."""
        if not os.path.exists(self.knowledge_base_path):
            raise FileNotFoundError(f"Knowledge base not found: {self.knowledge_base_path}")
        
        self.sensitive_kb = pd.read_csv(self.knowledge_base_path)
        print(f"Loaded {len(self.sensitive_kb)} sensitive information entries")
    
    def _initialize_embeddings(self):
        """
        Initialize embeddings - load precomputed embeddings for the knowledge base.
        For agent response encoding, we'll use OpenAI embeddings API (no heavy dependencies).
        """
        # Load precomputed embeddings for sensitive knowledge base
        if self.precomputed_embeddings_path and os.path.exists(self.precomputed_embeddings_path):
            try:
                print(f"Loading precomputed embeddings from {self.precomputed_embeddings_path}...")
                with open(self.precomputed_embeddings_path, 'rb') as f:
                    data = pickle.load(f)
                    # Ensure embeddings are NumPy arrays (critical for cosine_similarity)
                    self.sensitive_embeddings = np.array(data['embeddings'], dtype=np.float32)
                    # Verify knowledge base matches
                    if len(data['knowledge_base']) == len(self.sensitive_kb):
                        print(f"Loaded precomputed embeddings with shape: {self.sensitive_embeddings.shape}, dtype: {self.sensitive_embeddings.dtype}")
                        # Mark that we'll use OpenAI embeddings for runtime encoding
                        self.embedding_model = "openai"  # String marker to indicate OpenAI usage
                        return
                    else:
                        print("Warning: Knowledge base size mismatch...")
            except Exception as e:
                print(f"Error loading precomputed embeddings: {e}")
        
        # If precomputed embeddings not available, fall back to keyword matching
        print("Precomputed embeddings not found, using keyword fallback only...")
        self.embedding_model = None
        self.sensitive_embeddings = None
    
    def _encode_with_openai(self, text: str) -> Optional[np.ndarray]:
        """
        Encode text using OpenAI embeddings API.
        Uses text-embedding-3-small with dimensions=384 to match precomputed embeddings.
        
        Note: Replit AI Integrations currently only supports chat completions, not embeddings.
        This method will fall back to keyword matching for deployment.
        
        Args:
            text: Text to encode
            
        Returns:
            384-dimensional embedding vector, or None if encoding fails
        """
        try:
            # Try to use sentence-transformers if available (development only)
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode([text], show_progress_bar=False)[0]
            return embedding.astype(np.float32)
        except ImportError:
            # sentence-transformers not available (deployment), use keyword fallback
            return None
        except Exception as e:
            print(f"Error encoding with sentence-transformers: {e}")
            return None
    
    def _keyword_fallback_check(self, response: str) -> Dict[str, Any]:
        """
        Fallback safety check using basic keyword matching.
        Used when sentence transformers are not available.
        """
        response_lower = response.lower()
        
        dangerous_keywords = [
            'fico', 'credit score', 'algorithm', 'formula', 'threshold',
            'fraud detection', 'api endpoint', 'password', 'secret key',
            'override code', 'database', 'admin', 'master key',
            'bypass', 'loophole', 'credentials', 'social security','master', 
        ]
        
        max_score = 0
        matched_idx = 0
        
        for i, row in self.sensitive_kb.iterrows():
            sensitive_text = row['sensitive_info'].lower()
            keyword_matches = sum(1 for kw in dangerous_keywords if kw in response_lower and kw in sensitive_text)
            
            if keyword_matches > 0:
                score = min(keyword_matches * 0.25, 0.95)
                if score > max_score:
                    max_score = score
                    matched_idx = i
        
        return {
            'safe': max_score < self.threshold,
            'similarity_score': float(max_score),
            'matched_topic': self.sensitive_kb.iloc[matched_idx]['category'] if max_score >= self.threshold else None,
            'matched_text': self.sensitive_kb.iloc[matched_idx]['sensitive_info'] if max_score >= self.threshold else None,
            'method': 'keyword_fallback'
        }
    
    def check_safety(self, agent_response: str) -> Dict[str, Any]:
        """
        Check if an agent response contains sensitive information.
        
        Args:
            agent_response: The response text from the agent to evaluate
            
        Returns:
            Dictionary containing:
                - safe (bool): Whether the response is safe to send
                - similarity_score (float): Maximum similarity score
                - matched_topic (str): Category of matched sensitive info (if blocked)
                - matched_text (str): The sensitive info that was matched (if blocked)
                - method (str): Method used for classification
        """
        if not agent_response or len(agent_response.strip()) == 0:
            return {
                'safe': True,
                'similarity_score': 0.0,
                'matched_topic': None,
                'matched_text': None,
                'method': 'empty_response'
            }
        
        if self.sensitive_embeddings is None:
            return self._keyword_fallback_check(agent_response)
        
        try:
            # Generate embedding for the response using OpenAI embeddings API
            if self.embedding_model == "openai":
                response_embedding = self._encode_with_openai(agent_response)
                if response_embedding is None:
                    # OpenAI encoding failed, fall back to keyword matching
                    return self._keyword_fallback_check(agent_response)
            else:
                # No embedding method available, fall back to keyword matching
                return self._keyword_fallback_check(agent_response)
            
            # Reshape to 2D array for cosine_similarity
            response_embedding = response_embedding.reshape(1, -1)
            similarities = cosine_similarity(response_embedding, self.sensitive_embeddings)[0]
            
            max_similarity = float(np.max(similarities))
            matched_idx = int(np.argmax(similarities))
            
            is_safe = max_similarity < self.threshold
            
            return {
                'safe': is_safe,
                'similarity_score': max_similarity,
                'matched_topic': self.sensitive_kb.iloc[matched_idx]['category'] if not is_safe else None,
                'matched_text': self.sensitive_kb.iloc[matched_idx]['sensitive_info'] if not is_safe else None,
                'risk_level': self.sensitive_kb.iloc[matched_idx]['risk_level'] if not is_safe else None,
                'method': 'embedding_similarity'
            }
            
        except Exception as e:
            print(f"Error in safety check: {e}")
            return self._keyword_fallback_check(agent_response)
    
    def get_safe_alternative(self, original_response: str, safety_result: Dict[str, Any]) -> str:
        """
        Generate a safe alternative response when the original is blocked.
        
        Args:
            original_response: The original (blocked) response
            safety_result: The result from check_safety()
            
        Returns:
            A safe alternative message to send to the user
        """
        matched_category = safety_result.get('matched_topic', 'internal information')
        
        category_responses = {
            'fraud_rules': "I apologize, but I cannot provide details about our internal security systems. I can help you with account-related questions or report suspicious activity if you've noticed anything concerning.",
            'internal_models': "I cannot provide internal model details. For general information about our services, I'm happy to help with specific account questions.",
            'system_info': "I cannot share technical system details. How can I assist you with your banking needs today?",
            'credentials': "I cannot provide any credential or access information. If you need account access, please use our secure authentication system.",
            'customer_data': "I cannot share information about other customers. I can only help you with your own account information.",
            'security': "I cannot discuss specific security implementations. Rest assured, we use industry-standard security practices to protect your account.",
            'internal_policy': "I cannot share internal policy details. Let me help you with your account needs through our standard procedures.",
            'compliance': "I cannot discuss specific compliance details. Our practices follow all required regulations to protect you."
        }
        
        return category_responses.get(
            matched_category,
            "I apologize, but I cannot provide that specific information. Let me help you with your account-related questions instead."
        )
