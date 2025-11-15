"""Finance customer support agent with LangGraph and safety observer."""

import os
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from safety_classifier import SafetyClassifier
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
    
    def __init__(self, safety_threshold: float = 0.7):
        """
        Initialize the finance agent with safety monitoring.
        
        Args:
            safety_threshold: Similarity threshold for safety classifier
        """
        self.safety_classifier = SafetyClassifier(threshold=safety_threshold)
        
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
    
    def invoke(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message through the agent with safety checking.
        
        Args:
            user_message: The user's input message
            
        Returns:
            Dictionary with response, safety info, and metadata
        """
        start_time = time.time()
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message)
        ]
        
        try:
            agent_response = self.agent.invoke({"messages": messages})
            
            final_message = agent_response['messages'][-1].content
            
            safety_result = self.safety_classifier.check_safety(final_message)
            
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
            
            interaction = {
                'user_message': user_message,
                'agent_original_response': final_message,
                'final_response': response_text,
                'status': status,
                'safety_result': safety_result,
                'processing_time': processing_time,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.interaction_log.append(interaction)
            
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
        """Get statistics about agent interactions and safety checks."""
        if not self.interaction_log:
            return {
                'total_interactions': 0,
                'blocked_count': 0,
                'safe_count': 0,
                'block_rate': 0.0,
                'avg_similarity_score': 0.0,
                'avg_processing_time': 0.0,
                'blocked_interactions': [],
                'category_counts': {}
            }
        
        blocked = [log for log in self.interaction_log if log['status'] == 'blocked']
        safe = [log for log in self.interaction_log if log['status'] == 'safe']
        
        similarity_scores = [log['safety_result']['similarity_score'] for log in self.interaction_log]
        processing_times = [log['processing_time'] for log in self.interaction_log]
        
        return {
            'total_interactions': len(self.interaction_log),
            'blocked_count': len(blocked),
            'safe_count': len(safe),
            'block_rate': len(blocked) / len(self.interaction_log) * 100 if self.interaction_log else 0,
            'avg_similarity_score': sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0,
            'avg_processing_time': sum(processing_times) / len(processing_times) if processing_times else 0,
            'blocked_interactions': blocked[-5:],
            'category_counts': self._get_category_counts()
        }
    
    def _get_category_counts(self) -> Dict[str, int]:
        """Count blocked attempts by category."""
        category_counts = {}
        for log in self.interaction_log:
            if log['status'] == 'blocked' and log['safety_result'].get('matched_topic'):
                category = log['safety_result']['matched_topic']
                category_counts[category] = category_counts.get(category, 0) + 1
        return category_counts
