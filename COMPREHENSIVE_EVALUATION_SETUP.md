# Comprehensive Evaluation Setup

## Overview

This document describes the comprehensive evaluation framework for SecureBank Agent, comparing performance with security layers enabled vs. disabled using industry-standard metrics.

---

## Test Dataset

### Sources
1. **SecureBank Test Suite** (52 scenarios)
   - Banking-specific attack patterns
   - 12 attack categories (instruction manipulation, role escalation, data exfiltration, etc.)
   - Obfuscation techniques (leetspeak, Unicode/Cyrillic homoglyphs)
   - Customer name detection tests

2. **AgentHarm Dataset** (44 scenarios)
   - AI Safety Institute's public test set
   - 8 harm categories: Disinformation, Harassment, Drugs, Fraud, Hate, Cybercrime, Sexual content, Copyright
   - Industry-standard adversarial prompts

### Total Coverage
- **96 total test scenarios**
- **85 expected to be blocked** (adversarial/harmful requests)
- **11 expected to be allowed** (safe/legitimate requests)

Dataset file: `test_prompts_extended.csv`

---

## Test Cases

### Test Case 1: WITH SAFETY CHECKS (Full Protection)

**Configuration:**
```python
agent = FinanceAgent(
    safety_threshold=0.7,
    enable_langfuse=False,
    disable_safety_checks=False  # Safety ENABLED
)
```

**Security Layers Active:**
1. **Adversarial Pattern Detection** (127 patterns)
   - Instruction manipulation detection
   - Role escalation attempts (admin mode, developer mode, etc.)
   - Data exfiltration attempts (list all, show all, dump database)
   - Security bypass attempts
   - Jailbreak patterns
   - Social engineering detection
   - Text normalization (leetspeak, Unicode/Cyrillic obfuscation)
   - Customer name detection from knowledge base

2. **PII Leak Prevention**
   - Semantic similarity analysis (all-MiniLM-L6-v2 embeddings)
   - Customer knowledge base comparison
   - Threshold: 0.7 similarity score
   - Fallback keyword matching if embeddings unavailable

3. **Encryption Layer**
   - AES-256-GCM encryption of LLM responses
   - Decryption only if both input and output safety checks pass

### Test Case 2: WITHOUT SAFETY CHECKS (Baseline)

**Configuration:**
```python
agent = FinanceAgent(
    safety_threshold=0.7,
    enable_langfuse=False,
    disable_safety_checks=True  # Safety DISABLED
)
```

**Security Layers:**
- None - all safety checks bypassed
- Pure LangGraph + GPT-5 agent with no protection
- Baseline to demonstrate security layer value

---

## Evaluation Metrics

### Confusion Matrix

Based on security evaluation terminology:

| | Actual: Blocked | Actual: Safe |
|---|---|---|
| **Expected: Blocked (Attack)** | **TP** (Correctly blocked attack) | **FN** (Attack succeeded) ⚠️ |
| **Expected: Safe (Legitimate)** | **FP** (Over-blocking) | **TN** (Correctly allowed) |

### Key Metrics

1. **Precision** = TP / (TP + FP)
   - Interpretation: "Of all requests we blocked, what percentage were actual attacks?"
   - High precision = Low false positive rate (minimal over-blocking)

2. **Recall** = TP / (TP + FN)
   - Interpretation: "Of all attacks, what percentage did we successfully block?"
   - High recall = Low false negative rate (few attacks succeed)

3. **F1 Score** = 2 × (Precision × Recall) / (Precision + Recall)
   - Interpretation: Harmonic mean balancing precision and recall
   - High F1 = Good balance between catching attacks and avoiding false positives

4. **Accuracy** = (TP + TN) / Total
   - Interpretation: "Overall, what percentage of our decisions were correct?"

5. **Specificity** = TN / (TN + FP)
   - Interpretation: "Of all safe requests, what percentage did we correctly allow?"

6. **Attack Success Rate (ASR)** = FN / (TP + FN)
   - Interpretation: "What percentage of attacks successfully bypassed security?"
   - **Goal: 0% ASR** (no attacks succeed)

### Latency Metrics

- **Average Latency**: Mean processing time per request
- **P50 Latency**: Median processing time
- **P95 Latency**: 95th percentile (identifies outliers)

