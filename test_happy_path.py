#!/usr/bin/env python3
"""
Test script to verify the happy path demo works correctly.
Tests that a verified customer can successfully check their balance.
"""

import os
from finance_agent import FinanceAgent

# Set required environment variables
os.environ['SECUREBANK_ENC_KEY'] = "XqB1IHNSIKvMgsk8nJdrEU2OJd3Aiiq2PDRH1x/USSw="

def test_happy_path():
    """Test that a verified customer can check their balance."""
    print("=" * 80)
    print("Testing Happy Path: Verified Customer Balance Check")
    print("=" * 80)

    # Initialize the finance agent
    agent = FinanceAgent(enable_langfuse=False)

    # Test message from demo website (Emma Thompson's credentials)
    test_message = "I want to check my balance. Card: 3156, postcode: SW1A 1AA"

    print(f"\nUser Message: {test_message}")
    print("\nExpected behavior:")
    print("  - Verification should succeed for Emma Thompson")
    print("  - Balance should be returned (£8,234.67)")
    print("  - Status should be 'safe' (not blocked)")
    print("\n" + "-" * 80)

    # Invoke the agent
    result = agent.invoke(test_message)

    print(f"\nStatus: {result['status']}")
    print(f"Final Response: {result['final_response']}")

    # Check the decision flow
    print("\n" + "-" * 80)
    print("Decision Flow:")
    for step in result['decision_flow']:
        print(f"  {step['stage_name']}: {step['status']}")
        if step['stage'] == 'output_safety_check':
            print(f"    - Safe: {step['details'].get('safe', 'N/A')}")
            print(f"    - Method: {step['details'].get('method', 'N/A')}")
            print(f"    - Similarity Score: {step['details'].get('similarity_score', 'N/A')}")

    # Verify expectations
    print("\n" + "=" * 80)
    print("Test Results:")
    print("=" * 80)

    passed = True

    # Check 1: Status should be 'safe'
    if result['status'] == 'safe':
        print("✓ Status is 'safe' (not blocked)")
    else:
        print(f"✗ FAILED: Status is '{result['status']}' (expected 'safe')")
        passed = False

    # Check 2: Response should contain balance information
    if '£' in result['final_response'] or 'balance' in result['final_response'].lower():
        print("✓ Response contains balance information")
    else:
        print("✗ FAILED: Response does not contain balance information")
        passed = False

    # Check 3: Response should not be a generic security message
    if 'cannot provide that information' not in result['final_response'].lower():
        print("✓ Response is not a generic security block message")
    else:
        print("✗ FAILED: Response is a generic security block message")
        passed = False

    # Check 4: Safety check details
    safety_result = result.get('safety_result', {})
    if safety_result.get('verified_customer_exemption', False):
        print("✓ Safety check recognized verified customer exemption")
    else:
        print("  - Note: Verified customer exemption flag not set (may still pass if safe=True)")

    print("\n" + "=" * 80)
    if passed:
        print("✓✓✓ HAPPY PATH TEST PASSED ✓✓✓")
    else:
        print("✗✗✗ HAPPY PATH TEST FAILED ✗✗✗")
    print("=" * 80)

    return passed

if __name__ == "__main__":
    try:
        success = test_happy_path()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗✗✗ TEST FAILED WITH ERROR ✗✗✗")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
