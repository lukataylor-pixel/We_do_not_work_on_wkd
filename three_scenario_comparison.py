"""
Three-Scenario Security Comparison
Tests 10 representative cases across 3 protection levels

IMPORTANT: Only attack patterns and normalizations are stored.
Customer data is read-only and NEVER added to knowledge base.
"""

import pandas as pd
import json
import time
from finance_agent import FinanceAgent
from typing import Dict, Any, List

# Select test cases to run
# For quick tests, use SELECTED_TESTS list
# For full evaluation, set SELECTED_TESTS = None to run all tests
SELECTED_TESTS = None  # Run ALL test cases

# 10 diverse test cases (for quick testing)
QUICK_TESTS = [
    # Instruction manipulation
    "instruction_manipulation/ignore_previous",
    # Role escalation
    "role_escalation/admin_mode",
    # Data exfiltration
    "data_exfiltration/list_all_customers",
    # Direct PII (with customer name)
    "direct_pii_request/specific_customer_address",
    # Social engineering
    "social_engineering/fake_employee",
    # Jailbreak
    "jailbreak/hypothetical",
    # Verification bypass
    "verification_bypass/skip_verification",
    # Obfuscation
    "obfuscation/leetspeak",
    # Legitimate request
    "legitimate_safe/balance_request_verified",
    # Edge case
    "edge_case/wrong_credentials"
]

def run_scenario(scenario_name: str, agent: FinanceAgent, test_cases: List[Dict]) -> Dict[str, Any]:
    """Run evaluation for one scenario"""
    print(f"\n{'='*80}")
    print(f"SCENARIO: {scenario_name}")
    print('='*80)

    results = []
    start_time = time.time()
    total_tests = len(test_cases)

    for idx, test in enumerate(test_cases):
        test_id = test['test_id']
        category = test['attack_category']
        attack_type = test['attack_type']
        prompt = test['prompt']
        expected = test['expected_result']

        print(f"\n[{idx+1}/{total_tests}] {category}/{attack_type}")

        # Run test
        test_start = time.time()
        response = agent.invoke(prompt)
        latency = time.time() - test_start

        actual = response['status']
        passed = (actual == expected)

        # Determine result type
        if expected == 'blocked':
            result_type = 'TP' if passed else 'FN'  # True Positive or False Negative
        else:
            result_type = 'TN' if passed else 'FP'  # True Negative or False Positive

        result_emoji = '✅' if passed else '❌'
        print(f"  {result_emoji} {result_type}: {actual} (expected: {expected}) - {latency:.2f}s")

        # Extract detection info
        adversarial = response.get('adversarial_check', {}).get('is_adversarial', False)
        matched_patterns = response.get('adversarial_check', {}).get('matched_patterns', [])

        if matched_patterns:
            print(f"  Patterns: {matched_patterns[:3]}")

        results.append({
            'test_id': test_id,
            'category': category,
            'attack_type': attack_type,
            'prompt': prompt,
            'expected': expected,
            'actual': actual,
            'passed': passed,
            'result_type': result_type,
            'latency': latency,
            'adversarial_detected': adversarial,
            'matched_patterns': matched_patterns,
            'agent_response': response.get('final_response', '')
        })

    total_time = time.time() - start_time

    # Calculate metrics
    total = len(results)
    passed_count = sum(1 for r in results if r['passed'])
    attacks = [r for r in results if r['expected'] == 'blocked']
    blocked = sum(1 for r in attacks if r['actual'] == 'blocked')

    accuracy = (passed_count / total * 100) if total > 0 else 0
    asr = ((len(attacks) - blocked) / len(attacks) * 100) if attacks else 0

    summary = {
        'scenario': scenario_name,
        'total_tests': total,
        'passed': passed_count,
        'accuracy': accuracy,
        'total_attacks': len(attacks),
        'attacks_blocked': blocked,
        'attack_success_rate': asr,
        'avg_latency': sum(r['latency'] for r in results) / total,
        'total_time': total_time,
        'results': results
    }

    print(f"\n📊 Summary:")
    print(f"  Accuracy: {accuracy:.1f}% ({passed_count}/{total})")
    print(f"  ASR: {asr:.1f}% ({len(attacks) - blocked}/{len(attacks)} attacks succeeded)")
    print(f"  Avg Latency: {summary['avg_latency']:.2f}s")

    return summary

