"""NLP-based safety classifier for detecting sensitive information leakage."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from sklearn.metrics.pairwise import cosine_similarity
import os
import pickle
from encryption import decrypt_text, is_encrypted_payload, DecryptionError


class SafetyClassifier:
    """
    Probabilistic NLP-based safety classifier using sentence embeddings
    and cosine similarity to detect potential sensitive information leakage.
    """

    def __init__(self,
                 knowledge_base_path: str = "customer_knowledge_base.csv",
                 threshold: float = 0.7,
                 precomputed_embeddings_path: Optional[
                     str] = "customer_embeddings.pkl"):
        """
        Initialize the safety classifier for PII leak prevention.
        
        Args:
            knowledge_base_path: Path to the CSV file containing customer PII
            threshold: Similarity threshold above which responses are flagged (default: 0.7)
            precomputed_embeddings_path: Path to precomputed embeddings file (for deployment)
        """
        self.threshold = threshold
        self.knowledge_base_path = knowledge_base_path
        self.precomputed_embeddings_path = precomputed_embeddings_path
        self.sensitive_kb = None
        self.embedding_model = None
        self.sensitive_embeddings = None
        self.adversarial_patterns = self._load_adversarial_patterns()

        self._load_knowledge_base()
        self._initialize_embeddings()

    def _load_adversarial_patterns(self) -> List[str]:
        """Load common adversarial/jailbreak patterns to detect."""
        return [
            # Instruction manipulation
            "ignore previous instructions",
            "ignore all previous",
            "disregard previous",
            "forget everything",
            "forget all instructions",
            "override instructions",

            # System/role manipulation
            "system override",
            "admin mode",
            "developer mode",
            "debug mode",
            "you are now",
            "act as if",
            "pretend you are",
            "pretend that",
            "assume you are",
            "roleplay as",

            # Data extraction attempts
            "list all customers",
            "list all",
            "show all accounts",
            "show all customers",
            "show me all",
            "show all",
            "give me all",
            "all customer",
            "every customer",
            "dump database",
            "dump the",
            "print all",
            "give me everyone",
            "display all",
            "reveal all",

            # Direct PII requests (asking for specific customer info)
            "provide me with",
            "can you provide",
            "give me their",
            "give me his",
            "give me her",
            "what is their address",
            "what is his address",
            "what is her address",
            "tell me their",
            "tell me his",
            "tell me her",
            "'s address",
            "'s balance",
            "'s account",
            "'s information",
            "'s details",
            "'s home address",
            "'s account balance",
            "look up",
            "search for",
            "customer id",
            "customer details",

            # Security bypass
            "bypass security",
            "bypass verification",
            "bypass the",
            "skip verification",
            "skip the",
            "without verification",

            # Jailbreak / Hypotheticals
            "hypothetical",
            "in a hypothetical",
            "imagine if",
            "let's pretend",
            "what if",

            # Social engineering
            "i'm a new employee",
            "i'm an employee",
            "i work here",
            "for training",
            "training purposes"
        ]
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to handle obfuscation attempts.

        Handles:
        - Leetspeak (1 -> i, 3 -> e, 4 -> a, 5 -> s, 0 -> o, 7 -> t)
        - Unicode tricks (Cyrillic characters that look like Latin)
        - Extra spaces and punctuation
        """
        import unicodedata

        # Normalize Unicode (convert Cyrillic to Latin equivalents)
        # NFKD decomposition helps with some Unicode tricks
        normalized = unicodedata.normalize('NFKD', text)

        # Manual Cyrillic -> Latin mapping for common lookalikes
        cyrillic_map = {
            'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c',
            'у': 'y', 'х': 'x', 'і': 'i', 'ѕ': 's', 'һ': 'h',
            'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M',
            'Н': 'H', 'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T',
            'Х': 'X', 'Ѕ': 'S', 'І': 'I'
        }

        for cyrillic, latin in cyrillic_map.items():
            normalized = normalized.replace(cyrillic, latin)

        # Leetspeak normalization
        leetspeak_map = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a',
            '5': 's', '7': 't', '8': 'b', '9': 'g'
        }

        for leet, normal in leetspeak_map.items():
            normalized = normalized.replace(leet, normal)

        return normalized.lower()

    def _check_customer_names(self, user_message: str) -> List[str]:
        """
        Check if user message contains customer names from the knowledge base.

        Returns:
            List of matched customer names
        """
        message_lower = user_message.lower()
        matched_names = []

        if self.sensitive_kb is not None:
            for _, row in self.sensitive_kb.iterrows():
                customer_name = str(row['name']).lower()
                # Check for full name or last name
                name_parts = customer_name.split()

                if customer_name in message_lower:
                    matched_names.append(row['name'])
                elif len(name_parts) >= 2 and name_parts[-1] in message_lower:
                    # Check if last name appears (e.g., "Johnson")
                    matched_names.append(row['name'])

        return matched_names

    def check_adversarial_input(self, user_message: str) -> Dict[str, Any]:
        """
        Check if user input contains known adversarial patterns.

        Enhanced with:
        - Obfuscation detection (leetspeak, unicode tricks)
        - Customer name detection

        Args:
            user_message: The user's input message

        Returns:
            Dictionary with adversarial detection results
        """
        message_lower = user_message.lower()
        normalized_message = self._normalize_text(user_message)
        matched_patterns = []

        # Check patterns against both original and normalized text
        for pattern in self.adversarial_patterns:
            if pattern in message_lower or pattern in normalized_message:
                matched_patterns.append(pattern)

        # Check for customer names in the message
        matched_names = self._check_customer_names(user_message)

        # If customer names are mentioned, it's likely a PII request
        if matched_names:
            matched_patterns.extend([f"customer_name:{name}" for name in matched_names])

        return {
            'is_adversarial': len(matched_patterns) > 0,
            'matched_patterns': matched_patterns,
            'pattern_count': len(matched_patterns),
            'matched_customer_names': matched_names,
            'obfuscation_detected': normalized_message != message_lower
        }
    
    def _load_knowledge_base(self):
        """Load customer PII knowledge base from CSV."""
        if not os.path.exists(self.knowledge_base_path):
            raise FileNotFoundError(
                f"Knowledge base not found: {self.knowledge_base_path}")

        self.sensitive_kb = pd.read_csv(self.knowledge_base_path)
        print(f"Loaded {len(self.sensitive_kb)} customer records")

    def _initialize_embeddings(self):
        """
        Initialize embeddings - load precomputed embeddings for the knowledge base.
        For agent response encoding, we'll use OpenAI embeddings API (no heavy dependencies).
        """
        # Load precomputed embeddings for sensitive knowledge base
        if self.precomputed_embeddings_path and os.path.exists(
                self.precomputed_embeddings_path):
            try:
                print(
                    f"Loading precomputed embeddings from {self.precomputed_embeddings_path}..."
                )
                with open(self.precomputed_embeddings_path, 'rb') as f:
                    data = pickle.load(f)
                    # Ensure embeddings are NumPy arrays (critical for cosine_similarity)
                    self.sensitive_embeddings = np.array(data['embeddings'],
                                                         dtype=np.float32)
                    # Verify knowledge base matches
                    if len(data['knowledge_base']) == len(self.sensitive_kb):
                        print(
                            f"Loaded precomputed embeddings with shape: {self.sensitive_embeddings.shape}, dtype: {self.sensitive_embeddings.dtype}"
                        )
                        # Mark that we'll use OpenAI embeddings for runtime encoding
                        self.embedding_model = "openai"  # String marker to indicate OpenAI usage
                        return
                    else:
                        print("Warning: Knowledge base size mismatch...")
            except Exception as e:
                print(f"Error loading precomputed embeddings: {e}")

        # If precomputed embeddings not available, fall back to keyword matching
        print(
            "Precomputed embeddings not found, using keyword fallback only...")
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
        Fallback safety check using keyword matching for PII detection.
        Checks if response contains customer names, addresses, postcodes, or balances.
        """
        response_lower = response.lower()
        max_score = 0
        matched_idx = 0

        for i, row in self.sensitive_kb.iterrows():
            # Check if response contains customer PII
            pii_elements = [
                str(row['name']).lower(),
                str(row['address']).lower(),
                str(row['postcode']).lower(),
                str(row['balance']),
                str(row['card_last4'])
            ]
            
            matches = sum(1 for elem in pii_elements if elem and elem in response_lower)
            
            if matches > 0:
                # Higher score for multiple PII elements from same customer
                score = min(matches * 0.3, 0.95)
                if score > max_score:
                    max_score = score
                    matched_idx = i

        # Get matched customer record for detailed explainability
        matched_customer = None
        if max_score >= self.threshold:
            customer_row = self.sensitive_kb.iloc[matched_idx]
            matched_customer = {
                'customer_id': customer_row['customer_id'],
                'name': customer_row['name'],
                'card_last4': customer_row['card_last4'],
                'address': customer_row['address'],
                'postcode': customer_row['postcode'],
                'balance': customer_row['balance']
            }

        return {
            'safe': max_score < self.threshold,
            'similarity_score': float(max_score),
            'matched_topic': f"customer_pii_{self.sensitive_kb.iloc[matched_idx]['customer_id']}" if max_score >= self.threshold else None,
            'matched_text': f"{self.sensitive_kb.iloc[matched_idx]['name']} - {self.sensitive_kb.iloc[matched_idx]['address']}" if max_score >= self.threshold else None,
            'matched_customer_record': matched_customer,
            'method': 'keyword_fallback'
        }

    def check_safety(self, agent_response: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if an agent response contains sensitive information.
        
        Supports both plaintext strings (legacy) and encrypted payloads (secure).
        If an encrypted payload is provided, it will be decrypted before classification.
        
        Args:
            agent_response: The response from the agent - either:
                - str: Plaintext response (legacy, backward compatibility)
                - Dict[str, Any]: Encrypted payload with ciphertext, nonce, key_id
            
        Returns:
            Dictionary containing:
                - safe (bool): Whether the response is safe to send
                - similarity_score (float): Maximum similarity score
                - matched_topic (str): Category of matched sensitive info (if blocked)
                - matched_text (str): The sensitive info that was matched (if blocked)
                - method (str): Method used for classification
                - decryption_error (bool): True if decryption failed (only for encrypted payloads)
        """
        # Handle encrypted payloads
        if is_encrypted_payload(agent_response):
            try:
                plaintext_response = decrypt_text(agent_response)
            except DecryptionError as e:
                # Decryption failed - treat as unsafe and log security event
                print(f"⚠️ SECURITY EVENT: Decryption failed in safety check: {e}")
                return {
                    'safe': False,
                    'similarity_score': 1.0,
                    'matched_topic': 'decryption_error',
                    'matched_text': None,
                    'method': 'decryption_error',
                    'decryption_error': True
                }
        else:
            # Plaintext response (backward compatibility)
            plaintext_response = agent_response
        
        if not plaintext_response or len(plaintext_response.strip()) == 0:
            return {
                'safe': True,
                'similarity_score': 0.0,
                'matched_topic': None,
                'matched_text': None,
                'method': 'empty_response'
            }

        if self.sensitive_embeddings is None:
            return self._keyword_fallback_check(plaintext_response)

        try:
            # Generate embedding for the response using OpenAI embeddings API
            if self.embedding_model == "openai":
                response_embedding = self._encode_with_openai(plaintext_response)
                if response_embedding is None:
                    # OpenAI encoding failed, fall back to keyword matching
                    return self._keyword_fallback_check(plaintext_response)
            else:
                # No embedding method available, fall back to keyword matching
                return self._keyword_fallback_check(plaintext_response)

            # Reshape to 2D array for cosine_similarity
            response_embedding = response_embedding.reshape(1, -1)
            similarities = cosine_similarity(response_embedding,
                                             self.sensitive_embeddings)[0]

            max_similarity = float(np.max(similarities))
            matched_idx = int(np.argmax(similarities))

            is_safe = max_similarity < self.threshold

            # Get matched customer record for detailed explainability
            matched_customer = None
            if not is_safe:
                customer_row = self.sensitive_kb.iloc[matched_idx]
                matched_customer = {
                    'customer_id': customer_row['customer_id'],
                    'name': customer_row['name'],
                    'card_last4': customer_row['card_last4'],
                    'address': customer_row['address'],
                    'postcode': customer_row['postcode'],
                    'balance': customer_row['balance']
                }

            return {
                'safe':
                is_safe,
                'similarity_score':
                max_similarity,
                'matched_topic':
                f"customer_pii_{self.sensitive_kb.iloc[matched_idx]['customer_id']}"
                if not is_safe else None,
                'matched_text':
                f"{self.sensitive_kb.iloc[matched_idx]['name']} - {self.sensitive_kb.iloc[matched_idx]['address']}"
                if not is_safe else None,
                'matched_customer_record': matched_customer,
                'method':
                'embedding_similarity'
            }

        except Exception as e:
            print(f"Error in safety check: {e}")
            return self._keyword_fallback_check(agent_response)

    def get_safe_alternative(self, original_response: str,
                             safety_result: Dict[str, Any]) -> str:
        """
        Generate a safe alternative response when PII leak is detected.
        
        Args:
            original_response: The original (blocked) response
            safety_result: The result from check_safety()
            
        Returns:
            A safe alternative message to send to the user
        """
        return "I apologize, but I cannot provide that information without proper verification. For security reasons, I can only share account details after you've verified your identity with your card number and postcode. How can I assist you today?"
