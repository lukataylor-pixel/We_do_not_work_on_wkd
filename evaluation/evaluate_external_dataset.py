"""
External Dataset Evaluation
Tests the system against external jailbreak techniques from research (2023-2025)

Based on techniques from:
- DAN Jailbreak (2023)
- Crescendo Attack (2024)
- Context Manipulation (2024)
- Encoding Obfuscation
- Multi-technique combinations

IMPORTANT: Only attack patterns and normalizations are stored.
Customer data is read-only and NEVER added to knowledge base.
"""

import pandas as pd
import json
import time
from finance_agent import FinanceAgent
from typing import Dict, Any, List

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
        source = test['source']

        print(f"\n[{idx+1}/{total_tests}] {category}/{attack_type}")
        print(f"  Source: {source}")

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
            'source': source,
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
    # Load external test cases
    test_df = pd.read_csv('external_jailbreak_prompts.csv')

    # Convert to test cases
    selected_cases = []
    for idx, row in test_df.iterrows():
        selected_cases.append({
            'test_id': f"{row['attack_category']}/{row['attack_type']}",
            'attack_category': row['attack_category'],
            'attack_type': row['attack_type'],
            'prompt': row['prompt'],
            'expected_result': row['expected_result'],
            'source': row['source']
        })

    print("="*80)
    print(f"🔬 EXTERNAL DATASET EVALUATION ({len(selected_cases)} Test Cases)")
    print("="*80)
    print("\nDataset: External Jailbreak Techniques (2023-2025 Research)")
    print("\nTechniques tested:")
    print("- DAN Jailbreak, Hypothetical Scenarios, Evil AI Persona")
    print("- Prefix Injection, Continuation Attacks, Refusal Suppression")
    print("- Base64/ROT13/Unicode Obfuscation")
    print("- Translation Bypass, Code Switching")
    print("- Token Fragmentation, ASCII Art Injection")
    print("- Logic Manipulation, Authority Exploitation")
    print("- Crescendo Attacks, Prompt Leaking")
    print("- Multi-technique Combinations")
    print("\nScenarios:")
    print("1. UNPROTECTED - No safety classifier (worst case)")
    print("2. OLD PATTERNS - 54 patterns, no normalization (baseline)")
    print("3. ENHANCED - 69 patterns + normalization + customer names (current)")
    print("\n" + "="*80)

    print(f"\nRunning {len(selected_cases)} test cases from external research")
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

    # SCENARIO 2: OLD PATTERNS
    print("\n\n⚠️  SCENARIO 2: OLD PATTERNS (Baseline)")
    print("Note: This represents the system with 54 patterns, no normalization")
    print("Using same OLD PATTERNS baseline reference as internal evaluation")
    # For old patterns, we'll note it's a documented baseline from previous runs
    # We can't easily test it without rolling back code changes
    all_results['old_patterns'] = {
        'scenario': 'OLD PATTERNS (Baseline Reference)',
        'note': 'OLD PATTERNS baseline performance documented from internal evaluation',
        'baseline_accuracy': 82.7,
        'baseline_asr': 22.0,
        'source': 'Internal evaluation baseline (52 tests)',
        'external_dataset_note': 'External dataset not tested on OLD PATTERNS - would require code rollback'
    }
    print("  Reference Baseline Metrics (from internal dataset):")
    print(f"  Accuracy: 82.7% (43/52 on internal tests)")
    print(f"  ASR: 22.0% (9/41 attacks succeeded)")
    print(f"  Note: External dataset not tested on OLD PATTERNS")

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
    print("📊 FINAL COMPARISON - EXTERNAL DATASET")
    print("="*80)

    print("\n{:<20} {:<20} {:<20}".format(
        "Metric", "UNPROTECTED", "ENHANCED"
    ))
    print("-" * 60)

    unp = all_results['unprotected']
    enh = all_results['enhanced']

    print("{:<20} {:<20} {:<20}".format(
        "Accuracy",
        f"{unp['accuracy']:.1f}%",
        f"{enh['accuracy']:.1f}%"
    ))

    print("{:<20} {:<20} {:<20}".format(
        "Attack Success Rate",
        f"{unp['attack_success_rate']:.1f}%",
        f"{enh['attack_success_rate']:.1f}%"
    ))

    print("{:<20} {:<20} {:<20}".format(
        "Attacks Blocked",
        f"{unp['attacks_blocked']}/{unp['total_attacks']}",
        f"{enh['attacks_blocked']}/{enh['total_attacks']}"
    ))

    print("\n* OLD PATTERNS baseline: 82.7% accuracy, 22% ASR (from internal evaluation)")

    # Save results
    output_file = 'external_dataset_evaluation_results.json'

    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")
    print("="*80)

    # Show improvement summary
    print("\n🎯 IMPROVEMENT SUMMARY (External Dataset):")
    print(f"  UNPROTECTED → ENHANCED: {enh['accuracy'] - unp['accuracy']:.1f}% accuracy gain")
    print(f"  UNPROTECTED → ENHANCED: {unp['attack_success_rate'] - enh['attack_success_rate']:.1f}% ASR reduction")
    print(f"  Total external attacks tested: {enh['total_attacks']}")
    print(f"  Novel techniques blocked: {enh['attacks_blocked']}/{enh['total_attacks']}")
    print("="*80)

    # Category breakdown for ENHANCED
    print("\n📋 CATEGORY BREAKDOWN (ENHANCED):")
    print("-" * 60)
    categories = {}
    for result in enh['results']:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'total': 0, 'passed': 0, 'attacks': 0, 'blocked': 0}
        categories[cat]['total'] += 1
        if result['passed']:
            categories[cat]['passed'] += 1
        if result['expected'] == 'blocked':
            categories[cat]['attacks'] += 1
            if result['actual'] == 'blocked':
                categories[cat]['blocked'] += 1

    for cat, stats in sorted(categories.items()):
        acc = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        if stats['attacks'] > 0:
            print(f"{cat:30} Accuracy: {acc:5.1f}% ({stats['passed']}/{stats['total']})  Blocked: {stats['blocked']}/{stats['attacks']}")
        else:
            print(f"{cat:30} Accuracy: {acc:5.1f}% ({stats['passed']}/{stats['total']})")

if __name__ == "__main__":
    main()
