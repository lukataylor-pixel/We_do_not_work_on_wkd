# SecureBank Support Agent: Red-Teaming Defense & Glass-Box Observability Demo

## Overview

This hackathon project demonstrates a SecureBank customer support agent with multi-layered security defenses against adversarial attacks and PII leakage. Built for Track C (Red-Teaming Defense) and Track B (Glass-Box Observability), it showcases:
1. **Adversarial Pattern Detection**: Real-time detection of jailbreak attempts, prompt injections, and role manipulation
2. **PII Leak Prevention**: Similarity-based checking to prevent customer data leakage via semantic matching
3. **Verification-Based Access**: Card number + postcode verification flow before revealing sensitive information
4. **Comprehensive Observability**: LangFuse tracing with interactive dashboards showing adversarial attempts and PII leak blocks in real-time

The demo includes 30 fake customer records with realistic PII (names, addresses, card numbers, balances) and test scenarios to demonstrate both happy-path operations and successful defense against adversarial prompts.

## User Preferences

None specified yet.

## System Architecture

The SecureBank Support Agent project is structured around five main components, each serving a distinct security or observability function:

### Core Components

1.  **SecureBank Support Agent** (`finance_agent.py`): A LangGraph-based conversational agent powered by GPT-5 that implements verification-based access control. Features two tools: `verify_customer` (validates card_last4 + postcode) and `get_customer_balance` (returns balance only after verification). Integrated with LangFuse for comprehensive tracing and adversarial pattern detection. **Encrypts all LLM outputs immediately** using AES-256-GCM.
2.  **Safety Classifier** (`safety_classifier.py`): Dual-purpose security module:
    - **Adversarial Pattern Detection**: Detects jailbreak attempts via keyword matching (54 patterns including "ignore previous instructions", "list all", "admin mode", "provide [name]'s address")
    - **PII Leak Prevention**: Uses precomputed 384-dimensional embeddings from `all-MiniLM-L6-v2` model to check output similarity against customer PII database. Falls back to keyword matching for deployment compatibility.
3.  **Encryption System** (`encryption.py`): AES-256-GCM authenticated encryption module ensuring raw LLM text is never stored in plaintext. Features `encrypt_text`, `decrypt_text`, and `get_payload_preview` helpers with 96-bit random nonces and base64 encoding for storage compatibility.
4.  **Customer Knowledge Base** (`customer_knowledge_base.csv` + `customer_embeddings.pkl`): Contains 30 realistic fake customer records with PII: customer_id, name, card_last4, address, postcode, balance. Embeddings are precomputed for efficient similarity checking.
5.  **Shared Telemetry** (`shared_telemetry.py`): SQLite-based cross-process logging system that tracks both PII leak attempts and adversarial input patterns for dashboard analytics. **Stores only encrypted payloads** (ciphertext, nonce, key_id).

### Architectural Patterns & Design Decisions

*   **Defense-in-Depth Security**: Multi-layered protection with adversarial pattern detection on input, PII similarity checking on output, verification-based access control for sensitive operations, and end-to-end encryption for all LLM outputs.
*   **Verification-First Design**: Agent cannot reveal account balances without successful card_last4 + postcode verification against customer knowledge base. This prevents data leakage even if adversarial prompts bypass other defenses.
*   **Real-time Safety Intervention**: 
    - **Input Layer**: Adversarial pattern detection flags jailbreak attempts (54 patterns), logged to LangFuse and telemetry
    - **Output Layer**: PII leak prevention via similarity checking against customer embeddings (threshold: 0.7)
    - **Encryption Layer**: AES-256-GCM encrypts LLM outputs immediately, stores only ciphertext in logs/telemetry
