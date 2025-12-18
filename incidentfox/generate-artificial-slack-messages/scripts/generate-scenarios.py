#!/usr/bin/env python3
"""
Generate realistic alert scenarios for populating Slack channels

This creates a mix of:
- 90% quick/noisy alerts (false positives, auto-resolved, etc.)
- 10% intensive discussion incidents

All based on the cascade impact analysis and real service dependencies.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

# Load service configuration
SCRIPT_DIR = Path(__file__).parent.parent
with open(SCRIPT_DIR / "lib/services.json") as f:
    SERVICES_CONFIG = json.load(f)

# Service dependencies from cascade analysis
SERVICE_DEPENDENCIES = {
    "recommendation": ["product-catalog", "redis"],
    "product-catalog": ["postgresql"],
    "frontend": ["recommendation", "product-catalog", "ad", "cart", "checkout"],
    "checkout": ["cart", "currency", "email", "payment", "product-catalog", "shipping", "kafka"],
    "payment": [],
    "cart": ["valkey-cart"],
    "email": [],
    "shipping": ["quote"],
    "currency": [],
    "ad": [],
    "accounting": ["postgresql", "kafka"],
    "fraud-detection": ["kafka"],
    "images": [],
    "reviews": ["product-catalog", "llm", "postgresql"],
    "llm": []
}

# Common alert types with variations
ALERT_TYPES = {
    "high_latency": ["P95 latency spike", "P99 latency increased", "Slow response times"],
    "high_cpu": ["CPU usage high", "CPU spike detected", "CPU above threshold"],
    "high_memory": ["Memory usage high", "Memory spike", "Memory pressure"],
    "high_error_rate": ["Error rate increased", "5xx errors spiking", "Failed requests"],
    "low_success_rate": ["Success rate dropped", "Request failures", "Service degraded"],
    "disk_space": ["Disk usage high", "Disk space low", "Storage pressure"],
    "connection_errors": ["Connection failures", "Timeout errors", "Connection refused"],
    "queue_lag": ["Consumer lag high", "Message backlog", "Queue depth increasing"],
}

# Quick response patterns
QUICK_RESPONSES = {
    "false_positive": [
        "Looking at this",
        "Metrics actually look fine",
        "False alarm - threshold too sensitive",
        "Snoozing"
    ],
    "auto_resolved": [
        "Checking...",
        "Already back to normal",
        "Resolved itself 👍",
        "Looks like a blip"
    ],
    "acknowledged": [
        "Ack'd",
        "Will check after standup",
        "Known issue - TICKET-{ticket}",
        "On it"
    ],
    "maintenance": [
        "Expected - maintenance window",
        "Deployment in progress",
        "Ignore - planned change"
    ],
    "threshold_adjust": [
        "This keeps firing",
        "Need to adjust threshold",
        "Creating ticket to tune alert",
        "Too noisy"
    ]
}

def generate_ticket_number():
    """Generate realistic ticket number"""
    return f"INC-{random.randint(1000, 9999)}"

def generate_quick_alert(service: str, index: int, base_time: datetime) -> Dict:
    """Generate a quick/noisy alert"""
    
    # Get proper channel from services.json, fallback to generated name
    service_config = SERVICES_CONFIG.get(service, {})
    channel = service_config.get("channel", f"#{service}-alert")
    oncall_group = service_config.get("oncall_group", f"@{service}-oncall")
    service_name = service_config.get("service_name", service.replace("-", " ").title())
    
    alert_category = random.choice(list(ALERT_TYPES.keys()))
    alert_title = random.choice(ALERT_TYPES[alert_category])
    
    response_type = random.choice([
        "false_positive", "auto_resolved", "acknowledged", 
        "maintenance", "threshold_adjust"
    ])
    
    # Pick an engineer from the service or random
    engineers = service_config.get("engineers", []) or [
        "alice", "bob", "charlie", "diana", "eve", "frank", "grace", 
        "henry", "iris", "jack", "kate", "leo", "maria", "nathan"
    ]
    engineer = random.choice(engineers)
    
    # Generate timeline
    timeline = [
        {
            "offset_seconds": 0,
            "type": "alert",
            "channel": channel,
            "severity": random.choice(["warning", "info"]),
            "title": f"🟡 {alert_title} - {service_name}",
            "details": f"Metrics show {alert_title.lower()}",
            "metrics": {
                "current_value": f"{random.randint(60, 95)}%",
                "threshold": "80%"
            },
            "thread_parent": None
        }
    ]
    
    # Decide if anyone responds
    no_human_response = random.random() < 0.3  # 30% chance nobody responds
    
    if no_human_response:
        # Auto-resolve from monitoring bot after some time
        timeline.append({
            "offset_seconds": random.randint(60, 180),
            "type": "resolution",
            "channel": channel,
            "user": "Monitoring Bot",
            "content": "✅ Auto-resolved: Metrics returned to normal",
            "metrics_after": {
                "status": "healthy",
                "value": "normal"
            },
            "thread_parent": 0
        })
    else:
        # Add 1-3 quick responses from engineers
        responses = QUICK_RESPONSES[response_type]
        for i, response in enumerate(responses[:random.randint(1, 3)]):
            if "{ticket}" in response:
                response = response.format(ticket=generate_ticket_number())
            timeline.append({
                "offset_seconds": 15 + (i * 20),
                "type": "message",
                "channel": channel,
                "user": engineer,
                "content": response,
                "thread_parent": 0
            })
        
        # Some alerts also auto-resolve after human ack
        if response_type in ["false_positive", "auto_resolved"] and random.random() < 0.5:
            timeline.append({
                "offset_seconds": timeline[-1]["offset_seconds"] + 45,
                "type": "resolution",
                "channel": channel,
                "user": "Monitoring Bot",
                "content": "✅ Auto-resolved: Metrics returned to baseline",
                "thread_parent": 0
            })
    
    return {
        "scenario_id": f"{service}-quick-{index:03d}",
        "scenario_type": "quick-alert",
        "title": f"{alert_title} - {service}",
        "start_time": base_time.isoformat(),
        "services": {
            service: {
                "channel": channel,
                "oncall_group": oncall_group,
                "role": "primary"
            }
        },
        "timeline": timeline,
        "metadata": {
            "severity": "SEV-4",
            "duration_seconds": timeline[-1]["offset_seconds"],
            "services_impacted": 1,
            "root_cause": response_type,
            "tags": ["quick", response_type, alert_category]
        }
    }

def main():
    """Generate 50+ alert scenarios"""
    
    scenarios_dir = Path("scenarios")
    generated_dir = scenarios_dir / "generated"
    generated_dir.mkdir(exist_ok=True)
    
    # Get services from services.json (use keys)
    services = list(SERVICES_CONFIG.keys())
    
    # Generate 50 quick alerts
    base_time = datetime(2024, 12, 11, 10, 0, 0)  # Start at 10 AM
    
    print("Generating 50 quick/noisy alerts...")
    for i in range(50):
        service = random.choice(services)
        # Spread alerts throughout the day
        alert_time = base_time + timedelta(minutes=random.randint(0, 480))  # 8 hour spread
        
        scenario = generate_quick_alert(service, i + 1, alert_time)
        
        filename = generated_dir / f"{scenario['scenario_id']}.json"
        with open(filename, 'w') as f:
            json.dump(scenario, f, indent=2)
        
        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1}/50 scenarios...")
    
    print(f"\n✅ Generated 50 quick alert scenarios in {generated_dir}/")
    print("\nScenario breakdown:")
    print("  - False positives: ~10-12")
    print("  - Auto-resolved: ~10-12")
    print("  - Acknowledged: ~10-12")
    print("  - Maintenance/Deployment: ~8-10")
    print("  - Threshold adjustments: ~8-10")
    
    print("\nTo post all scenarios:")
    print(f"  for scenario in {generated_dir}/*.json; do")
    print(f"    python3 scripts/post-to-slack.py \"$scenario\" --yes --realtime --speed 50")
    print(f"    sleep 30")
    print(f"  done")

if __name__ == "__main__":
    main()
