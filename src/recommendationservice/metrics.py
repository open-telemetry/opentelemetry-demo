#!/usr/bin/python

from gc import callbacks
from typing import Iterable
import psutil

from opentelemetry.metrics import (
    CallbackOptions,
    Observation,
)

# RAM usage
def ram_usage_callback(options: CallbackOptions) -> Iterable[Observation]:
    observations = []    
    ram_percent = psutil.virtual_memory().percent
    print(f"ram_percent: {ram_percent}")
    labels = {"dimension": "value"}
    observations.append(Observation(ram_percent, labels))
    
    return observations

# CPU Time callback
def cpu_time_callback(options: CallbackOptions) -> Iterable[Observation]:
    observations = []
    with open("/proc/stat") as procstat:
        procstat.readline()  # skip the first line
        for line in procstat:
            if not line.startswith("cpu"): break
            cpu, *states = line.split()
            observations.append(Observation(int(states[0]) // 100, {"cpu": cpu, "state": "user"}))
            observations.append(Observation(int(states[1]) // 100, {"cpu": cpu, "state": "nice"}))
            observations.append(Observation(int(states[2]) // 100, {"cpu": cpu, "state": "system"}))
            # ... other states
    return observations

# CPU usage
def cpu_usage_callback(options: CallbackOptions) -> Iterable[Observation]:
    observations = []    
    for (number, percent) in enumerate(psutil.cpu_percent(percpu=True)):
        print(f"cpu_number: {number}, cpu_percent: {percent}")
        labels = {"cpu_number": str(number)}
        observations.append(Observation(percent, labels))
        
    return observations
        
def observable_counter_callback(options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(1, {})


def observable_up_down_counter_callback(
    options: CallbackOptions,
) -> Iterable[Observation]:
    yield Observation(-10, {})


def observable_gauge_callback(options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(9, {})


def init_metrics(meter):

    # Requests counter
    list_recommendations_request_counter = meter.create_counter(
        name="app.recommendations.request.counter",
        description="number of requests to RecommendationService.ListRecommendations",
        unit="requests"
    )

    # Recommendations counter
    app_recommendations_counter = meter.create_counter(
        'app.recommendations.counter', unit='recommendations', description="Counts the total number of given recommendations"
    )

    # CPU usage
    cpu_usage = meter.create_observable_counter(
        "cpu_usage",
        callbacks=[cpu_usage_callback],
        unit="%",
        description="CPU usage"
    )

    # RAM usage
    ram_usage = meter.create_observable_up_down_counter(
        "ram_usage",
        callbacks=[ram_usage_callback],
        unit="1",
        description="RAM usage"        
    )
    
    attributes = {"application.name": "otel-demo"}
    
    rec_svc_metrics = {
        "list_recommendations_request_counter": list_recommendations_request_counter,
        "attributes": attributes,
        "app_recommendations_counter": app_recommendations_counter,
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage
    }
    
    return rec_svc_metrics
