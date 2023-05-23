# OpenSearch Observability Tutorial

Welcome to the OpenSearch Observability tutorials! 

This tutorial is designed to guide users in the Observability domain through the process of using the OpenSearch Observability plugin. By the end of this tutorial, you will be familiar with building dashboards, creating Pipe Processing Language (PPL) queries, federating metrics from Prometheus data sources, and conducting root cause analysis investigations on your data.

## Overview

This tutorial uses the OpenTelemetry demo application, an e-commerce application for an astronomy shop. The application includes multiple microservices, each providing different functionalities. These services are monitored and traced using the OpenTelemetry trace collector and additional agents.

The resulting traces and logs are stored in structured indices in OpenSearch indices, following the OpenTelemetry format. 

This provides a realistic environment for learning and applying Observability concepts, investigation and diagnostic patterns.

## Content

This tutorial is structured as follows:

1. **Introduction to the OTEL demo infrastructure & Architecture**: An introduction to OTEL demo architecture and services, how they are monitored, traces and collected.

2. **Introduction to OpenSearch Observability**: A brief introduction to the plugin, its features, and its advantages.

3. **Building Dashboards**: Step-by-step guide on how to create effective and informative dashboards in OpenSearch Observability.

4. **Creating PPL Queries**: Learn how to create PPL queries to extract valuable insights from your data.

5. **Federating Metrics from Prometheus**: Detailed guide on how to federate metrics from a Prometheus data source into OpenSearch Observability.

6. **Conducting Root Cause Analysis**: Learn how to use the built-in features of OpenSearch Observability to conduct a root cause analysis investigation on your data.

7. **OpenTelemetry Integration**: Learn how the OpenTelemetry demo application sends data to OpenSearch and how to navigate and understand this data in OpenSearch Observability.

This tutorial would enhance your understanding of Observability and your ability to use OpenSearch Observability to its fullest.

**_Enjoy the learning journey!_**

## Prerequisites

To get the most out of this tutorial, you should have a basic understanding of Observability, microservice architectures, and the OpenTelemetry ecosystem.

## Getting Started

To start the tutorial, navigate to the `Introduction to OpenSearch Observability` section.

Happy Learning!

---

#### 1. [OTEL Demo Architecture](OTEL Demo Architecture.md) 

#### 2. [Observability Introduction](Observability Introduction.md) 

#### 3. [Memory Leak Investigation Tutorial](Memory Leak Tutorial.md) 


---
## References

[Cloud Native OpenTelemetry community you-tube lecture](https://www.youtube.com/watch?v=kD0EAjly9jc)