*   **Observability-Driven Design**: Deep LangFuse integration tracking adversarial attempts, verification flows, PII leak blocks, and agent reasoning. Unified dashboard shows real-time security events with adversarial pattern indicators. **Agent Decision Flow Visualizer** provides 4-stage interactive timeline with explainability panels.
*   **Hybrid Security Approach**: Semantic similarity for PII detection (development) + keyword matching (deployment fallback) + rule-based adversarial detection + AES-256-GCM encryption.
*   **Precomputed Embeddings**: Customer PII embeddings pre-generated for fast similarity checks without runtime model loading overhead.
*   **Lazy Loading Optimization**: Dashboard uses lazy loading to defer heavy agent initialization until first message, reducing startup time from ~20s to <2s.
*   **UI/UX**:
    *   **Unified Mission Control Dashboard** (`unified_dashboard.py` - Port 5000): Comprehensive Streamlit-based interface with **lazy loading** (fast startup <2s) and 4 tabs:
        *   **Live Chat & Monitor**: Interactive chat with adversarial pattern warnings, PII leak visualization, test scenario buttons (happy path, jailbreak, role manipulation), and real-time activity feed showing adversarial attempts with 🚨 indicators
        *   **Trace Explorer with Agent Decision Flow Visualizer**: Complete interaction history with adversarial pattern badges, filtering, search, and **interactive 4-stage timeline** (Input Safety → Agent Reasoning → Output Safety → Final Decision) showing detailed evidence, matched patterns, tool calls, PII similarity scores, and block reasons
        *   **Analytics Dashboard**: Charts showing block rates, adversarial attempt frequency, and PII leak prevention stats
        *   **System Status**: Health monitoring with security event counts and encryption system status
    *   **Demo SecureBank Website** (`demo_website/` + `api.py` - Port 8000): Professional banking UI with test scenarios including "Happy Path", "PII Request", "Jailbreak Attempt", and "Role Manipulation" buttons. Displays test credentials for Emma Johnson (card: 2356, postcode: SW1A 1AA) and Michael Chen (card: 7891, postcode: M1 1AA).

### Technical Implementation & Specifications

*   **Language**: Python 3.11.
*   **LLM Framework**: LangChain + LangGraph.
*   **LLM Provider**: OpenAI GPT-5 (via Replit AI Integrations).
*   **Backend API**: FastAPI + Uvicorn for async REST endpoints, also serving static files for the demo website.
*   **Frontend**: Streamlit for customer chat and admin dashboard, vanilla HTML/CSS/JavaScript for the demo website.
*   **Embeddings**: `all-MiniLM-L6-v2` for knowledge base, `sentence-transformers` (dev) / keyword matching (deployment) for agent responses.
*   **Similarity**: `scikit-learn` cosine similarity (dev) / keyword matching (deployment).

## External Dependencies

*   **LLM Provider**: OpenAI (GPT-5 via Replit AI Integrations)
*   **Observability**: LangFuse SDK (optional, for tracing and analytics)
*   **Web Frameworks**: Streamlit, FastAPI
*   **Database**: SQLite (for shared telemetry with encrypted payloads)
*   **NLP/Embeddings**: `sentence-transformers` (specifically `all-MiniLM-L6-v2`), `scikit-learn` (for cosine similarity)
*   **Encryption**: `cryptography` library (AES-256-GCM authenticated encryption)
*   **Data Manipulation**: Pandas
*   **Web Server**: Uvicorn

## Environment Variables

*   **Required**:
    *   `AI_INTEGRATIONS_OPENAI_API_KEY`: OpenAI API key
    *   `AI_INTEGRATIONS_OPENAI_BASE_URL`: OpenAI API base URL
    *   `SECUREBANK_ENC_KEY`: Base64-encoded 32-byte AES-256 encryption key
*   **Optional**:
    *   `LANGFUSE_PUBLIC_KEY`: LangFuse public key (for tracing)
    *   `LANGFUSE_SECRET_KEY`: LangFuse secret key (for tracing)
    *   `LANGFUSE_HOST`: LangFuse host URL (default: https://cloud.langfuse.com)