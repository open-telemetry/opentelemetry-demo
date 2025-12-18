"""
Slack client wrapper for posting incident scenario messages
"""

import os
import time
import logging
from typing import Dict, List, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackIncidentClient:
    """Wrapper around Slack API for posting incident messages"""
    
    def __init__(
        self, 
        token: str, 
        dry_run: bool = False, 
        test_channel: Optional[str] = None,
        alert_bot_token: Optional[str] = None,
        alert_bot_name: Optional[str] = None,
        channel_mapping: Optional[Dict[str, str]] = None,
        usergroup_mapping: Optional[Dict[str, str]] = None
    ):
        """
        Initialize Slack client
        
        Args:
            token: Main Slack bot token
            dry_run: If True, don't actually post messages
            test_channel: If provided, override all channels to post to this one
            alert_bot_token: Optional separate bot token for alerts
            alert_bot_name: Name to display for alert bot
            channel_mapping: Map scenario channels to actual Slack channels
            usergroup_mapping: Map scenario usergroups to actual Slack usergroups
        """
        self.client = WebClient(token=token)
        self.dry_run = dry_run
        self.test_channel = test_channel
        self.message_timestamps = {}  # Map index -> timestamp for threading
        self.message_channels = {}  # Map index -> channel for reactions
        
        # Alert bot configuration
        self.alert_client = WebClient(token=alert_bot_token) if alert_bot_token else self.client
        self.alert_bot_name = alert_bot_name or "Monitoring Alert"
        
        # Channel and usergroup mapping
        self.channel_mapping = channel_mapping or {}
        self.usergroup_mapping = usergroup_mapping or {}
        
        # Track if reactions are supported
        self.reactions_supported = True
        
    def _get_channel(self, channel: str) -> str:
        """
        Get actual channel to post to
        
        Priority:
        1. test_channel override (if set)
        2. channel_mapping (if channel is mapped)
        3. original channel name
        """
        if self.test_channel:
            return self.test_channel
        
        # Check if this channel is mapped to a different one
        if channel in self.channel_mapping:
            return self.channel_mapping[channel]
        
        # Try without # prefix for mapping lookup
        channel_key = channel.lstrip('#').replace('-', '_')
        if channel_key in self.channel_mapping:
            return self.channel_mapping[channel_key]
        
        return channel
    
    def _resolve_mentions(self, content: str) -> str:
        """
        Resolve @mentions to actual Slack usergroup IDs
        
        Converts @recommendation-oncall to <!subteam^S01ABC123|recommendation-oncall>
        """
        if not self.usergroup_mapping:
            return content
        
        for mention, group_id in self.usergroup_mapping.items():
            # Handle both @mention and mention formats
            mention_with_at = mention if mention.startswith('@') else f'@{mention}'
            mention_without_at = mention.lstrip('@')
            
            # If group_id starts with S, it's a group ID - format properly
            if group_id.startswith('S'):
                replacement = f'<!subteam^{group_id}|{mention_without_at}>'
            else:
                # Otherwise it's a handle, keep it as is
                replacement = group_id
            
            content = content.replace(mention_with_at, replacement)
        
        return content
    
    def post_alert(
        self,
        channel: str,
        severity: str,
        title: str,
        details: str,
        metrics: Optional[Dict[str, str]] = None,
        runbook: Optional[str] = None,
        dashboard: Optional[str] = None,
        thread_parent: Optional[int] = None
    ) -> str:
        """
        Post an alert message
        
        Returns:
            Message timestamp (for threading)
        """
        channel = self._get_channel(channel)
        
        # Build alert message
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "ℹ️"
        }
        emoji = severity_emoji.get(severity, "⚠️")
        
        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": details
                }
            }
        ]
        
        # Add metrics if provided
        if metrics:
            metrics_text = "*Metrics:*\n" + "\n".join(
                f"• `{key}`: {value}" for key, value in metrics.items()
            )
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": metrics_text
                }
            })
        
        # Add links if provided
        if runbook or dashboard:
            elements = []
            if runbook:
                elements.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📖 Runbook"
                    },
                    "url": runbook
                })
            if dashboard:
                elements.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Dashboard"
                    },
                    "url": dashboard
                })
            blocks.append({
                "type": "actions",
                "elements": elements
            })
        
        return self._post_message(
            channel=channel,
            blocks=blocks,
            text=title,  # Fallback text
            thread_ts=self.message_timestamps.get(thread_parent) if thread_parent is not None else None,
            use_alert_bot=True  # Use alert bot for alerts
        )
    
    def post_message(
        self,
        channel: str,
        user: str,
        content: str,
        thread_parent: Optional[int] = None,
        mentions: Optional[List[str]] = None
    ) -> str:
        """
        Post a regular message from a user
        
        Since we don't have real users, we format the message to show who's speaking
        
        Returns:
            Message timestamp (for threading)
        """
        channel = self._get_channel(channel)
        
        # Format message to show the persona name
        # This makes it clear who's "speaking" even though it's posted by the bot
        formatted_content = f"**{user}:** {content}"
        
        # Resolve @mentions
        formatted_content = self._resolve_mentions(formatted_content)
        
        return self._post_message(
            channel=channel,
            text=formatted_content,
            thread_ts=self.message_timestamps.get(thread_parent) if thread_parent is not None else None
        )
    
    def post_action(
        self,
        channel: str,
        user: str,
        action_type: str,
        action_details: str,
        content: str,
        thread_parent: Optional[int] = None
    ) -> str:
        """
        Post an action message (e.g., restart, scale, flag toggle)
        
        Returns:
            Message timestamp (for threading)
        """
        channel = self._get_channel(channel)
        
        action_emoji = {
            "restart": "🔄",
            "scale": "📈",
            "flag_toggle": "🚩",
            "rollback": "⏮️",
            "manual_fix": "🔧"
        }
        emoji = action_emoji.get(action_type, "⚡")
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"**{user}:** {emoji} *{action_details}*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content
                }
            }
        ]
        
        return self._post_message(
            channel=channel,
            blocks=blocks,
            text=f"{user}: {emoji} {action_details}",
            thread_ts=self.message_timestamps.get(thread_parent) if thread_parent is not None else None
        )
    
    def post_resolution(
        self,
        channel: str,
        user: str,
        content: str,
        metrics_after: Optional[Dict[str, str]] = None,
        thread_parent: Optional[int] = None
    ) -> str:
        """
        Post a resolution message
        
        Returns:
            Message timestamp (for threading)
        """
        channel = self._get_channel(channel)
        
        # Check if this is from a bot/system (not a human engineer)
        is_bot = user.lower() in ["monitoring bot", "pagerduty bot", "alert bot", "system"]
        
        if is_bot:
            # Post as alert bot (no persona name prefix)
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": content
                    }
                }
            ]
        else:
            # Post as human engineer
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"**{user}:**\n{content}"
                    }
                }
            ]
        
        if metrics_after:
            metrics_text = "*Metrics After Resolution:*\n" + "\n".join(
                f"• `{key}`: {value}" for key, value in metrics_after.items()
            )
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": metrics_text
                }
            })
        
        return self._post_message(
            channel=channel,
            blocks=blocks,
            text=f"{user}: {content}",
            thread_ts=self.message_timestamps.get(thread_parent) if thread_parent is not None else None,
            use_alert_bot=is_bot  # Use alert bot for system resolutions
        )
    
    def add_reaction(
        self,
        message_index: int,
        emoji: str,
        users: List[str]
    ):
        """Add emoji reactions to a message"""
        # Skip if reactions not supported
        if not self.reactions_supported:
            return
            
        if message_index not in self.message_timestamps:
            logger.warning(f"Cannot add reaction: message index {message_index} not found")
            return
        
        timestamp = self.message_timestamps[message_index]
        channel = self.message_channels.get(message_index)
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would add reaction :{emoji}: to message {timestamp}")
            return
        
        try:
            self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
        except SlackApiError as e:
            error_msg = str(e)
            if "missing_scope" in error_msg and "reactions:write" in error_msg:
                logger.warning("Bot missing 'reactions:write' scope - disabling reactions")
                logger.info("To enable: Add 'reactions:write' scope in Slack App settings")
                self.reactions_supported = False  # Disable for future attempts
            else:
                logger.error(f"Error adding reaction: {e}")
    
    def _post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        username: Optional[str] = None,
        thread_ts: Optional[str] = None,
        use_alert_bot: bool = False
    ) -> str:
        """
        Internal method to post a message
        
        Args:
            use_alert_bot: If True, use alert_client instead of main client
        
        Returns:
            Message timestamp
        """
        if self.dry_run:
            bot_name = self.alert_bot_name if use_alert_bot else "Main Bot"
            logger.info(f"[DRY RUN] [{bot_name}] Would post to {channel}: {text[:100]}...")
            if thread_ts:
                logger.info(f"  └─ In thread: {thread_ts}")
            return f"ts_dryrun_{time.time()}"
        
        # Choose which client to use
        client = self.alert_client if use_alert_bot else self.client
        
        try:
            response = client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                username=username if username else (self.alert_bot_name if use_alert_bot else None),
                thread_ts=thread_ts
            )
            
            timestamp = response["ts"]
            bot_name = self.alert_bot_name if use_alert_bot else "Main Bot"
            logger.info(f"[{bot_name}] Posted to {channel}: {text[:100]}...")
            
            return timestamp
            
        except SlackApiError as e:
            error_msg = str(e)
            if "channel_not_found" in error_msg:
                logger.error(f"Channel not found: {channel}")
                logger.error(f"Make sure the bot is invited to the channel:")
                logger.error(f"  In Slack: /invite @your-bot to {channel}")
            elif "not_in_channel" in error_msg:
                logger.error(f"Bot is not a member of {channel}")
                logger.error(f"Invite the bot: /invite @your-bot to {channel}")
            else:
                logger.error(f"Error posting message: {e}")
            raise
    
    def register_message(self, index: int, timestamp: str, channel: str = None):
        """Register a message timestamp for threading"""
        self.message_timestamps[index] = timestamp
        if channel:
            self.message_channels[index] = channel
