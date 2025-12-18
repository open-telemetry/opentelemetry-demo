#!/usr/bin/env python3
"""
Post incident scenarios to Slack

Usage:
    python post-to-slack.py scenarios/cache-failure-001.json
    python post-to-slack.py scenarios/cache-failure-001.json --dry-run
    python post-to-slack.py scenarios/cache-failure-001.json --realtime
    python post-to-slack.py scenarios/cache-failure-001.json --realtime --speed 10
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.slack_client import SlackIncidentClient

# Setup logging
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)


def load_scenario(scenario_path: str) -> Dict:
    """Load scenario JSON file"""
    with open(scenario_path, 'r') as f:
        return json.load(f)


def preview_scenario(scenario: Dict):
    """Print a preview of the scenario"""
    console.print("\n[bold cyan]Scenario Preview[/bold cyan]")
    console.print(f"[bold]ID:[/bold] {scenario['scenario_id']}")
    console.print(f"[bold]Type:[/bold] {scenario['scenario_type']}")
    console.print(f"[bold]Title:[/bold] {scenario['title']}")
    console.print(f"[bold]Start Time:[/bold] {scenario['start_time']}")
    console.print(f"[bold]Duration:[/bold] {scenario['metadata']['duration_seconds']}s")
    console.print(f"[bold]Services:[/bold] {len(scenario['services'])}")
    console.print(f"[bold]Timeline Events:[/bold] {len(scenario['timeline'])}\n")
    
    # Show services table
    services_table = Table(title="Services Involved")
    services_table.add_column("Service", style="cyan")
    services_table.add_column("Channel", style="green")
    services_table.add_column("Role", style="yellow")
    
    for service_name, service_info in scenario['services'].items():
        services_table.add_row(
            service_name,
            service_info['channel'],
            service_info['role']
        )
    
    console.print(services_table)
    
    # Show timeline summary
    timeline_table = Table(title="Timeline Preview (first 10 events)")
    timeline_table.add_column("Time", style="cyan")
    timeline_table.add_column("Type", style="magenta")
    timeline_table.add_column("Channel", style="green")
    timeline_table.add_column("Preview", style="white")
    
    for event in scenario['timeline'][:10]:
        offset = event['offset_seconds']
        time_str = f"+{offset}s"
        event_type = event['type']
        channel = event['channel']
        
        if event_type == 'alert':
            preview = event['title'][:50]
        elif event_type in ['message', 'mention', 'resolution']:
            user = event.get('user', 'unknown')
            content = event.get('content', '')[:40]
            preview = f"[{user}] {content}"
        elif event_type == 'action':
            preview = event.get('action_details', '')[:50]
        else:
            preview = "..."
        
        timeline_table.add_row(time_str, event_type, channel, preview)
    
    if len(scenario['timeline']) > 10:
        console.print(f"\n[dim]... and {len(scenario['timeline']) - 10} more events[/dim]")
    
    console.print(timeline_table)
    console.print()


def post_scenario(
    scenario: Dict,
    client: SlackIncidentClient,
    realtime: bool = False,
    speed_multiplier: float = 1.0
):
    """
    Post scenario to Slack
    
    Args:
        scenario: Scenario data
        client: Slack client
        realtime: If True, post messages with delays based on offset_seconds
        speed_multiplier: Speed up factor for realtime mode (10.0 = 10x faster)
    """
    console.print(f"\n[bold green]Posting scenario: {scenario['title']}[/bold green]\n")
    
    timeline = scenario['timeline']
    start_time = datetime.now()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task(
            f"Posting {len(timeline)} events...",
            total=len(timeline)
        )
        
        last_offset = 0
        
        for idx, event in enumerate(timeline):
            offset = event['offset_seconds']
            
            # Calculate sleep time for realtime mode
            if realtime and offset > last_offset:
                sleep_time = (offset - last_offset) / speed_multiplier
                if sleep_time > 0:
                    progress.update(task, description=f"⏸ Waiting {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                last_offset = offset
            
            # Update progress description
            event_type = event['type']
            channel = event['channel']
            progress.update(
                task,
                description=f"Posting {event_type} to {channel}..."
            )
            
            # Post the event
            timestamp = None
            try:
                if event_type == 'alert':
                    timestamp = client.post_alert(
                        channel=event['channel'],
                        severity=event['severity'],
                        title=event['title'],
                        details=event['details'],
                        metrics=event.get('metrics'),
                        runbook=event.get('runbook'),
                        dashboard=event.get('dashboard'),
                        thread_parent=event.get('thread_parent')
                    )
                
                elif event_type == 'message' or event_type == 'mention':
                    timestamp = client.post_message(
                        channel=event['channel'],
                        user=event['user'],
                        content=event['content'],
                        thread_parent=event.get('thread_parent'),
                        mentions=event.get('mentions')
                    )
                
                elif event_type == 'action':
                    timestamp = client.post_action(
                        channel=event['channel'],
                        user=event['user'],
                        action_type=event['action_type'],
                        action_details=event['action_details'],
                        content=event.get('content', ''),
                        thread_parent=event.get('thread_parent')
                    )
                
                elif event_type == 'resolution':
                    timestamp = client.post_resolution(
                        channel=event['channel'],
                        user=event['user'],
                        content=event['content'],
                        metrics_after=event.get('metrics_after'),
                        thread_parent=event.get('thread_parent')
                    )
                
                # Register message for threading
                if timestamp:
                    client.register_message(idx, timestamp, event['channel'])
                
                # Handle reactions
                if 'reactions' in event and timestamp:
                    for reaction in event['reactions']:
                        client.add_reaction(
                            message_index=idx,
                            emoji=reaction['emoji'],
                            users=reaction['users']
                        )
                
            except Exception as e:
                logger.error(f"Error posting event {idx}: {e}")
                if not client.dry_run:
                    raise
            
            progress.update(task, advance=1)
        
        duration = (datetime.now() - start_time).total_seconds()
        progress.update(task, description=f"✅ Posted {len(timeline)} events in {duration:.1f}s")
    
    console.print(f"\n[bold green]✓ Scenario posted successfully![/bold green]")
    console.print(f"Duration: {duration:.1f}s\n")


def main():
    parser = argparse.ArgumentParser(
        description="Post incident scenarios to Slack",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'scenario',
        help='Path to scenario JSON file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview messages without actually posting to Slack'
    )
    parser.add_argument(
        '--realtime',
        action='store_true',
        help='Post messages with delays based on offset_seconds'
    )
    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Speed multiplier for realtime mode (e.g., 10 = 10x faster)'
    )
    parser.add_argument(
        '--test-channel',
        help='Override all channels to post to this test channel'
    )
    parser.add_argument(
        '--preview-only',
        action='store_true',
        help='Only show preview, do not post'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Load scenario
    try:
        scenario = load_scenario(args.scenario)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Scenario file not found: {args.scenario}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid JSON in scenario file: {e}")
        sys.exit(1)
    
    # Preview scenario
    preview_scenario(scenario)
    
    if args.preview_only:
        return
    
    # Get Slack token
    slack_token = os.getenv('SLACK_BOT_TOKEN')
    if not slack_token and not args.dry_run:
        console.print("[bold red]Error:[/bold red] SLACK_BOT_TOKEN not set in environment")
        console.print("Set it in .env file or export SLACK_BOT_TOKEN=xoxb-...")
        sys.exit(1)
    
    # Get alert bot configuration
    use_alert_bot = os.getenv('USE_ALERT_BOT', 'false').lower() == 'true'
    alert_bot_token = os.getenv('ALERT_BOT_TOKEN') if use_alert_bot else None
    alert_bot_name = os.getenv('ALERT_BOT_NAME', 'Monitoring Alert')
    
    # Load channel mapping from environment
    channel_mapping = {}
    for key, value in os.environ.items():
        if key.startswith('CHANNEL_'):
            # CHANNEL_recommendation_oncall -> recommendation-oncall
            service_name = key[8:].replace('_', '-')
            channel_mapping[f'#{service_name}'] = value
            logger.debug(f"Channel mapping: #{service_name} -> {value}")
    
    # Load usergroup mapping from environment
    usergroup_mapping = {}
    for key, value in os.environ.items():
        if key.startswith('USERGROUP_'):
            # USERGROUP_recommendation_oncall -> @recommendation-oncall
            service_name = key[10:].replace('_', '-')
            usergroup_mapping[f'@{service_name}'] = value
            logger.debug(f"Usergroup mapping: @{service_name} -> {value}")
    
    if use_alert_bot:
        if alert_bot_token:
            console.print(f"[cyan]Using separate alert bot:[/cyan] {alert_bot_name}")
        else:
            console.print("[bold yellow]Warning:[/bold yellow] USE_ALERT_BOT=true but ALERT_BOT_TOKEN not set")
            use_alert_bot = False
    
    # Initialize Slack client
    client = SlackIncidentClient(
        token=slack_token or "dummy-token",
        dry_run=args.dry_run,
        test_channel=args.test_channel or os.getenv('TEST_CHANNEL_OVERRIDE'),
        alert_bot_token=alert_bot_token,
        alert_bot_name=alert_bot_name,
        channel_mapping=channel_mapping,
        usergroup_mapping=usergroup_mapping
    )
    
    # Confirm before posting (unless dry run or --yes flag)
    if not args.dry_run and not args.yes:
        console.print("[bold yellow]⚠ This will post messages to Slack![/bold yellow]")
        if args.test_channel:
            console.print(f"Messages will be posted to: [cyan]{args.test_channel}[/cyan]")
        else:
            console.print("Messages will be posted to multiple channels:")
            for service_info in scenario['services'].values():
                console.print(f"  • {service_info['channel']}")
        
        response = input("\nContinue? [y/N]: ")
        if response.lower() != 'y':
            console.print("Aborted.")
            return
    
    # Post scenario
    try:
        post_scenario(
            scenario=scenario,
            client=client,
            realtime=args.realtime,
            speed_multiplier=args.speed
        )
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted by user[/bold yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        logger.exception("Detailed error:")
        sys.exit(1)


if __name__ == '__main__':
    main()
