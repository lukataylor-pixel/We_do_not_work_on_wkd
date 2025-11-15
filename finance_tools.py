"""Finance customer support tools for the agent."""

from typing import Dict, Any
import random
from datetime import datetime, timedelta


MOCK_CUSTOMER_DATA = {
    "CUST-001": {
        "name": "John Doe",
        "account_balance": 5432.18,
        "email": "john.doe@email.com",
        "phone": "555-0123"
    },
    "CUST-002": {
        "name": "Jane Smith", 
        "account_balance": 12847.55,
        "email": "jane.smith@email.com",
        "phone": "555-0456"
    }
}


def get_account_balance(account_id: str) -> Dict[str, Any]:
    """
    Retrieves customer account balance.
    
    Args:
        account_id: The customer account identifier (e.g., 'CUST-001')
        
    Returns:
        Dictionary with account balance information
    """
    if account_id in MOCK_CUSTOMER_DATA:
        customer = MOCK_CUSTOMER_DATA[account_id]
        return {
            "status": "success",
            "account_id": account_id,
            "balance": customer["account_balance"],
            "currency": "USD",
            "as_of_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        return {
            "status": "error",
            "message": f"Account {account_id} not found"
        }


def get_transaction_history(account_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Fetches recent transaction history.
    
    Args:
        account_id: The customer account identifier
        days: Number of days of history to retrieve (default: 30)
        
    Returns:
        Dictionary with transaction history
    """
    if account_id not in MOCK_CUSTOMER_DATA:
        return {
            "status": "error",
            "message": f"Account {account_id} not found"
        }
    
    transactions = []
    base_date = datetime.now()
    
    for i in range(min(days // 3, 10)):
        transaction_date = base_date - timedelta(days=random.randint(1, days))
        transactions.append({
            "date": transaction_date.strftime("%Y-%m-%d"),
            "description": random.choice([
                "Online Purchase - Amazon",
                "Grocery Store - Whole Foods",
                "Gas Station - Shell",
                "Restaurant - Chipotle",
                "ATM Withdrawal",
                "Direct Deposit - Salary",
                "Utility Payment - Electric"
            ]),
            "amount": round(random.uniform(-200, 500), 2),
            "type": random.choice(["debit", "credit"])
        })
    
    return {
        "status": "success",
        "account_id": account_id,
        "transactions": sorted(transactions, key=lambda x: x["date"], reverse=True),
        "count": len(transactions)
    }


def transfer_funds(from_account: str, to_account: str, amount: float) -> Dict[str, Any]:
    """
    Initiates a fund transfer between accounts.
    
    Args:
        from_account: Source account identifier
        to_account: Destination account identifier  
        amount: Amount to transfer
        
    Returns:
        Dictionary with transfer confirmation
    """
    if from_account not in MOCK_CUSTOMER_DATA:
        return {
            "status": "error",
            "message": f"Source account {from_account} not found"
        }
    
    if amount <= 0:
        return {
            "status": "error",
            "message": "Transfer amount must be positive"
        }
    
    if MOCK_CUSTOMER_DATA[from_account]["account_balance"] < amount:
        return {
            "status": "error",
            "message": "Insufficient funds for transfer"
        }
    
    MOCK_CUSTOMER_DATA[from_account]["account_balance"] -= amount
    if to_account in MOCK_CUSTOMER_DATA:
        MOCK_CUSTOMER_DATA[to_account]["account_balance"] += amount
    
    return {
        "status": "success",
        "confirmation_number": f"TXN-{random.randint(100000, 999999)}",
        "from_account": from_account,
        "to_account": to_account,
        "amount": amount,
        "new_balance": MOCK_CUSTOMER_DATA[from_account]["account_balance"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_loan_eligibility(customer_id: str) -> Dict[str, Any]:
    """
    Checks customer loan pre-approval status.
    
    Args:
        customer_id: The customer identifier
        
    Returns:
        Dictionary with loan eligibility information
    """
    if customer_id not in MOCK_CUSTOMER_DATA:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }
    
    balance = MOCK_CUSTOMER_DATA[customer_id]["account_balance"]
    
    if balance > 10000:
        eligible = True
        max_amount = balance * 2
        message = "Pre-approved for personal loan"
    elif balance > 5000:
        eligible = True
        max_amount = balance * 1.5
        message = "Pre-approved for small loan"
    else:
        eligible = False
        max_amount = 0
        message = "Not currently eligible. Build your account balance to improve eligibility."
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "eligible": eligible,
        "max_loan_amount": max_amount,
        "message": message,
        "interest_rate": 5.99 if eligible else None
    }


def update_contact_info(customer_id: str, field: str, value: str) -> Dict[str, Any]:
    """
    Updates customer contact information.
    
    Args:
        customer_id: The customer identifier
        field: Field to update ('email' or 'phone')
        value: New value for the field
        
    Returns:
        Dictionary with update confirmation
    """
    if customer_id not in MOCK_CUSTOMER_DATA:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }
    
    if field not in ["email", "phone"]:
        return {
            "status": "error",
            "message": f"Invalid field '{field}'. Only 'email' and 'phone' can be updated."
        }
    
    old_value = MOCK_CUSTOMER_DATA[customer_id].get(field)
    MOCK_CUSTOMER_DATA[customer_id][field] = value
    
    return {
        "status": "success",
        "customer_id": customer_id,
        "field": field,
        "old_value": old_value,
        "new_value": value,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
