# Context for Incident Insight Service

## What We Have: Artificial Slack Incident Data

We've generated **57 realistic incident scenarios** posted to Slack across **17 service channels**, simulating a microservices environment based on the OpenTelemetry Demo (e-commerce application).

## System Architecture

### Microservices (17 total):

```
Frontend Layer:
- frontend (Next.js)

Business Logic:
- recommendation (Python, Redis)
- product-catalog (Go, PostgreSQL)
- cart (C#, Valkey)
- checkout (Go, Kafka)
- payment (JavaScript)
- shipping (Rust)
- currency (C++)
- ad (Java)
- email (Ruby)

Backend Processing:
- accounting (C#, PostgreSQL, Kafka consumer)
- fraud-detection (Java, Kafka consumer)

Supporting:
- images (Python)
- reviews (Python, PostgreSQL, LLM)
- llm (Python)

Infrastructure:
- kafka (message queue)
- load-generator (testing)
```

### Service Dependencies (Critical for Understanding Cascading Failures):

```json
{
  "recommendation": ["product-catalog", "redis"],
  "product-catalog": ["postgresql"],
  "frontend": ["recommendation", "product-catalog", "ad", "cart", "checkout"],
  "checkout": ["cart", "currency", "email", "payment", "product-catalog", "shipping", "kafka"],
  "cart": ["valkey-cart"],
  "shipping": ["quote"],
  "accounting": ["postgresql", "kafka"],
  "fraud-detection": ["kafka"],
  "reviews": ["product-catalog", "llm", "postgresql"]
}
```

## Incident Data Structure

### Slack Channels:

Each service has a dedicated alert channel:
- `#recommendation-alert`
- `#product-catalog-alert`
- `#frontend-alert`
- `#payment-alert`
- `#checkout-alert`
- `#accounting-alert`
- `#cart-alert`
- `#shipping-alert`
- `#currency-alert`
- `#ad-alert`
- `#email-alert`
- `#fraud-alert`
- `#images-alert`
- `#reviews-alert`
- `#llm-alert`
- `#kafka-alert`
- `#load-gen-alert`

### Message Types:

1. **Alerts** (from PagerDuty Bot):
   - Posted by monitoring bot
   - Include severity (critical/warning/info)
   - Include metrics
   - Have dashboard/runbook links

2. **Messages** (from Engineers):
   - Format: `**engineer_name:** message content`
   - 27 different engineer personas (alice, bob, charlie, etc.)
   - Threaded under alerts

3. **Actions** (remediation steps):
   - kubectl commands
   - Flag toggles
   - Restarts, scaling, etc.

4. **Resolutions** (incident closed):
   - From engineers or monitoring bot
   - Include root cause analysis
   - Before/after metrics

### 57 Scenarios Breakdown:

**7 Intensive Discussions (~12%):**
- Complex incidents with 15-30 messages
- Multiple services involved
- Cross-channel coordination
- Full investigation → root cause → fix → resolution

**50 Quick Alerts (~88%):**
- 1-4 messages each
- False positives, auto-resolves, known issues
- Realistic noise in ops environment

## 27 Engineer Personas

Each engineer has a distinct communication style:

```json
{
  "alice": {
    "style": "analytical",
    "response_time": "fast",
    "characteristics": ["checks metrics first", "methodical debugger"]
  },
  "bob": {
    "style": "pragmatic",
    "response_time": "medium",
    "characteristics": ["action-oriented", "quick fixes"]
  },
  "charlie": {
    "style": "cautious",
    "response_time": "medium",
    "characteristics": ["checks impact", "coordinates teams"]
  },
  "grace": {
    "style": "efficient",
    "response_time": "very_fast",
    "characteristics": ["quick to identify", "fast fixer"]
  }
  // ... 23 more personas
}
```

## Incident Types and Patterns

### Pattern 1: Cascading Failure (Example: cache-failure)

