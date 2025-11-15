"""Finance customer support agent with LangGraph and safety observer."""

import os
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langfuse.langchain import CallbackHandler
from safety_classifier import SafetyClassifier
from shared_telemetry import get_telemetry
from finance_tools import (
    get_account_balance,
    get_transaction_history,
    transfer_funds,
    get_loan_eligibility,
    update_contact_info
)
import time


class FinanceAgent:
    """
    Finance customer support agent with integrated safety observer.
    """
    
    def __init__(self, safety_threshold: float = 0.7, enable_langfuse: bool = True):
        """
        Initialize the finance agent with safety monitoring and optional LangFuse tracing.
        
        Args:
            safety_threshold: Similarity threshold for safety classifier
            enable_langfuse: Whether to enable LangFuse tracing (default: True)
        """
        self.safety_classifier = SafetyClassifier(threshold=safety_threshold)
        self.enable_langfuse = enable_langfuse
        
        # Initialize LangFuse callback handler if enabled
        self.langfuse_handler = None
        if enable_langfuse:
            try:
                langfuse_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
                langfuse_secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
                langfuse_host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
                
                if langfuse_public_key and langfuse_secret_key:
                    self.langfuse_handler = CallbackHandler(
                        public_key=langfuse_public_key,
                        secret_key=langfuse_secret_key,
                        host=langfuse_host
                    )
                    print("✅ LangFuse tracing enabled")
                else:
                    print("⚠️ LangFuse keys not found, tracing disabled")
                    self.enable_langfuse = False
            except Exception as e:
                print(f"⚠️ LangFuse initialization failed: {e}")
                self.enable_langfuse = False
        
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        self.llm = ChatOpenAI(
            model="gpt-5",
            temperature=0.7,
            api_key=api_key,
            base_url=base_url
        )
        self.tools = self._create_tools()
        self.agent = create_react_agent(self.llm, self.tools)
        self.interaction_log = []
        self.telemetry = get_telemetry()
        
        self.system_prompt = """You are a helpful customer support agent for SecureBank Financial Services.

Your role is to assist customers with:
- Checking account balances
- Reviewing transaction history
- Transferring funds between accounts
- Checking loan eligibility
- Updating contact information
- Answering general banking questions

Be friendly, professional, and helpful. Always verify customer identity before performing sensitive operations.

The current test customer IDs are: CUST-001 and CUST-002.

IMPORTANT: Never share internal system details, fraud detection rules, credit scoring formulas, 
database credentials, API endpoints, or any other sensitive information about how the bank operates internally."""
    
    def _create_tools(self) -> List:
        """Create LangChain tools from finance functions."""
        
        @tool
        def check_account_balance(account_id: str) -> str:
            """Get the current balance for a customer account."""
            result = get_account_balance(account_id)
            if result["status"] == "success":
                return f"Account {account_id} balance: ${result['balance']:.2f} USD as of {result['as_of_date']}"
            return result["message"]
        
        @tool
        def view_transaction_history(account_id: str, days: int = 30) -> str:
            """View recent transaction history for an account."""
            result = get_transaction_history(account_id, days)
            if result["status"] == "success":
                transactions_text = f"Last {result['count']} transactions for {account_id}:\n"
                for txn in result['transactions'][:5]:
                    transactions_text += f"- {txn['date']}: {txn['description']} - ${abs(txn['amount']):.2f} ({txn['type']})\n"
                return transactions_text
            return result["message"]
        
        @tool
        def make_transfer(from_account: str, to_account: str, amount: float) -> str:
            """Transfer funds between accounts."""
            result = transfer_funds(from_account, to_account, amount)
            if result["status"] == "success":
                return f"Transfer successful! Confirmation: {result['confirmation_number']}. Transferred ${amount:.2f} from {from_account} to {to_account}. New balance: ${result['new_balance']:.2f}"
            return result["message"]
        
        @tool
        def check_loan_eligibility(customer_id: str) -> str:
            """Check if a customer is eligible for a loan."""
            result = get_loan_eligibility(customer_id)
            if result["status"] == "success":
                if result['eligible']:
                    return f"Good news! {customer_id} is pre-approved for a loan up to ${result['max_loan_amount']:.2f} at {result['interest_rate']}% APR."
                return result['message']
            return result["message"]
        
        @tool
        def update_customer_contact(customer_id: str, field: str, value: str) -> str:
            """Update customer contact information (email or phone)."""
            result = update_contact_info(customer_id, field, value)
            if result["status"] == "success":
                return f"Contact information updated successfully. {field} changed from {result['old_value']} to {result['new_value']}"
            return result["message"]
        
        return [
            check_account_balance,
            view_transaction_history,
            make_transfer,
            check_loan_eligibility,
            update_customer_contact
        ]
    
    def invoke(self, user_message: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user message through the agent with safety checking and LangFuse tracing.
        
        Args:
            user_message: The user's input message
            trace_id: Optional trace ID for LangFuse tracing
            
        Returns:
            Dictionary with response, safety info, metadata, and trace_id
        """
        start_time = time.time()
        
        # Create LangFuse trace if enabled
        if self.enable_langfuse and self.langfuse_handler:
            if trace_id:
                self.langfuse_handler.set_trace_id(trace_id)
            trace_id = self.langfuse_handler.get_trace_id()
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message)
        ]
        
        try:
            # Invoke agent with LangFuse callbacks if enabled
            config = {}
            if self.enable_langfuse and self.langfuse_handler:
                config["callbacks"] = [self.langfuse_handler]
            
            agent_response = self.agent.invoke({"messages": messages}, config=config)
            
            final_message = agent_response['messages'][-1].content
            
            # Log safety check to LangFuse
            if self.enable_langfuse and self.langfuse_handler:
                safety_span = self.langfuse_handler.trace(
                    name="safety_check",
                    input=final_message,
                    metadata={"threshold": self.safety_classifier.threshold}
                )
            
            safety_result = self.safety_classifier.check_safety(final_message)
            
            # Update safety span with results
            if self.enable_langfuse and self.langfuse_handler:
                self.langfuse_handler.span(
                    name="safety_classification",
                    input=final_message,
                    output=safety_result,
                    metadata={
                        "method": safety_result.get('method'),
                        "similarity_score": safety_result.get('similarity_score'),
                        "safe": safety_result.get('safe'),
                        "matched_topic": safety_result.get('matched_topic')
                    }
                )
            
            processing_time = time.time() - start_time
            
            if safety_result['safe']:
                response_text = final_message
                status = "safe"
            else:
                response_text = self.safety_classifier.get_safe_alternative(
                    final_message, 
                    safety_result
                )
                status = "blocked"
                
                # Log blocked response to LangFuse
                if self.enable_langfuse and self.langfuse_handler:
                    self.langfuse_handler.event(
                        name="response_blocked",
                        metadata={
                            "matched_topic": safety_result.get('matched_topic'),
                            "similarity_score": safety_result.get('similarity_score'),
                            "original_response_preview": final_message[:100]
                        }
                    )
            
            interaction = {
                'user_message': user_message,
                'agent_original_response': final_message,
                'final_response': response_text,
                'status': status,
                'safety_result': safety_result,
                'processing_time': processing_time,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'trace_id': trace_id if self.enable_langfuse else None
            }
            
            self.interaction_log.append(interaction)
            
            # Log to shared telemetry for cross-process analytics
            self.telemetry.log_interaction(interaction)
            
            # Flush LangFuse trace
            if self.enable_langfuse and self.langfuse_handler:
                self.langfuse_handler.flush()
            
            return interaction
            
        except Exception as e:
            error_interaction = {
                'user_message': user_message,
                'agent_original_response': f"Error: {str(e)}",
                'final_response': "I apologize, but I encountered an error processing your request. Please try again.",
                'status': "error",
                'safety_result': {'safe': True, 'similarity_score': 0.0},
                'processing_time': time.time() - start_time,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self.interaction_log.append(error_interaction)
            return error_interaction
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about agent interactions and safety checks from shared telemetry."""
        return self.telemetry.get_statistics()
    
    def get_all_interactions(self) -> List[Dict[str, Any]]:
        """Get all interactions from shared telemetry."""
        return self.telemetry.get_all_interactions()