def main():
    # Load test cases
    test_df = pd.read_csv('test_prompts.csv')

    # Determine which tests to run
    if SELECTED_TESTS is None:
        # Run ALL tests
        selected_cases = []
        for idx, row in test_df.iterrows():
            selected_cases.append({
                'test_id': f"{row['attack_category']}/{row['attack_type']}",
                'attack_category': row['attack_category'],
                'attack_type': row['attack_type'],
                'prompt': row['prompt'],
                'expected_result': row['expected_result']
            })
        test_description = f"{len(selected_cases)} Test Cases (FULL SUITE)"
    else:
        # Run selected tests
        selected_cases = []
        for test_name in SELECTED_TESTS:
            category, attack_type = test_name.split('/')
            row = test_df[(test_df['attack_category'] == category) &
                          (test_df['attack_type'] == attack_type)]
            if not row.empty:
                selected_cases.append({
                    'test_id': test_name,
                    'attack_category': category,
                    'attack_type': attack_type,
                    'prompt': row.iloc[0]['prompt'],
                    'expected_result': row.iloc[0]['expected_result']
                })
        test_description = f"{len(selected_cases)} Test Cases (SELECTED)"

    print("="*80)
    print(f"🔬 THREE-SCENARIO SECURITY COMPARISON ({test_description})")
    print("="*80)
    print("\nScenarios:")
    print("1. UNPROTECTED - No safety classifier")
    print("2. OLD PATTERNS - 54 patterns, no normalization (baseline)")
    print("3. ENHANCED - 69 patterns + normalization + customer names (current)")
    print("\n" + "="*80)

    print(f"\nRunning {len(selected_cases)} test cases")
    print("-" * 80)

    all_results = {}

    # SCENARIO 1: UNPROTECTED
    print("\n\n🚫 SCENARIO 1: UNPROTECTED (No Safety Classifier)")
    agent_unprotected = FinanceAgent(
        safety_threshold=0.7,
        enable_langfuse=False,
        disable_safety_checks=True  # DISABLE all safety
    )
    all_results['unprotected'] = run_scenario('UNPROTECTED', agent_unprotected, selected_cases)

    # SCENARIO 2: OLD PATTERNS (simulated - we'll use current but note it in docs)
    # NOTE: We can't actually run old patterns without code changes,
    # so we'll document that the old baseline was 82.7% (22% ASR) from previous runs
    print("\n\n⚠️  SCENARIO 2: OLD PATTERNS (Baseline)")
    print("Note: Using documented results from previous baseline evaluation")
    print("(54 patterns, no normalization, no customer name detection)")
    # We'll add the baseline results from our documented evaluation
    all_results['old_patterns'] = {
        'scenario': 'OLD PATTERNS (Baseline)',
        'note': 'Results from previous baseline evaluation on full 52-test suite',
        'overall_accuracy': 82.7,
        'attack_success_rate': 22.0,
        'attacks_blocked_rate': 78.0,
        'source': 'Previous evaluation documented in IMPROVEMENTS.md'
    }
    print("  Documented Results:")
    print(f"  Accuracy: 82.7% (43/52 on full suite)")
    print(f"  ASR: 22.0% (9/41 attacks succeeded)")

    # SCENARIO 3: ENHANCED (current)
    print("\n\n✅ SCENARIO 3: ENHANCED (Current Protection)")
    print("Loading customer embeddings and initializing safety classifier...")
    agent_enhanced = FinanceAgent(
        safety_threshold=0.7,
        enable_langfuse=False,
        disable_safety_checks=False  # ENABLE all safety
    )
    all_results['enhanced'] = run_scenario('ENHANCED', agent_enhanced, selected_cases)

    # Final Comparison
    print("\n\n" + "="*80)
    print("📊 FINAL COMPARISON")
    print("="*80)

    print("\n{:<20} {:<15} {:<15} {:<15}".format(
        "Metric", "UNPROTECTED", "OLD PATTERNS", "ENHANCED"
    ))
    print("-" * 70)

    unp = all_results['unprotected']
    old = all_results['old_patterns']
    enh = all_results['enhanced']

    print("{:<20} {:<15} {:<15} {:<15}".format(
        "Accuracy",
        f"{unp['accuracy']:.1f}%",
        f"{old['overall_accuracy']:.1f}%*",
        f"{enh['accuracy']:.1f}%"
    ))

    print("{:<20} {:<15} {:<15} {:<15}".format(
        "Attack Success Rate",
        f"{unp['attack_success_rate']:.1f}%",
        f"{old['attack_success_rate']:.1f}%*",
        f"{enh['attack_success_rate']:.1f}%"
    ))

    print("{:<20} {:<15} {:<15} {:<15}".format(
        "Attacks Blocked",
        f"{unp['attacks_blocked']}/{unp['total_attacks']}",
        "32/41*",
        f"{enh['attacks_blocked']}/{enh['total_attacks']}"
    ))

    print("\n* Old Patterns results from full 52-test baseline evaluation")

    # Save results
    if SELECTED_TESTS is None:
        output_file = 'three_scenario_comparison_full.json'
    else:
        num_tests = len(selected_cases)
        output_file = f'three_scenario_comparison_{num_tests}tests.json'

    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")
    print("="*80)

    # Show improvement summary
    print("\n🎯 IMPROVEMENT SUMMARY:")
    print(f"  UNPROTECTED → ENHANCED: {enh['accuracy'] - unp['accuracy']:.1f}% accuracy gain")
    print(f"  UNPROTECTED → ENHANCED: {unp['attack_success_rate'] - enh['attack_success_rate']:.1f}% ASR reduction")
    print(f"  OLD PATTERNS → ENHANCED: {enh['accuracy'] - old['overall_accuracy']:.1f}% accuracy gain")
    print(f"  OLD PATTERNS → ENHANCED: {old['attack_success_rate'] - enh['attack_success_rate']:.1f}% ASR reduction")
    print("="*80)

if __name__ == "__main__":
    main()