```
Timeline in #recommendation-alert:
T+0s:   🟡 Alert: High Latency (P95: 520ms)
T+8s:   alice: "Looking into this"
T+42s:  alice: "Cache hit rate dropped to 0% 😱"
T+50s:  bob: "That explains it - hitting product-catalog for every request"

Timeline in #product-catalog-alert (60s later):
T+60s:  🟡 Alert: High CPU (68%)
T+68s:  charlie: "Whoa what's going on? 10x traffic suddenly"
T+75s:  charlie: "All from recommendation service"
T+85s:  charlie: "@recommendation-oncall are you having issues?"
T+92s:  alice: "Yes! Our cache is down"
T+100s: bob: [ACTION] Updated redis memory limit
T+150s: alice: [RESOLVED] ✅
T+155s: charlie: [CONFIRMED] ✅ Traffic back to normal
```

**Key Insight**: Cache failure in one service caused downstream overload

### Pattern 2: Single Service Issue (Example: high-cpu)

```
T+0s:   Alert in #ad-alert
T+5s:   olivia investigates
T+40s:  peter finds root cause (feature flag)
T+50s:  peter disables flag
T+70s:  [RESOLVED]
```

**Key Insight**: Isolated issue, quick resolution

### Pattern 3: Async Processing Lag (Example: kafka-lag)

```
T+0s:   Alert in #kafka-alert (consumer lag)
T+60s:  Alert in #accounting-alert (stale data)
T+65s:  Alert in #fraud-alert (detection delay)
T+85s:  xander disables flag
T+300s: Consumers catch up gradually
T+310s: [RESOLVED]
```

**Key Insight**: Infrastructure issue affecting multiple downstream consumers

### Pattern 4: Quick/Noisy Alerts

```
T+0s:   Alert fires
T+15s:  Engineer: "Looking at this"
T+30s:  Engineer: "False alarm - threshold too sensitive"
OR
T+0s:   Alert fires
T+120s: Monitoring Bot: "✅ Auto-resolved"
```

**Key Insight**: Most alerts are noise

## Data Schema

### JSON Structure (for each scenario):

```json
{
  "scenario_id": "cache-failure-001",
  "scenario_type": "cache-failure",
  "title": "Recommendation Service Cache Failure",
  "start_time": "2024-12-11T14:30:00Z",
  "services": {
    "recommendation": {
      "channel": "#recommendation-alert",
      "oncall_group": "@recommendation-oncall",
      "role": "primary"
    },
    "product-catalog": {
      "channel": "#product-catalog-alert",
      "oncall_group": "@product-catalog-oncall",
      "role": "downstream"
    }
  },
  "timeline": [
    {
      "offset_seconds": 0,
      "type": "alert",
      "channel": "#recommendation-alert",
      "severity": "warning",
      "title": "🟡 High Latency Detected",
      "details": "P95 latency increased...",
      "metrics": {
        "p95_latency": "520ms",
        "p99_latency": "890ms"
      }
    },
    {
      "offset_seconds": 8,
      "type": "message",
      "channel": "#recommendation-alert",
      "user": "alice",
      "content": "Looking into this",
      "thread_parent": 0
    }
  ],
  "metadata": {
    "severity": "SEV-3",
    "duration_seconds": 170,
    "services_impacted": 3,
    "root_cause": "Redis pod OOMKilled",
    "resolution": "Increased memory limit",
    "tags": ["cache", "redis", "memory", "cascade"]
  }
}
```

## Insights to Extract

### 1. Incident Patterns
- **Frequency by service**: Which services have most incidents?
- **Time distribution**: When do incidents occur?
- **Severity distribution**: How many critical vs warning?
- **Duration patterns**: Average time to resolve by type

### 2. Cascading Analysis
- **Dependency discovery**: Service A affects Service B
- **Cascade depth**: How many hops does an incident propagate?
- **Impact radius**: How many services affected by root cause?
- **Cross-channel correlation**: Alerts in multiple channels related?

### 3. Response Patterns
- **Time to acknowledge**: How fast do engineers respond?
- **Time to resolution**: How long to fix?
- **Response rate**: What % of alerts get human response?
- **Auto-resolve rate**: What % resolve without human action?

