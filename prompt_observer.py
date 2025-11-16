"""
Pre-LLM Prompt Observer for Advanced Adversarial Detection

This module analyzes user prompts BEFORE they reach the LLM using:
1. Homograph attack detection (Unicode confusables)
2. Contextual embedding similarity to known-bad prompts
3. Steganography-like pattern detection
4. Greedy coordinate gradient-style adversarial prompting detection
"""

import re
import unicodedata
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter
import math


class PromptObserver:
    """
    Pre-LLM observer that analyzes user prompts for sophisticated adversarial attacks.
    """
    
    def __init__(self, blocked_prompts_kb: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the prompt observer.
        
        Args:
            blocked_prompts_kb: List of previously blocked prompts with embeddings
        """
        self.blocked_prompts_kb = blocked_prompts_kb or []
        self.kb_texts = [p.get('prompt', '') for p in self.blocked_prompts_kb]
        self.kb_embeddings = [p.get('embedding') for p in self.blocked_prompts_kb if p.get('embedding') is not None]
        
        # Detection thresholds
        self.SIMILARITY_THRESHOLD = 0.85
        self.ENTROPY_THRESHOLD_HIGH = 4.5
        self.ENTROPY_THRESHOLD_LOW = 2.0
        self.HOMOGRAPH_THRESHOLD = 0.15
        self.GRADIENT_SIMILARITY_THRESHOLD = 0.92
        
    def analyze_user_prompt(self, prompt: str, session_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze an incoming user prompt using multiple detection techniques.
        
        Args:
            prompt: The user's input text
            session_context: Optional session context with previous prompts
            
        Returns:
            Dictionary with:
                - risk_score: float (0-1)
                - flags: dict of detection flags
                - explanations: list of explanations
                - details: detailed results from each detector
        """
        results = {
            'risk_score': 0.0,
            'flags': {
                'homograph': False,
                'context_similar_to_blocked': False,
                'steganography': False,
                'greedy_coordinate_gradient': False,
            },
            'explanations': [],
            'details': {}
        }
        
        # 1. Homograph detection
        homograph_flag, homograph_explanation = self.detect_homograph(prompt)
        results['flags']['homograph'] = homograph_flag
        if homograph_flag:
            results['explanations'].append(homograph_explanation)
            results['risk_score'] += 0.3
            results['details']['homograph'] = homograph_explanation
        
        # 2. Contextual similarity to blocked prompts
        if self.kb_embeddings:
            similar_flag, similarity_score, similar_explanation = self.detect_contextual_similarity(prompt)
            results['flags']['context_similar_to_blocked'] = similar_flag
            if similar_flag:
                results['explanations'].append(similar_explanation)
                results['risk_score'] += 0.4
                results['details']['similarity'] = {
                    'score': similarity_score,
                    'explanation': similar_explanation
                }
        
        # 3. Steganography detection
        steg_flag, steg_explanation = self.detect_steganography(prompt)
        results['flags']['steganography'] = steg_flag
        if steg_flag:
            results['explanations'].append(steg_explanation)
            results['risk_score'] += 0.25
            results['details']['steganography'] = steg_explanation
        
        # 4. Greedy coordinate gradient detection
        if session_context:
            gradient_flag, gradient_explanation = self.detect_greedy_coordinate_gradient(
                prompt, session_context
            )
            results['flags']['greedy_coordinate_gradient'] = gradient_flag
            if gradient_flag:
                results['explanations'].append(gradient_explanation)
                results['risk_score'] += 0.35
                results['details']['gradient'] = gradient_explanation
        
        # Normalize risk score to [0, 1]
        results['risk_score'] = min(1.0, results['risk_score'])
        
        return results
    
    def detect_homograph(self, prompt: str) -> Tuple[bool, Optional[str]]:
        """
        Detect homograph attacks using Unicode confusables.
        
        Checks for:
        - Mixed scripts (Latin + Cyrillic + Greek)
        - High ratio of visually similar non-ASCII characters
        - Unicode normalization anomalies
        
        Args:
            prompt: User input text
            
        Returns:
            (flag, explanation)
        """
        if not prompt:
            return False, None
        
        # Normalize to NFKC for comparison
        normalized = unicodedata.normalize('NFKC', prompt)
        
        # Count characters by script
        scripts = Counter()
        confusable_count = 0
        total_chars = 0
        
        # Known confusable character pairs (Latin vs Cyrillic/Greek)
        confusables = {
            'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'у': 'y', 'х': 'x',  # Cyrillic
            'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'Х': 'X',
            'α': 'a', 'ο': 'o', 'τ': 't', 'ν': 'v',  # Greek
        }
        
        for char in prompt:
            if not char.isspace():
                total_chars += 1
                
                # Check if character is in confusables
                if char in confusables:
                    confusable_count += 1
                
                # Detect script
                try:
                    script_name = unicodedata.name(char, '').split()[0]
                    if 'LATIN' in script_name:
                        scripts['LATIN'] += 1
                    elif 'CYRILLIC' in script_name:
                        scripts['CYRILLIC'] += 1
                    elif 'GREEK' in script_name:
                        scripts['GREEK'] += 1
                except (ValueError, IndexError):
                    pass
        
        if total_chars == 0:
            return False, None
        
        # Check for mixed scripts
        script_count = sum(1 for count in scripts.values() if count > 0)
        confusable_ratio = confusable_count / total_chars
        
        # Flag if multiple scripts or high confusable ratio
        if script_count >= 2 and confusable_ratio > 0.1:
            return True, f"Homograph attack detected: Mixed scripts ({', '.join(scripts.keys())}) with {confusable_ratio:.1%} confusable characters"
        
        if confusable_ratio > self.HOMOGRAPH_THRESHOLD:
            return True, f"Homograph attack detected: {confusable_ratio:.1%} of characters are visually confusable"
        
        # Check for normalization changes
        if normalized != prompt and len(normalized) < len(prompt) * 0.8:
            return True, f"Homograph attack detected: Significant Unicode normalization changes ({len(prompt)} -> {len(normalized)} chars)"
        
        return False, None
    
    def detect_contextual_similarity(self, prompt: str) -> Tuple[bool, float, Optional[str]]:
        """
        Detect similarity to previously blocked prompts using embeddings.
        
        Args:
            prompt: User input text
            
        Returns:
            (flag, similarity_score, explanation)
        """
        if not self.kb_embeddings:
            return False, 0.0, None
        
        try:
            # Use sentence-transformers if available, otherwise return False
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Compute embedding for current prompt
            prompt_embedding = model.encode([prompt], show_progress_bar=False)[0]
            
            # Compute cosine similarities to all blocked prompts
            max_similarity = 0.0
            most_similar_idx = -1
            
            for idx, kb_embedding in enumerate(self.kb_embeddings):
                if kb_embedding is None:
                    continue
                
                # Cosine similarity
                similarity = np.dot(prompt_embedding, kb_embedding) / (
                    np.linalg.norm(prompt_embedding) * np.linalg.norm(kb_embedding)
                )
                
                if similarity > max_similarity:
                    max_similarity = similarity
                    most_similar_idx = idx
            
            if max_similarity >= self.SIMILARITY_THRESHOLD and most_similar_idx >= 0:
                similar_prompt = self.kb_texts[most_similar_idx][:100]
                return True, max_similarity, f"High similarity ({max_similarity:.2%}) to blocked prompt: '{similar_prompt}...'"
            
            return False, max_similarity, None
            
        except ImportError:
            # sentence-transformers not available, use keyword fallback
            return self._keyword_similarity_fallback(prompt)
    
    def _keyword_similarity_fallback(self, prompt: str) -> Tuple[bool, float, Optional[str]]:
        """Fallback similarity detection using keyword matching."""
        prompt_lower = prompt.lower()
        max_overlap = 0.0
        most_similar_prompt = None
        
        for kb_prompt in self.kb_texts:
            kb_lower = kb_prompt.lower()
            
            # Simple word overlap
            prompt_words = set(prompt_lower.split())
            kb_words = set(kb_lower.split())
            
            if not prompt_words or not kb_words:
                continue
            
            overlap = len(prompt_words & kb_words) / len(prompt_words | kb_words)
            
            if overlap > max_overlap:
                max_overlap = overlap
                most_similar_prompt = kb_prompt
        
        if max_overlap >= 0.6:
            return True, max_overlap, f"Keyword overlap ({max_overlap:.1%}) with blocked prompt: '{most_similar_prompt[:100]}...'"
        
        return False, max_overlap, None
    
    def detect_steganography(self, prompt: str) -> Tuple[bool, Optional[str]]:
        """
        Detect steganography-like patterns in prompts.
        
        Checks for:
        - High/low Shannon entropy (random-looking text)
        - Suspicious character class ratios
        - Base64-like encoding patterns
        - Repeated substring patterns
        
        Args:
            prompt: User input text
            
        Returns:
            (flag, explanation)
        """
        if not prompt or len(prompt) < 20:
            return False, None
        
        flags = []
        
        # 1. Shannon entropy
        entropy = self._calculate_entropy(prompt)
        if entropy > self.ENTROPY_THRESHOLD_HIGH:
            flags.append(f"Very high entropy ({entropy:.2f}) suggests random/encoded data")
        elif entropy < self.ENTROPY_THRESHOLD_LOW and len(prompt) > 50:
            flags.append(f"Abnormally low entropy ({entropy:.2f}) for prompt length")
        
        # 2. Character class ratios
        total = len(prompt)
        letters = sum(c.isalpha() for c in prompt)
        digits = sum(c.isdigit() for c in prompt)
        punct = sum(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`' for c in prompt)
        spaces = sum(c.isspace() for c in prompt)
        
        letter_ratio = letters / total
        digit_ratio = digits / total
        punct_ratio = punct / total
        
        if digit_ratio > 0.4:
            flags.append(f"Excessive digits ({digit_ratio:.1%}) suggests encoding")
        if punct_ratio > 0.3:
            flags.append(f"Excessive punctuation ({punct_ratio:.1%}) suggests obfuscation")
        if letter_ratio < 0.3 and total > 50:
            flags.append(f"Very low letter ratio ({letter_ratio:.1%}) for text length")
        
        # 3. Base64-like pattern detection
        base64_pattern = r'[A-Za-z0-9+/]{40,}={0,2}'
        if re.search(base64_pattern, prompt):
            flags.append("Base64-like encoding pattern detected")
        
        # 4. Repeated substring patterns (like "abcabcabc...")
        if self._has_repeated_patterns(prompt):
            flags.append("Repeated substring patterns detected")
        
        # 5. Very long prompt with low dictionary coverage
        if len(prompt) > 200:
            word_like_ratio = self._dictionary_word_coverage(prompt)
            if word_like_ratio < 0.3:
                flags.append(f"Low dictionary word coverage ({word_like_ratio:.1%}) for long prompt")
        
        if flags:
            return True, "Steganography patterns: " + "; ".join(flags)
        
        return False, None
    
    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text."""
        if not text:
            return 0.0
        
        char_counts = Counter(text)
        total_chars = len(text)
        
        entropy = 0.0
        for count in char_counts.values():
            probability = count / total_chars
            entropy -= probability * math.log2(probability)
        
        return entropy
    
    def _has_repeated_patterns(self, text: str, min_length: int = 3) -> bool:
        """Detect repeated substring patterns."""
        text_clean = re.sub(r'\s+', '', text.lower())
        
        if len(text_clean) < 20:
            return False
        
        # Check for repeated patterns of length 3-10
        for pattern_len in range(min_length, min(11, len(text_clean) // 4)):
            for i in range(len(text_clean) - pattern_len * 3):
                pattern = text_clean[i:i+pattern_len]
                # Check if pattern repeats at least 3 times consecutively
                repeated = pattern * 3
                if repeated in text_clean[i:i+pattern_len*4]:
                    return True
        
        return False
    
    def _dictionary_word_coverage(self, text: str) -> float:
        """Estimate ratio of dictionary-like words in text."""
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
        
        if not words:
            return 0.0
        
        # Simple heuristic: words with reasonable vowel/consonant ratio
        vowels = set('aeiouAEIOU')
        valid_words = 0
        
        for word in words:
            vowel_count = sum(1 for c in word if c in vowels)
            vowel_ratio = vowel_count / len(word)
            
            # Reasonable English words have 20-60% vowels
            if 0.2 <= vowel_ratio <= 0.6:
                valid_words += 1
        
        return valid_words / len(words)
    
    def detect_greedy_coordinate_gradient(
        self, 
        prompt: str, 
        session_context: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Detect greedy coordinate gradient-style adversarial prompting.
        
        This detects iterative refinement attacks where users make small edits
        to prompts across multiple attempts to bypass defenses.
        
        Args:
            prompt: Current user prompt
            session_context: Session data with previous prompts
            
        Returns:
            (flag, explanation)
        """
        # Extract previous prompts from session
        previous_prompts = session_context.get('previous_prompts', [])
        
        if len(previous_prompts) < 2:
            return False, None
        
        # Analyze recent prompts (last 5)
        recent_prompts = previous_prompts[-5:]
        
        # Calculate similarities between consecutive prompts
        high_similarity_count = 0
        edit_distances = []
        
        for prev_prompt in recent_prompts:
            similarity = self._text_similarity(prompt, prev_prompt)
            edit_dist = self._levenshtein_distance(prompt, prev_prompt)
            
            edit_distances.append(edit_dist)
            
            # High similarity but not identical
            if similarity >= self.GRADIENT_SIMILARITY_THRESHOLD and prompt != prev_prompt:
                high_similarity_count += 1
        
        # Pattern: Multiple near-duplicate prompts with small edits
        if high_similarity_count >= 2:
            avg_edit_dist = sum(edit_distances) / len(edit_distances)
            return True, f"Greedy gradient pattern detected: {high_similarity_count} similar prompts with avg edit distance {avg_edit_dist:.0f}"
        
        # Check if prompts are incrementally getting more adversarial
        # (e.g., adding jailbreak keywords gradually)
        adversarial_keywords = [
            'ignore', 'disregard', 'override', 'admin', 'system',
            'jailbreak', 'bypass', 'disable', 'unrestricted'
        ]
        
        keyword_counts = []
        for prev_prompt in recent_prompts + [prompt]:
            count = sum(1 for kw in adversarial_keywords if kw in prev_prompt.lower())
            keyword_counts.append(count)
        
        # Increasing adversarial keyword count suggests iterative probing
        if len(keyword_counts) >= 3:
            increasing = all(keyword_counts[i] <= keyword_counts[i+1] 
                           for i in range(len(keyword_counts)-1))
            if increasing and keyword_counts[-1] > 0:
                return True, f"Incremental adversarial keyword addition detected: {keyword_counts}"
        
        return False, None
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using word overlap (Jaccard)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


# Global observer instance (lazy-loaded)
_observer_instance: Optional[PromptObserver] = None


def get_observer(blocked_prompts_kb: Optional[List[Dict]] = None) -> PromptObserver:
    """Get or create the global prompt observer instance."""
    global _observer_instance
    
    if _observer_instance is None or blocked_prompts_kb is not None:
        _observer_instance = PromptObserver(blocked_prompts_kb)
    
    return _observer_instance


def analyze_user_prompt(
    prompt: str, 
    session_context: Optional[Dict] = None,
    blocked_prompts_kb: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Main entry point for analyzing user prompts.
    
    Args:
        prompt: User's input text
        session_context: Optional session context with previous prompts
        blocked_prompts_kb: Optional KB of blocked prompts (will update observer if provided)
        
    Returns:
        Analysis results with risk_score, flags, and explanations
    """
    observer = get_observer(blocked_prompts_kb)
    return observer.analyze_user_prompt(prompt, session_context)
