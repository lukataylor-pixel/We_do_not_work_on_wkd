"""
Fetch AgentHarm dataset scenarios and adapt them for SecureBank evaluation.
"""

from datasets import load_dataset
import pandas as pd
import csv

def fetch_agentharm_scenarios():
    """
    Fetch AgentHarm test scenarios from HuggingFace.
    """
    print("📥 Fetching AgentHarm dataset from HuggingFace...")

    # Load the test_public split
    dataset = load_dataset("ai-safety-institute/AgentHarm", "chat", split="test_public")

    print(f"✅ Loaded {len(dataset)} scenarios from AgentHarm")

    # Convert to pandas for easier manipulation
    df = pd.DataFrame(dataset)

    # Display columns
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nCategories: {df['category'].unique()}")
    print(f"\nSample scenarios:")
    for idx, row in df.head(3).iterrows():
        print(f"\n{idx+1}. {row['name']}")
        print(f"   Category: {row['category']}")
        print(f"   Prompt: {row['prompt'][:100]}...")

    return df

def adapt_for_securebank(agentharm_df):
    """
    Adapt AgentHarm scenarios for SecureBank context.

    For SecureBank, we focus on scenarios that test:
    1. Prompt injection / jailbreaking patterns
    2. Data exfiltration attempts
    3. Adversarial instruction manipulation

    We'll use a subset of AgentHarm scenarios that can be adapted to banking context.
    """
    print("\n🔄 Adapting AgentHarm scenarios for SecureBank...")

    adapted_scenarios = []

    # All AgentHarm scenarios should be blocked (they're harmful requests)
    for idx, row in agentharm_df.iterrows():
        adapted_scenarios.append({
            'attack_category': f'agentharm_{row["category"].lower().replace(" ", "_")}',
            'attack_type': row['name'].lower().replace(' ', '_'),
            'prompt': row['prompt'],
            'expected_result': 'blocked',  # All AgentHarm scenarios are harmful
            'severity': 'critical',
            'source': 'agentharm',
            'original_id': row.get('id', ''),
            'original_category': row['category']
        })

    adapted_df = pd.DataFrame(adapted_scenarios)
    print(f"✅ Adapted {len(adapted_df)} scenarios from AgentHarm")

    return adapted_df

def merge_with_existing_tests(agentharm_df):
    """
    Merge AgentHarm scenarios with existing SecureBank test prompts.
    """
    print("\n📋 Merging with existing SecureBank test prompts...")

    # Load existing test prompts
    existing_df = pd.read_csv('test_prompts.csv')
    print(f"✅ Loaded {len(existing_df)} existing test prompts")

    # Add source column to existing tests
    existing_df['source'] = 'securebank'
    existing_df['original_id'] = ''
    existing_df['original_category'] = ''

    # Merge
    merged_df = pd.concat([existing_df, agentharm_df], ignore_index=True)

    print(f"\n📊 Merged dataset:")
    print(f"   Total scenarios: {len(merged_df)}")
    print(f"   SecureBank scenarios: {len(existing_df)}")
    print(f"   AgentHarm scenarios: {len(agentharm_df)}")
    print(f"   Expected blocked: {len(merged_df[merged_df['expected_result'] == 'blocked'])}")
    print(f"   Expected safe: {len(merged_df[merged_df['expected_result'] == 'safe'])}")

    # Save merged dataset
    merged_df.to_csv('test_prompts_extended.csv', index=False, quoting=csv.QUOTE_ALL)
    print(f"\n💾 Saved merged dataset to test_prompts_extended.csv")

    return merged_df

if __name__ == "__main__":
    try:
        # Fetch AgentHarm scenarios
        agentharm_df = fetch_agentharm_scenarios()

        # Adapt for SecureBank
        adapted_df = adapt_for_securebank(agentharm_df)

        # Merge with existing tests
        merged_df = merge_with_existing_tests(adapted_df)

        print("\n✅ Dataset preparation complete!")
        print(f"Use test_prompts_extended.csv for comprehensive evaluation")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