### 4. Root Cause Categories
```
Feature flags: 85% of intensive incidents
Configuration errors: 10%
Resource exhaustion: 5%

Common patterns:
- "feature flag enabled"
- "OOMKilled"
- "connection refused"
- "timeout"
- "rate limit"
```

### 5. Communication Patterns
- **@mentions frequency**: How often do teams coordinate?
- **Cross-channel incidents**: Services working together
- **Escalation patterns**: When do incidents escalate?
- **Collaboration signals**: Multiple people in thread

### 6. Engineer Behavior
- **Response speed by persona**: alice (fast), bob (medium), etc.
- **Communication style**: analytical vs pragmatic
- **Common phrases**: "checking...", "found it!", "resolved"
- **Action patterns**: Who restarts? Who investigates?

### 7. Service Reliability Metrics
```
By analyzing all incidents:
- Failure frequency per service
- Most common failure modes
- Services with most downstream impact
- Most critical dependencies
```

### 8. False Positive Patterns
```
- Threshold sensitivity issues
- Maintenance window alerts
- Deployment-related noise
- Flapping alerts
```

## Technical Details

### Message Format in Slack:

**Alerts:**
```
[PagerDuty Bot]
🟡 High Latency Detected - Recommendation Service

**Current Metrics:**
• P95: 520ms
• P99: 890ms

[📖 Runbook] [📊 Dashboard]
```

**Messages:**
```
[Main Bot]
**alice:** Looking into this 👀
```

**Actions:**
```
[Main Bot]
**bob:** 📈 Updated redis deployment memory limit: 256Mi → 512Mi

```
$ kubectl set resources deployment/redis --limits=memory=512Mi
```
```

**Resolutions:**
```
[Main Bot]
**alice:**
✅ **RESOLVED** - Cache is healthy

**Root Cause:** Redis pod OOMKilled
**Fix:** Increased memory limit
```

### Threading:
- Each alert creates a thread
- All discussion happens in replies under that alert
- Cross-channel coordination via @mentions

## Key Files and Data Sources

### Location:
```
incidentfox/generate-artificial-slack-messages/
├── scenarios/
│   ├── cache-failure-001.json
│   ├── payment-failure-001.json
│   ├── kafka-lag-001.json
│   ├── catalog-failure-001.json
│   ├── memory-leak-001.json
│   ├── latency-spike-001.json
│   ├── high-cpu-001.json
│   └── generated/
│       └── [50 quick alert scenarios]
├── lib/
│   ├── services.json (17 services, channels, dependencies)
│   └── personas.json (27 engineer profiles)
└── docs/
    └── cascade-impact-analysis.md (1700+ lines of failure analysis)
```

### To Access Slack Data:

**If consuming from Slack API:**
```python
# List channels
channels = ['#recommendation-alert', '#product-catalog-alert', ...]

# Fetch messages
for channel in channels:
    messages = slack_client.conversations_history(channel=channel)
    # Process messages
```

**If consuming from JSON files:**
```python
import json
from pathlib import Path

# Load all scenarios
scenarios_dir = Path("scenarios")
all_scenarios = []

for scenario_file in scenarios_dir.glob("**/*.json"):
    with open(scenario_file) as f:
        all_scenarios.append(json.load(f))

# Each scenario has: timeline, services, metadata
```

## Sample Insights to Extract

### 1. Service Health Dashboard
```
Service: recommendation
- Total incidents: 4
- Critical: 0, Warning: 4
- Avg resolution time: 92 seconds
- Most common: cache failures
- Impact: 2 downstream services on average
```

### 2. Dependency Graph Discovery
```
Detected dependencies from incidents:
recommendation → product-catalog (cache-failure-001)
payment → checkout (payment-failure-001)
kafka → [accounting, fraud-detection] (kafka-lag-001)
product-catalog → [frontend, recommendation, checkout] (catalog-failure-001)
```

