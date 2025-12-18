#!/usr/bin/env python3
"""
Validate a scenario JSON file against the schema

Usage:
    python validate-scenario.py scenarios/cache-failure-001.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

from rich.console import Console
from rich.table import Table

console = Console()


def load_json(path: str) -> Dict:
    """Load JSON file"""
    with open(path, 'r') as f:
        return json.load(f)


def validate_scenario(scenario: Dict) -> List[str]:
    """
    Validate scenario structure and logic
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    # Check required fields
    required_fields = ['scenario_id', 'scenario_type', 'title', 'start_time', 'services', 'timeline']
    for field in required_fields:
        if field not in scenario:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return errors  # Can't continue without basic fields
    
    # Validate timeline
    timeline = scenario['timeline']
    
    # Check timeline is sorted by offset_seconds
    offsets = [event['offset_seconds'] for event in timeline]
    if offsets != sorted(offsets):
        errors.append("Timeline events are not in chronological order (offset_seconds not sorted)")
    
    # Check thread references are valid
    valid_indices = set(range(len(timeline)))
    for idx, event in enumerate(timeline):
        thread_parent = event.get('thread_parent')
        if thread_parent is not None and thread_parent not in valid_indices:
            errors.append(f"Event {idx}: Invalid thread_parent {thread_parent} (must be < {len(timeline)})")
        if thread_parent is not None and thread_parent >= idx:
            errors.append(f"Event {idx}: thread_parent {thread_parent} must reference earlier message")
    
    # Check all channels are defined in services
    service_channels = {info['channel'] for info in scenario['services'].values()}
    for idx, event in enumerate(timeline):
        channel = event.get('channel')
        if channel and channel not in service_channels:
            errors.append(f"Event {idx}: Channel {channel} not defined in services")
    
    # Check event types have required fields
    for idx, event in enumerate(timeline):
        event_type = event.get('type')
        
        if event_type == 'alert':
            required = ['severity', 'title', 'details']
            for field in required:
                if field not in event:
                    errors.append(f"Event {idx}: Alert missing required field '{field}'")
        
        elif event_type in ['message', 'mention', 'resolution']:
            if 'user' not in event:
                errors.append(f"Event {idx}: {event_type} missing required field 'user'")
            if 'content' not in event:
                errors.append(f"Event {idx}: {event_type} missing required field 'content'")
        
        elif event_type == 'action':
            required = ['user', 'action_type', 'action_details']
            for field in required:
                if field not in event:
                    errors.append(f"Event {idx}: Action missing required field '{field}'")
    
    # Check @mentions reference valid oncall groups
    oncall_groups = {info['oncall_group'] for info in scenario['services'].values()}
    for idx, event in enumerate(timeline):
        mentions = event.get('mentions', [])
        for mention in mentions:
            if mention not in oncall_groups:
                errors.append(f"Event {idx}: @mention '{mention}' not defined in services")
    
    # Validate metrics are realistic
    for idx, event in enumerate(timeline):
        metrics = event.get('metrics', {})
        for key, value in metrics.items():
            # Basic sanity checks
            if 'latency' in key.lower():
                # Should have time units
                if not any(unit in value.lower() for unit in ['ms', 's', 'sec', 'min']):
                    errors.append(f"Event {idx}: Latency metric '{key}' should have time units (ms, s, etc)")
            
            if 'rate' in key.lower() and '%' not in value:
                # Rates should have units
                if not any(unit in value.lower() for unit in ['req/s', 'req/min', '%', 'qps']):
                    errors.append(f"Event {idx}: Rate metric '{key}' should have units")
    
    return errors


def print_validation_results(scenario: Dict, errors: List[str]):
    """Print validation results"""
    console.print(f"\n[bold cyan]Validating: {scenario.get('title', 'Unknown')}[/bold cyan]")
    console.print(f"Scenario ID: {scenario.get('scenario_id', 'unknown')}\n")
    
    if not errors:
        console.print("[bold green]✓ Scenario is valid![/bold green]\n")
        
        # Print summary
        table = Table(title="Scenario Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Services", str(len(scenario.get('services', {}))))
        table.add_row("Timeline Events", str(len(scenario.get('timeline', []))))
        table.add_row("Duration", f"{scenario.get('metadata', {}).get('duration_seconds', 0)}s")
        table.add_row("Severity", scenario.get('metadata', {}).get('severity', 'unknown'))
        
        console.print(table)
        return True
    else:
        console.print(f"[bold red]✗ Found {len(errors)} validation error(s):[/bold red]\n")
        for error in errors:
            console.print(f"  • {error}")
        console.print()
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate incident scenario JSON file")
    parser.add_argument('scenario', help='Path to scenario JSON file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Load scenario
    try:
        scenario = load_json(args.scenario)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] File not found: {args.scenario}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid JSON: {e}")
        sys.exit(1)
    
    # Validate
    errors = validate_scenario(scenario)
    
    # Print results
    is_valid = print_validation_results(scenario, errors)
    
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
