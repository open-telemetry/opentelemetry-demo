#!/usr/bin/env python3
"""
Helper script to discover Slack channels and user groups for configuration

Usage:
    # List all channels
    python setup-slack.py --list-channels
    
    # List all user groups
    python setup-slack.py --list-groups
    
    # Generate .env configuration
    python setup-slack.py --generate-env
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

console = Console()


def list_channels(client: WebClient):
    """List all channels in the workspace"""
    console.print("\n[bold cyan]Fetching Slack channels...[/bold cyan]\n")
    
    try:
        # Get all channels (public and private that bot is member of)
        response = client.conversations_list(
            types="public_channel,private_channel",
            limit=200
        )
        
        channels = response['channels']
        
        if not channels:
            console.print("[yellow]No channels found[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Slack Channels ({len(channels)} found)")
        table.add_column("Name", style="cyan")
        table.add_column("ID", style="green")
        table.add_column("Private", style="yellow")
        table.add_column("Members", style="white")
        
        # Filter for oncall channels if they exist
        oncall_channels = [c for c in channels if 'oncall' in c['name'].lower()]
        other_channels = [c for c in channels if 'oncall' not in c['name'].lower()]
        
        # Show oncall channels first
        for channel in sorted(oncall_channels, key=lambda x: x['name']):
            table.add_row(
                f"#{channel['name']}",
                channel['id'],
                "Yes" if channel.get('is_private') else "No",
                str(channel.get('num_members', '?'))
            )
        
        # Then others
        if len(other_channels) > 0 and len(oncall_channels) > 0:
            table.add_section()
        
        for channel in sorted(other_channels[:20], key=lambda x: x['name']):  # Limit to 20
            table.add_row(
                f"#{channel['name']}",
                channel['id'],
                "Yes" if channel.get('is_private') else "No",
                str(channel.get('num_members', '?'))
            )
        
        if len(other_channels) > 20:
            console.print(f"\n[dim]... and {len(other_channels) - 20} more channels[/dim]")
        
        console.print(table)
        
        # Show sample .env configuration
        if oncall_channels:
            console.print("\n[bold green]Sample .env configuration:[/bold green]\n")
            for channel in oncall_channels[:5]:
                name = channel['name'].replace('-', '_')
                console.print(f"CHANNEL_{name}={channel['id']}")
        
    except SlackApiError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


def list_usergroups(client: WebClient):
    """List all user groups in the workspace"""
    console.print("\n[bold cyan]Fetching Slack user groups...[/bold cyan]\n")
    
    try:
        response = client.usergroups_list(include_users=False)
        
        usergroups = response['usergroups']
        
        if not usergroups:
            console.print("[yellow]No user groups found[/yellow]")
            console.print("\n[dim]You may need to create user groups first:[/dim]")
            console.print("Settings → People → User groups → Create new user group")
            return
        
        # Create table
        table = Table(title=f"Slack User Groups ({len(usergroups)} found)")
        table.add_column("Handle", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("ID", style="yellow")
        table.add_column("Members", style="white")
        
        for group in sorted(usergroups, key=lambda x: x['handle']):
            table.add_row(
                f"@{group['handle']}",
                group['name'],
                group['id'],
                str(group.get('user_count', '?'))
            )
        
        console.print(table)
        
        # Show sample .env configuration
        console.print("\n[bold green]Sample .env configuration:[/bold green]\n")
        for group in usergroups:
            handle = group['handle'].replace('-', '_')
            console.print(f"USERGROUP_{handle}={group['id']}")
        
    except SlackApiError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if "missing_scope" in str(e):
            console.print("\n[yellow]Your bot needs the 'usergroups:read' scope[/yellow]")
            console.print("Add it in: https://api.slack.com/apps → OAuth & Permissions → Scopes")


def generate_env_config(client: WebClient):
    """Generate a complete .env configuration file"""
    console.print("\n[bold cyan]Generating .env configuration...[/bold cyan]\n")
    
    config_lines = [
        "# ============================================",
        "# Slack Configuration (Auto-generated)",
        "# ============================================",
        "",
        "# Main bot token",
        f"SLACK_BOT_TOKEN={os.getenv('SLACK_BOT_TOKEN', 'your-token-here')}",
        "",
    ]
    
    # Fetch channels
    try:
        response = client.conversations_list(
            types="public_channel,private_channel",
            limit=200
        )
        
        oncall_channels = [c for c in response['channels'] if 'oncall' in c['name'].lower()]
        
        if oncall_channels:
            config_lines.extend([
                "# ============================================",
                "# Channel Mapping",
                "# ============================================",
                ""
            ])
            
            for channel in sorted(oncall_channels, key=lambda x: x['name']):
                name = channel['name'].replace('-', '_')
                config_lines.append(f"CHANNEL_{name}={channel['id']}")
            
            config_lines.append("")
    
    except SlackApiError as e:
        console.print(f"[yellow]Warning: Could not fetch channels: {e}[/yellow]")
    
    # Fetch user groups
    try:
        response = client.usergroups_list(include_users=False)
        
        if response['usergroups']:
            config_lines.extend([
                "# ============================================",
                "# User Group Mapping",
                "# ============================================",
                ""
            ])
            
            for group in sorted(response['usergroups'], key=lambda x: x['handle']):
                handle = group['handle'].replace('-', '_')
                config_lines.append(f"USERGROUP_{handle}={group['id']}")
            
            config_lines.append("")
    
    except SlackApiError as e:
        console.print(f"[yellow]Warning: Could not fetch user groups: {e}[/yellow]")
    
    # Add testing options
    config_lines.extend([
        "# ============================================",
        "# Testing Options",
        "# ============================================",
        "",
        "# Uncomment to test in a single channel",
        "# TEST_CHANNEL_OVERRIDE=#incident-testing",
        "",
        "DRY_RUN=false",
        "SPEED_MULTIPLIER=1.0",
        "LOG_LEVEL=INFO",
        ""
    ])
    
    # Write to file
    env_file = Path(".env")
    
    if env_file.exists():
        console.print("[yellow]⚠ .env file already exists[/yellow]")
        response = input("Overwrite? [y/N]: ")
        if response.lower() != 'y':
            console.print("Aborted. Writing to .env.generated instead")
            env_file = Path(".env.generated")
    
    with open(env_file, 'w') as f:
        f.write('\n'.join(config_lines))
    
    console.print(f"\n[bold green]✓ Configuration written to {env_file}[/bold green]")
    console.print(f"\nReview and edit {env_file}, then run:")
    console.print("  python scripts/post-to-slack.py scenarios/cache-failure-001.json --dry-run\n")


def main():
    parser = argparse.ArgumentParser(description="Slack setup helper")
    parser.add_argument('--list-channels', action='store_true', help='List all channels')
    parser.add_argument('--list-groups', action='store_true', help='List all user groups')
    parser.add_argument('--generate-env', action='store_true', help='Generate .env configuration')
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()
    
    # Get token
    token = os.getenv('SLACK_BOT_TOKEN')
    if not token:
        console.print("[bold red]Error:[/bold red] SLACK_BOT_TOKEN not set")
        console.print("\nSet it first:")
        console.print("  export SLACK_BOT_TOKEN=xoxb-your-token")
        console.print("Or add to .env file:")
        console.print("  SLACK_BOT_TOKEN=xoxb-your-token")
        sys.exit(1)
    
    # Initialize client
    client = WebClient(token=token)
    
    # Test authentication
    try:
        auth_response = client.auth_test()
        console.print(f"[green]✓ Connected to Slack workspace:[/green] {auth_response['team']}")
        console.print(f"[green]✓ Bot name:[/green] {auth_response['user']}\n")
    except SlackApiError as e:
        console.print(f"[bold red]Error:[/bold red] Failed to authenticate: {e}")
        sys.exit(1)
    
    # Execute command
    if args.list_channels:
        list_channels(client)
    elif args.list_groups:
        list_usergroups(client)
    elif args.generate_env:
        generate_env_config(client)
    else:
        # Show all by default
        list_channels(client)
        list_usergroups(client)
        
        console.print("\n[bold cyan]To generate .env configuration:[/bold cyan]")
        console.print("  python scripts/setup-slack.py --generate-env\n")


if __name__ == '__main__':
    main()