### 3. Incident Timeline Visualization
```
10:00 AM - [SEV-4] shipping-alert: High CPU (auto-resolved)
10:15 AM - [SEV-4] accounting-alert: Message backlog (false positive)
11:15 AM - [SEV-2] kafka-alert: Consumer lag → accounting + fraud (310s)
13:20 PM - [SEV-1] product-catalog-alert: DB error → 4 services (135s)
14:10 PM - [SEV-3] ad-alert: CPU saturation → frontend (75s)
```

### 4. Engineer Performance
```
alice: 12 incidents handled, avg response: 8s, resolution rate: 100%
bob: 8 incidents, avg response: 15s, action-oriented (restarts/scales)
charlie: 6 incidents, coordinates cross-team 83% of time
grace: 5 incidents, fastest finder (avg 35s to root cause)
```

### 5. Alert Noise Analysis
```
Total alerts: 57
- Actionable: 7 (12%)
- False positives: 12 (21%)
- Auto-resolved: 21 (37%)
- Known issues: 10 (18%)
- Maintenance: 7 (12%)

Recommendation: Tune thresholds to reduce 21% false positive rate
```

### 6. Root Cause Categories
```
Feature flags accidentally enabled: 6 incidents (86% of intensive)
Configuration errors: 1 incident (14%)
Resource exhaustion: Multiple (memory, CPU, disk)

Action: Implement safeguards for feature flag management
```

### 7. Cross-Service Impact Analysis
```
Incidents with cascading failures:
- cache-failure: 1 service → 2 downstream (cascade depth: 2)
- catalog-failure: 1 service → 3 downstream (cascade depth: 2)
- kafka-lag: 1 service → 2 consumers (cascade depth: 1)

Highest impact service: product-catalog (affected 3 others in catalog-failure)
```

### 8. Communication Effectiveness
```
Incidents with @mentions: 6/7 intensive (86%)
Average time to cross-team coordination: 85 seconds
Response time after @mention: avg 7 seconds

Effective pattern: Quick @mention leads to faster resolution
```

### 9. Temporal Patterns
```
Alert distribution by hour:
09:00-12:00: 15 alerts (morning spike)
12:00-15:00: 22 alerts (peak)
15:00-18:00: 20 alerts (afternoon)

Insight: Peak incidents during business hours (as expected)
```

### 10. Recurring Issues
```
Detected recurring patterns:
- Cache failures: 2 instances (recommendation, cart)
- Memory pressure: 3 instances (email, redis, postgresql)
- Feature flag issues: 6 instances

Recommendation: Create runbook for common feature flag incidents
```

## Example Code Structure for Insight Service

### Data Ingestion:

```python
class SlackIncidentParser:
    """Parse Slack messages into structured incident data"""
    
    def parse_thread(self, messages: List[Dict]) -> Incident:
        """Parse a thread of messages into an Incident object"""
        alert = self._find_alert(messages)
        engineer_messages = self._find_messages(messages)
        resolution = self._find_resolution(messages)
        
        return Incident(
            service=self._extract_service(alert),
            severity=alert.get('severity'),
            start_time=alert.get('timestamp'),
            end_time=resolution.get('timestamp'),
            metrics=self._extract_metrics(messages),
            engineers_involved=self._extract_engineers(engineer_messages),
            root_cause=self._extract_root_cause(resolution),
            mentions=self._extract_mentions(engineer_messages)
        )
```

### Pattern Detection:

```python
class CascadeDetector:
    """Detect cascading failures across services"""
    
    def detect_cascades(self, incidents: List[Incident]) -> List[Cascade]:
        """Find related incidents across channels"""
        cascades = []
        
        # Group incidents by time window (within 5 minutes)
        for incident in incidents:
            related = self._find_related_incidents(
                incident, 
                incidents, 
                time_window=300  # 5 minutes
            )
            
            if related:
                cascade = Cascade(
                    root_incident=incident,
                    affected_services=related,
                    cascade_depth=len(related),
                    total_duration=max(i.duration for i in related)
                )
                cascades.append(cascade)
        
        return cascades
```

### Insight Generation:

