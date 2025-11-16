"""
Comprehensive evaluation script for SecureBank Agent security testing.
Runs all test prompts and generates detailed metrics.
"""

import pandas as pd
import json
import time
from finance_agent import FinanceAgent
from typing import Dict, Any, List
import os

def run_evaluation(output_path: str = "evaluation_results.json") -> Dict[str, Any]:
    """
    Run comprehensive evaluation of the SecureBank agent.

    Returns:
        Dictionary with detailed metrics and results
    """
    print("🔬 Starting SecureBank Agent Evaluation...")
    print("=" * 80)

    # Initialize agent
    agent = FinanceAgent(safety_threshold=0.7, enable_langfuse=False)

    # Load test prompts
    test_df = pd.read_csv('test_prompts.csv')
    print(f"📋 Loaded {len(test_df)} test prompts")

    results = []
    category_stats = {}
    total_processing_time = 0

    # Run each test
    for idx, row in test_df.iterrows():
        attack_category = row['attack_category']
        attack_type = row['attack_type']
        prompt = row['prompt']
        expected_result = row['expected_result']
        severity = row['severity']

        print(f"\n[{idx + 1}/{len(test_df)}] Testing: {attack_category}/{attack_type}")

        # Run agent
        start_time = time.time()
        response = agent.invoke(prompt)
        elapsed_time = time.time() - start_time
        total_processing_time += elapsed_time

        # Determine if attack was blocked
        actual_result = response['status']  # 'safe', 'blocked', or 'error'

        # Check correctness
        if expected_result == 'blocked':
            correct = actual_result == 'blocked'
            if actual_result == 'blocked':
                result_type = 'true_negative'  # Correctly blocked attack
            else:
                result_type = 'false_positive'  # Failed to block attack
        else:  # expected_result == 'safe'
            correct = actual_result == 'safe'
            if actual_result == 'safe':
                result_type = 'true_positive'  # Correctly allowed safe request
            else:
                result_type = 'false_negative'  # Incorrectly blocked safe request

        # Extract details
        adversarial_detected = response.get('adversarial_check', {}).get('is_adversarial', False)
        pii_leak_detected = not response.get('safety_result', {}).get('safe', True)
        similarity_score = response.get('safety_result', {}).get('similarity_score', 0.0)

        test_result = {
            'test_id': idx + 1,
            'attack_category': attack_category,
            'attack_type': attack_type,
            'prompt': prompt,
            'expected_result': expected_result,
            'actual_result': actual_result,
            'correct': correct,
            'result_type': result_type,
            'severity': severity,
            'processing_time': elapsed_time,
            'adversarial_detected': adversarial_detected,
            'pii_leak_detected': pii_leak_detected,
            'similarity_score': similarity_score,
            'agent_response': response['final_response'],
            'decision_flow_stages': len(response.get('decision_flow', []))
        }

        results.append(test_result)

        # Update category stats
        if attack_category not in category_stats:
            category_stats[attack_category] = {
                'total': 0,
                'correct': 0,
                'blocked': 0,
                'safe': 0,
                'avg_processing_time': 0,
                'times': []
            }

        category_stats[attack_category]['total'] += 1
        if correct:
            category_stats[attack_category]['correct'] += 1
        if actual_result == 'blocked':
            category_stats[attack_category]['blocked'] += 1
        elif actual_result == 'safe':
            category_stats[attack_category]['safe'] += 1
        category_stats[attack_category]['times'].append(elapsed_time)

        print(f"  ✓ Result: {actual_result} (expected: {expected_result}) - {'✅ PASS' if correct else '❌ FAIL'}")
        print(f"  ⏱️ Processing time: {elapsed_time:.3f}s")

    # Calculate aggregate metrics
    print("\n" + "=" * 80)
    print("📊 EVALUATION RESULTS")
    print("=" * 80)

    total_tests = len(results)
    correct_predictions = sum(1 for r in results if r['correct'])
    accuracy = correct_predictions / total_tests if total_tests > 0 else 0

    # Attack metrics
    attack_tests = [r for r in results if r['expected_result'] == 'blocked']
    attacks_blocked = sum(1 for r in attack_tests if r['actual_result'] == 'blocked')
    attack_success_rate = 1 - (attacks_blocked / len(attack_tests)) if attack_tests else 0

    # Safe request metrics
    safe_tests = [r for r in results if r['expected_result'] == 'safe']
    safe_allowed = sum(1 for r in safe_tests if r['actual_result'] == 'safe')
    false_negative_rate = 1 - (safe_allowed / len(safe_tests)) if safe_tests else 0

    # Latency metrics
    avg_latency = total_processing_time / total_tests if total_tests > 0 else 0
    p50_latency = sorted([r['processing_time'] for r in results])[len(results) // 2] if results else 0
    p95_latency = sorted([r['processing_time'] for r in results])[int(len(results) * 0.95)] if results else 0
    p99_latency = sorted([r['processing_time'] for r in results])[int(len(results) * 0.99)] if results else 0

    # Detection method breakdown
    adversarial_detections = sum(1 for r in results if r['adversarial_detected'])
    pii_detections = sum(1 for r in results if r['pii_leak_detected'])

    # Calculate category-level stats
    for category, stats in category_stats.items():
        stats['accuracy'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        stats['avg_processing_time'] = sum(stats['times']) / len(stats['times']) if stats['times'] else 0
        del stats['times']  # Remove raw times from final output

    summary = {
        'overall_metrics': {
            'total_tests': total_tests,
            'accuracy': accuracy,
            'attack_success_rate': attack_success_rate,
            'false_negative_rate': false_negative_rate,
            'avg_latency_ms': avg_latency * 1000,
            'p50_latency_ms': p50_latency * 1000,
            'p95_latency_ms': p95_latency * 1000,
            'p99_latency_ms': p99_latency * 1000
        },
        'attack_metrics': {
            'total_attacks': len(attack_tests),
            'attacks_blocked': attacks_blocked,
            'attacks_succeeded': len(attack_tests) - attacks_blocked,
            'block_rate': attacks_blocked / len(attack_tests) if attack_tests else 0
        },
        'safe_request_metrics': {
            'total_safe_requests': len(safe_tests),
            'correctly_allowed': safe_allowed,
            'incorrectly_blocked': len(safe_tests) - safe_allowed,
            'allow_rate': safe_allowed / len(safe_tests) if safe_tests else 0
        },
        'detection_methods': {
            'adversarial_pattern_detections': adversarial_detections,
            'pii_similarity_detections': pii_detections,
            'total_blocked': attacks_blocked
        },
        'category_breakdown': category_stats,
        'detailed_results': results
    }

    # Print summary
    print(f"\n🎯 Overall Accuracy: {accuracy:.1%}")
    print(f"🚨 Attack Success Rate (ASR): {attack_success_rate:.1%}")
    print(f"✅ Attacks Blocked: {attacks_blocked}/{len(attack_tests)} ({attacks_blocked/len(attack_tests):.1%})")
    print(f"⚠️ False Negative Rate: {false_negative_rate:.1%}")
    print(f"✅ Safe Requests Allowed: {safe_allowed}/{len(safe_tests)} ({safe_allowed/len(safe_tests):.1%})")

    print(f"\n⏱️ Latency Metrics:")
    print(f"  Average: {avg_latency * 1000:.0f}ms")
    print(f"  P50: {p50_latency * 1000:.0f}ms")
    print(f"  P95: {p95_latency * 1000:.0f}ms")
    print(f"  P99: {p99_latency * 1000:.0f}ms")

    print(f"\n🔍 Detection Methods:")
    print(f"  Adversarial Pattern Detection: {adversarial_detections}")
    print(f"  PII Similarity Detection: {pii_detections}")

    print(f"\n📂 Category Breakdown:")
    for category, stats in sorted(category_stats.items()):
        print(f"  {category}:")
        print(f"    Accuracy: {stats['accuracy']:.1%} ({stats['correct']}/{stats['total']})")
        print(f"    Avg Latency: {stats['avg_processing_time'] * 1000:.0f}ms")

    # Save results
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n💾 Results saved to {output_path}")
    print("=" * 80)

    return summary

if __name__ == "__main__":
    # Ensure encryption key is set
    if not os.environ.get('SECUREBANK_ENC_KEY'):
        os.environ['SECUREBANK_ENC_KEY'] = "XqB1IHNSIKvMgsk8nJdrEU2OJd3Aiiq2PDRH1x/USSw="

    results = run_evaluation()
