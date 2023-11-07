# Observability Introduction Tutorial
The purpose of this tutorial is to provide the skill set for the user to start building his system's observability representation
using the tools supplied by the Observability plugin.

---

## The Observability acronyms:

The next section describes the main Observability acronyms that are used in the daily work of the Observability domain experts and reliability engineers.
Understanding their concepts and how to use them play a key factor in this tutorial. 

### The SAAFE model
The SAAFE model is a comprehensive approach to Observability that stands for Secure, Adaptable, Automated, Forensic, and Explainable.

Each element of this model plays a vital role in enhancing the visibility and understanding of systems.

- **"Secure"** ensures that all data in the system is protected and interactions are guarded against security threats.

- **"Adaptable"** allows systems to adjust to changing conditions and requirements, making them robust and resilient to evolving business needs and technological advancements.

- **"Automated"** involves the use of automation to reduce manual tasks, improve accuracy, and enhance system efficiency. This includes automated alerting, remediation, and anomaly detection, among other tasks.

- **"Forensic"** refers to the ability to retrospectively analyze system states and behaviors, which is crucial for debugging, identifying root causes of issues, and learning from past incidents. 

- **"Explainable"** stresses the importance of clear, understandable insights. It's not just about having data; it's about making that data meaningful, comprehensible, and actionable for engineers and stakeholders. 

The SAAFE model provides a holistic approach to Observability, ensuring systems are reliable, efficient, secure, and user-friendly.


### The Insight Strategy

To be able to correctly quantify the health of the system, an observability domain expert can create a set of metrics that represents the overall KPI health hot-spots
of the system.

Once any of these KPIs are exceeded - an Insight is generated with the appropriate context in-which the user can investigate the cause of this behavior.

The most likely metrics to take part of these collections are the most "central" services that are part of the system which have the highest potential to influence and impact 
the user's satisfaction of the system.

In this context, "centrality" refers to the importance or influence of certain components or services within the overall system.

Central services are the ones that play a crucial role in system operations, acting as a hub or a nexus for other services.

They often process a large volume of requests, interact with many other services, or handle critical tasks that directly impact the user experience.

An issue in a central service can have cascading effects throughout the system, affecting many other components and potentially degrading the user experience significantly. 

That's why monitoring the key performance indicators (KPIs) of these central services can be particularly informative about the overall system's health.

By focusing on these central services, an observability domain expert can quickly identify and address issues that are likely to have a significant impact on the system.

When any of the KPIs for these services exceed their thresholds, an Insight is generated, providing valuable context for investigating and resolving the issue.

This approach enhances system reliability and user satisfaction by ensuring that potential problems are identified and addressed proactively.

### The RED monitoring Strategy

The RED method in Observability is a key monitoring strategy adopted by organizations to understand the performance of their systems. 
The RED acronym stands for **Rate**, **Errors**, and **Duration**.

- **"Rate"**

indicates the number of requests per second that your system is serving, helping you measure the load and traffic on your system.

- **"Errors"**

tracks the number of failed requests over a period of time, which could be due to various reasons such as server issues, bugs in the code, or problems with infrastructure.

- **"Duration"**

measures the amount of time it takes to process a request, which is crucial to understand the system latency and responsiveness.

By monitoring these three aspects, organizations can gain valuable insights into their systems' health and performance, allowing them to make data-driven decisions, optimize processes, and maintain a high level of service quality.

### Service Level Objectives (SLOs) and Service Level Agreements (SLAs)

Service Level Objectives (SLOs) and Service Level Agreements (SLAs) are essential aspects of Observability, playing crucial roles in maintaining and improving the quality of services in any system.

An SLO represents the target reliability of a particular service over a period, often defined in terms of specific metrics like error rate, latency, or uptime.

They form the basis for informed decision making, providing a clear understanding of the expected system behavior and guiding the engineering teams in their operations and development efforts.

On the other hand, an SLA is a formal agreement between a service provider and its users that defines the expected level of service.