```python
class IncidentInsights:
    """Generate insights from incident data"""
    
    def generate_service_health_report(self, incidents: List[Incident]):
        """Per-service health and reliability metrics"""
        
    def detect_dependency_graph(self, cascades: List[Cascade]):
        """Infer service dependencies from cascading failures"""
        
    def analyze_response_times(self, incidents: List[Incident]):
        """Engineer and team response effectiveness"""
        
    def identify_recurring_issues(self, incidents: List[Incident]):
        """Find patterns in root causes"""
        
    def calculate_noise_ratio(self, incidents: List[Incident]):
        """Signal vs noise analysis"""
```

## Example Queries Your Service Could Answer

1. **"Which service has the most incidents?"**
   → product-catalog (appears in 3 intensive incidents)

2. **"What causes cascading failures?"**
   → Cache failures, database issues, kafka lag

3. **"How effective is our on-call team?"**
   → 7/7 intensive incidents resolved, avg 147 seconds

4. **"Which alerts are noise?"**
   → 42/50 quick alerts are non-actionable (false positive or auto-resolve)

5. **"What are common root causes?"**
   → Feature flags (6/7), configuration errors (1/7)

6. **"Which services depend on product-catalog?"**
   → frontend, recommendation, checkout (discovered from incidents)

7. **"Who's the fastest responder?"**
   → alice (avg 8s), grace (avg 10s)

8. **"What's the cost of incidents?"**
   → Total revenue impact: $9,500 (from metadata)

9. **"Which incidents need post-mortems?"**
   → All SEV-1 and SEV-2 (3 incidents)

10. **"What should we fix first?"**
    → Feature flag management (causes 86% of incidents)

## Data Extraction Guide

### From JSON Files:

```python
# Load scenario
scenario = json.load(open("scenarios/cache-failure-001.json"))

# Extract key info
service_impacted = scenario['metadata']['services_impacted']
root_cause = scenario['metadata']['root_cause']
duration = scenario['metadata']['duration_seconds']
tags = scenario['metadata']['tags']

# Parse timeline
for event in scenario['timeline']:
    if event['type'] == 'alert':
        severity = event['severity']
        metrics = event['metrics']
    elif event['type'] == 'message':
        engineer = event['user']
        content = event['content']
        timestamp = event['offset_seconds']
```

### From Slack API:

```python
# Fetch messages
response = client.conversations_history(
    channel="C01RECOMMEND",  # channel ID
    limit=1000
)

# Parse messages
for message in response['messages']:
    text = message['text']
    timestamp = message['ts']
    thread_ts = message.get('thread_ts')
    
    # Extract persona name
    if text.startswith('**'):
        persona = text.split('**')[1].rstrip(':')
        content = text.split('**')[2]
```

## Important Patterns to Detect

### 1. @mention = Cross-team coordination
When you see `@service-oncall`, it means:
- Service A discovered dependency on Service B
- Useful for building dependency graph

### 2. Metrics in messages = Investigation
When messages contain numbers (latency, CPU, etc.):
- Engineer is actively debugging
- Shows investigation depth

### 3. kubectl commands = Remediation actions
When you see command blocks:
- Actual fix being applied
- Type of action (restart, scale, config change)

### 4. "✅ RESOLVED" = Incident closed
- Marks end of incident
- Usually includes root cause summary

### 5. Multiple alerts in short time = Cascade
If alerts fire in multiple channels within 5 minutes:
- Likely related (cascading failure)
- Check for dependencies

## Summary Statistics (What We Generated)

```
Total scenarios: 57
├── Intensive: 7 (12%)
│   ├── Services involved: 2-4 per incident
│   ├── Messages per incident: 15-30
│   ├── Duration: 75-310 seconds
│   └── Engineers involved: 2-5
└── Quick: 50 (88%)
    ├── Services involved: 1 per incident
    ├── Messages per incident: 0-4
    ├── Duration: 10-180 seconds
    └── Auto-resolved: ~21 (42%)

Total messages: ~260 across all scenarios
Channels used: 17 service channels
Personas used: 27 engineers
Cross-channel incidents: 7 (all intensive scenarios)
@mentions: 12 instances
```

