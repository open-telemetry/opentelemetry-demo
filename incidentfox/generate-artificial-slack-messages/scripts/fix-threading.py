#!/usr/bin/env python3
"""
Fix threading in all scenario files

Makes sure messages thread under the alert in their own channel,
not under alerts in other channels.
"""

import json
import sys
from pathlib import Path

def fix_threading(scenario_path: Path):
    """Fix threading for a single scenario"""
    with open(scenario_path, 'r') as f:
        scenario = json.load(f)
    
    timeline = scenario['timeline']
    
    # Build a map of channel -> alert index
    channel_alerts = {}
    for idx, event in enumerate(timeline):
        if event['type'] == 'alert' and event.get('thread_parent') is None:
            channel = event['channel']
            if channel not in channel_alerts:
                channel_alerts[channel] = idx
    
    # Fix thread_parent for all messages
    fixed_count = 0
    for idx, event in enumerate(timeline):
        if event.get('thread_parent') is not None:
            channel = event['channel']
            correct_parent = channel_alerts.get(channel)
            
            if correct_parent is not None and event['thread_parent'] != correct_parent:
                # print(f"  Fixing event {idx}: thread_parent {event['thread_parent']} -> {correct_parent}")
                event['thread_parent'] = correct_parent
                fixed_count += 1
    
    if fixed_count > 0:
        # Write back
        with open(scenario_path, 'w') as f:
            json.dump(scenario, f, indent=2)
        print(f"✓ {scenario_path.name}: Fixed {fixed_count} thread references")
        return True
    else:
        print(f"  {scenario_path.name}: Already correct")
        return False

def main():
    scenarios_dir = Path("scenarios")
    
    print("Fixing threading in all scenarios...\n")
    
    fixed_files = 0
    for scenario_file in scenarios_dir.glob("*.json"):
        if fix_threading(scenario_file):
            fixed_files += 1
    
    print(f"\n✅ Fixed {fixed_files} scenario files")

if __name__ == "__main__":
    main()