It usually includes the SLOs, as well as the repercussions for not meeting them, such as penalties or compensations. 

This ensures accountability, aids in setting realistic expectations, and allows the service provider to manage and mitigate potential issues proactively. Therefore, both SLOs and SLAs are indispensable tools for maintaining service quality, enhancing user satisfaction, and driving continuous improvement.

### The burn-rate Strategy

SLO burn rate is a concept in site reliability engineering that refers to the rate at which a service is consuming or "burning" through its error budget. 

The error budget is essentially the allowable threshold of unreliability, which is derived from the service's Service Level Objective (SLO). If a service is fully reliable and experiencing no issues, it won't be burning its error budget at all, meaning the burn rate is zero. 

On the other hand, if a service is experiencing issues and failures, it will be burning through its error budget at a certain rate.

The burn rate is an important metric because it can provide an early warning sign of trouble. If the burn rate is too high, it means the service is using up its error budget too quickly, and if left unchecked, it could exceed its SLO before the end of the measurement period. 

By monitoring the burn rate, teams can proactively address issues, potentially before they escalate and impact users significantly.

### Baseline and Anomaly Detection

Anomaly detection in Observability is a powerful technique used to identify unusual behavior or outliers within system metrics that deviate from normal operation.

Anomalies could be indicative of potential issues such as bugs in code, infrastructure problems, security breaches, or even performance degradation. 

For instance, an unexpected surge in error rates or latency might signify a system failure or a sudden drop in traffic could imply an issue with the user interface. 

Anomaly detection algorithms, often incorporating machine learning techniques which are based on taking the base-line from a functioning system.

Once we have a baseline sampling mechanism it is used to analyze the system data over time to learn what constitutes "normal" behavior . 

Then, they continuously monitor the system's state and alert engineers when they detect patterns that diverge from this established norm. 

These alerts enable teams to proactively address issues, often before they affect end-users, thereby enhancing the system's reliability and performance. Anomaly detection plays an indispensable role in maintaining system health, reducing downtime, and ensuring an optimal user experience.

### Alerts fatigue
Alert fatigue is the exhaustion and desensitization that can occur when system administrators, engineers, or operations teams are overwhelmed by a high volume of alerts, many of which may be unimportant, false, or redundant.

This constant stream of information can result in critical alerts being overlooked or disregarded, leading to delayed response times and potentially serious system issues going unnoticed. 

Alert fatigue is not just a productivity issue—it can also have significant implications for system reliability and performance.

To mitigate alert fatigue, Observability Insights must implement intelligent alerting systems that prioritize alerts based on their severity, relevance, and potential impact on the system.

This includes tuning alert thresholds, grouping related alerts, and incorporating anomaly detection and machine learning to improve the accuracy and relevance of alerts.

---

## Observability Workflow
This part will show how users can use OpenSearch Observability plugin to build an Observability monitoring solution and use it to further investigate and diagnose
Alerts and incidents in the system.

### Introduction of the Observability tools
This section will give an overview description with short sample on how to use the Observability tools and API 
   1) PPL Queries
   2) Saved search templates
   3) Correlation build-in queries
   4) Alerts and monitor KPI
   5) Logs analytics
   6) Trace analytics
   7) Metrics analytics
   8) Service maps / graph

### Collecting telemetry signals using different providers
This section will show how to setup and configure the different ingestion capabilities users have to submit Observability signals into OpenSearch.
   1) Data-prepper - Traces / Metrics
   2) Jaeger - Traces
   3) Fluent-bit - Logs

### How do we map OTEL Demo application topology 

This section will define the application services & infrastructure KPI / SLA to monitor
   1) Services break-down and prioritization according to impact analysis - **using graph centrality calculation**
   2) Defining the monitoring channels and alerts
   3) SLO / SLA definitions including burn-rate. 
   4) Dashboards Creation for selected services (RED strategy)
   5) Main health dashboard definition
   6) Sampling data for 'health' baseline creation