## Files to Copy to New Service

**Essential files:**
1. `scenarios/` folder (all 57 JSON files)
2. `lib/services.json` (service definitions and dependencies)
3. `lib/personas.json` (engineer profiles)
4. `schema/incident-schema.json` (data structure)
5. `cascade-impact-analysis.md` (failure mode analysis)

**Optional but helpful:**
6. `SCENARIOS_OVERVIEW.md` (summary of what we built)

## Quick Start for Your Insight Service

```python
import json
from pathlib import Path
from collections import Counter, defaultdict

# Load all scenarios
scenarios_dir = Path("incidentfox/generate-artificial-slack-messages/scenarios")
scenarios = []

for file in scenarios_dir.glob("**/*.json"):
    with open(file) as f:
        scenarios.append(json.load(f))

# Extract insights
print(f"Total scenarios: {len(scenarios)}")
print(f"Intensive: {sum(1 for s in scenarios if s['scenario_type'] != 'quick-alert')}")
print(f"Quick: {sum(1 for s in scenarios if s['scenario_type'] == 'quick-alert')}")

# Service frequency
services = Counter()
for s in scenarios:
    for service in s['services'].keys():
        services[service] += 1

print("\nIncidents per service:")
for service, count in services.most_common(10):
    print(f"  {service}: {count}")

# Root causes
root_causes = Counter(s['metadata']['root_cause'] for s in scenarios)
print("\nRoot causes:")
for cause, count in root_causes.most_common():
    print(f"  {cause}: {count}")
```

## Expected Insights Output Example

```
🎯 Incident Analysis Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Overview:
  • Total incidents: 57
  • Critical: 3 (5%)
  • Warning: 44 (77%)
  • Info: 10 (18%)
  • Avg resolution time: 47 seconds

🔥 Top Incident-Prone Services:
  1. product-catalog: 8 incidents (3 intensive, 5 quick)
  2. frontend: 7 incidents (3 intensive, 4 quick)
  3. accounting: 6 incidents (1 intensive, 5 quick)

🔗 Discovered Dependencies (from cascading failures):
  recommendation → product-catalog (cache bypass)
  product-catalog → [frontend, recommendation, checkout] (DB dependency)
  kafka → [accounting, fraud-detection] (consumer dependency)
  payment → checkout (payment processing)

⚡ Alert Noise Analysis:
  • Actionable: 7 (12%)
  • False positives: 12 (21%) ⚠️
  • Auto-resolved: 21 (37%)
  • Known issues: 10 (18%)

💡 Key Recommendations:
  1. Implement feature flag safeguards (86% of incidents)
  2. Tune alert thresholds (21% false positive rate)
  3. Add pre-deployment validation (config errors)
  4. Monitor cache hit rates proactively
  5. Implement auto-scaling for kafka consumers

👥 Team Performance:
  • Fastest responder: alice (avg 8s)
  • Most incidents handled: alice (12)
  • Best coordinator: charlie (cross-team @mentions: 4)
  • Most efficient: grace (avg 35s to root cause)

📈 Trends:
  • Peak incident time: 12:00-15:00 (22 incidents)
  • Most common cascade: cache → database load
  • Response rate: 58% (33/57 get human response)
```

---

## Summary for Cursor Context

**Copy this entire document** into your new service's Cursor context. It contains:

✅ Complete architecture (17 services, dependencies)
✅ Data structure (JSON schema with examples)
✅ 57 scenario descriptions (7 intensive + 50 quick)
✅ Insight ideas (10 categories of insights to extract)
✅ Code examples (parsing, analysis, detection)
✅ Expected outputs (what insights look like)

**Additional files to reference:**
- `services.json` - Service definitions
- `personas.json` - Engineer profiles
- `cascade-impact-analysis.md` - Failure mode analysis
- Any scenario JSON file - Example data structure

This gives complete context to build an incident insight/analytics service! 🚀