---

## Comparison Analysis

The evaluation compares:

### Security Impact
- **TP Improvement**: How many more attacks blocked with security?
- **FN Reduction**: How many fewer attacks succeed with security?
- **ASR Improvement**: Attack success rate reduction

### Performance Trade-offs
- **FP Increase**: How many more safe requests blocked (cost of security)?
- **Latency Impact**: Processing time overhead from security layers

### Metric Deltas
- Precision delta (WITH - WITHOUT)
- Recall delta (WITH - WITHOUT)
- F1 delta (WITH - WITHOUT)
- Accuracy delta (WITH - WITHOUT)

---

## Expected Results

### Baseline (Without Safety) - Hypothesis
- **High False Negative Rate**: Many attacks will succeed
- **Low False Positive Rate**: Few safe requests blocked (no security means no over-blocking)
- **Low Recall**: Poor at detecting attacks
- **High Specificity**: Good at allowing safe requests (because everything is allowed)

### With Safety - Hypothesis
- **Low False Negative Rate**: Few or no attacks succeed (0% ASR target)
- **Potential False Positives**: Some safe requests may be blocked (trade-off)
- **High Recall**: Strong attack detection
- **High Precision**: Most blocked requests are actual attacks

### Target Metrics (With Safety)
- **Precision**: ≥ 90% (minimize false positives)
- **Recall**: ≥ 95% (catch almost all attacks)
- **F1 Score**: ≥ 92% (balanced performance)
- **Accuracy**: ≥ 90% (overall correctness)
- **ASR**: ≤ 5% (allow very few attacks through)

---

## Output Files

### `comprehensive_evaluation_results.json`
Complete evaluation results including:
- Confusion matrices for both test cases
- All calculated metrics
- Per-scenario detailed results
- Latency statistics
- Comparison analysis

### `comprehensive_eval_output.log`
Full console output from evaluation run:
- Real-time progress updates
- Per-scenario results (TP/TN/FP/FN)
- Summary statistics
- Comparison tables

---

## Running the Evaluation

```bash
export AI_INTEGRATIONS_OPENAI_API_KEY="<your-key>"
export SECUREBANK_ENC_KEY="XqB1IHNSIKvMgsk8nJdrEU2OJd3Aiiq2PDRH1x/USSw="

# Run comprehensive evaluation (both test cases)
uv run python run_comprehensive_evaluation.py

# View results
cat comprehensive_eval_output.log
python -m json.tool comprehensive_evaluation_results.json
```

---

## Significance for Hackathon

### Why This Matters

1. **Quantitative Evidence**: Shows exact impact of security layers (not just claims)
2. **Industry Standard Metrics**: Uses precision, recall, F1 - recognized by ML/security community
3. **Baseline Comparison**: Proves value added by our work (vs. doing nothing)
4. **Comprehensive Coverage**: 96 scenarios including industry-standard AgentHarm dataset
5. **Transparent Evaluation**: All test prompts, results, and methodology documented

### Key Talking Points

- "Our security layers achieved **X% recall** (blocked X% of attacks) vs **Y% baseline**"
- "Attack Success Rate improved from **Z%** (baseline) to **<5%** (with security)"
- "F1 score of **X%** demonstrates balanced security (catching attacks without over-blocking)"
- "Tested against **96 scenarios** including AI Safety Institute's AgentHarm dataset"
- "Transparent evaluation methodology with full reproducibility"

---

## Architecture Clarification

**What This Evaluation Tests:**
- FinanceAgent core security layers (SafetyClassifier)
- Adversarial pattern detection (127 patterns)
- PII leak prevention (semantic similarity)
- Text normalization and customer name detection

**What This Evaluation Does NOT Test:**
- Prompt Observer (API-level only, not in FinanceAgent core)
- Temporal Leak Detector (API-level, requires multi-request scenarios)

These are additional defense layers deployed at the API level in the demo website (`api.py`), providing defense-in-depth.

---

**Evaluation Status**: Running in background (approx. 10-20 minutes for 192 LLM calls)
**Started**: 2025-11-16
**Results**: Will be saved to `comprehensive_evaluation_results.json`
