# Guardian Agent: Finance Customer Support with Safety Observer

## Overview

This project delivers a production-ready finance customer support agent featuring an integrated **Safety Observer**. Its primary purpose is to prevent sensitive information leakage by real-time monitoring and intervention, utilizing NLP-based similarity detection. The project aims to showcase a secure and intelligent customer interaction system for financial services, demonstrating how AI can enhance support while rigorously protecting proprietary and sensitive data. Key capabilities include conversational banking operations, real-time safety analysis, and comprehensive observability for monitoring agent performance and security.

## User Preferences

None specified yet.

## System Architecture

The Guardian Agent project is structured around three main components, each serving a distinct function, and several core components that underpin the system's functionality:

### Core Components

1.  **Finance Customer Support Agent** (`finance_agent.py`): A LangGraph-based conversational agent powered by GPT-5, integrated with LangFuse for comprehensive tracing of reasoning steps, tool calls, and safety decisions. It includes five tools for banking operations: account balance, transaction history, fund transfers, loan eligibility, and contact information updates.
2.  **Safety Classifier** (`safety_classifier.py`): A probabilistic NLP-based classifier that employs a hybrid approach. It uses precomputed 384-dimensional vectors from an `all-MiniLM-L6-v2` model for its knowledge base. For agent responses, it utilizes real-time encoding with `sentence-transformers` for semantic leak detection in development, falling back to robust keyword matching with 15+ financial/security keywords for deployment due to compatibility limitations. Cosine similarity compares agent responses against sensitive entries.
3.  **Sensitive Knowledge Base** (`do_not_share.csv`): Contains 18 entries of sensitive financial information across categories such as fraud rules, internal models, system info, credentials, customer data, security, internal policy, and compliance.
4.  **Finance Tools** (`finance_tools.py`): Mocks a banking backend with realistic data for two test customer accounts, providing implementations for all agent capabilities.
5.  **Shared Telemetry** (`shared_telemetry.py`): A SQLite-based system for cross-process storage of interaction logs, ensuring multi-process locking and ACID guarantees. It enables the admin dashboard to view interactions from all components and supports efficient SQL aggregations for analytics.

### Architectural Patterns & Design Decisions

*   **Modular Micro-frontend Architecture**: The system is split into three independent, interactive applications (Customer Chat, Admin Dashboard, Demo Finance Website) to enhance scalability, maintainability, and user experience.
*   **Real-time Safety Intervention**: Agent responses are intercepted and analyzed by the Safety Observer before delivery. If a response's similarity to sensitive information exceeds a configurable threshold (default: 0.7), it is blocked, and a category-specific safe alternative message is provided.
*   **Observability-Driven Design**: Deep integration with LangFuse for tracing all agent interactions, LLM calls, tool executions, and safety decisions. A `shared_telemetry.py` component provides a unified log of interactions across all parts of the system.
*   **Hybrid NLP Approach**: Utilizes semantic similarity (cosine similarity with `sentence-transformers`) for development and robust keyword matching for deployment to ensure compatibility and performance.
*   **Precomputed Embeddings**: To optimize deployment and startup times, embeddings for the sensitive knowledge base are precomputed.
*   **UI/UX**:
    *   **Unified Mission Control Dashboard** (`unified_dashboard.py` - Port 5000): Comprehensive Streamlit-based interface with 4 tabs providing complete observability:
        *   **Live Chat & Monitor**: Interactive chat with real-time safety visualization, demo scenario buttons, recent activity feed, and live statistics
        *   **Trace Explorer**: Complete interaction history with filtering, search, and detailed inspection
        *   **Analytics Dashboard**: Charts, statistics, performance metrics, and trend analysis
        *   **System Status**: Health monitoring, configuration overview, and integration status
    *   **Admin Dashboard** (`admin_dashboard.py` - Port 3000): Alternative Streamlit-based backend for trace review and analytics.
    *   **Demo Finance Website** (`demo_website/` + `api.py` - Port 8000): Professional fintech UI with homepage, support page (embedding the chat widget), and interactive chat component. Includes pre-configured "Jailbreak Test Buttons" for demonstration purposes.

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
*   **Observability**: LangFuse SDK (for tracing and analytics)
*   **Web Frameworks**: Streamlit, FastAPI
*   **Database**: SQLite (for shared telemetry)
*   **NLP/Embeddings**: `sentence-transformers` (specifically `all-MiniLM-L6-v2`), `scikit-learn` (for cosine similarity)
*   **Data Manipulation**: Pandas
*   **Web Server**: Uvicorn