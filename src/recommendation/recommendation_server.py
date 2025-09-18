#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
import random
import time
import psutil
import sys
from concurrent import futures

# Pip
import grpc
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

from openfeature.contrib.hook.opentelemetry import TracingHook

# Local
import logging
import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

from metrics import (
    init_metrics
)

cached_ids = []
first_run = True

# Cache performance tracking
cache_stats = {
    'hits': 0,
    'misses': 0,
    'total_requests': 0,
    'cache_size_history': [],
    'memory_usage_history': [],
    'last_cleanup_time': time.time(),
    'growth_rate': 0.0,
    'performance_degradation_count': 0
}

class RecommendationService(demo_pb2_grpc.RecommendationServiceServicer):
    def __init__(self):
        self.last_health_check = time.time()
        self.request_count = 0
    
    def ListRecommendations(self, request, context):
        start_time = time.time()
        self.request_count += 1
        
        try:
            prod_list = get_product_list(request.product_ids)
            span = trace.get_current_span()
            span.set_attribute("app.products_recommended.count", len(prod_list))
            
            # Enhanced logging with performance metrics
            processing_time = time.time() - start_time
            trace_context = get_trace_context()
            system_metrics = get_system_metrics()
            
            logger.info(f"ListRecommendations completed successfully", extra={
                'operation': 'list_recommendations',
                'request_id': f"req_{self.request_count}",
                'input_product_count': len(request.product_ids),
                'recommended_product_count': len(prod_list),
                'processing_time_ms': round(processing_time * 1000, 2),
                'cache_enabled': check_feature_flag("recommendationCacheFailure"),
                'system_metrics': system_metrics,
                'trace_context': trace_context,
                'service': 'recommendation-service'
            })

            # build and return response
            response = demo_pb2.ListRecommendationsResponse()
            response.product_ids.extend(prod_list)

            # Collect metrics for this service
            rec_svc_metrics["app_recommendations_counter"].add(len(prod_list), {'recommendation.type': 'catalog'})
            
            # Periodic health monitoring
            self._perform_periodic_health_check()

            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            trace_context = get_trace_context()
            system_metrics = get_system_metrics()
            
            logger.error(f"ListRecommendations failed", extra={
                'operation': 'list_recommendations',
                'request_id': f"req_{self.request_count}",
                'error_type': type(e).__name__,
                'error_message': str(e),
                'error_stack': str(e.__traceback__) if hasattr(e, '__traceback__') else 'unavailable',
                'processing_time_ms': round(processing_time * 1000, 2),
                'input_product_count': len(request.product_ids),
                'system_metrics': system_metrics,
                'trace_context': trace_context,
                'cache_state': {
                    'size': len(cached_ids),
                    'enabled': check_feature_flag("recommendationCacheFailure")
                },
                'service': 'recommendation-service'
            })
            raise e
    
    def _perform_periodic_health_check(self):
        """Perform periodic health checks and resource monitoring"""
        current_time = time.time()
        
        # Perform health check every 30 seconds or every 10 requests
        if (current_time - self.last_health_check > 30 or 
            self.request_count % 10 == 0):
            
            self.last_health_check = current_time
            
            # Check for memory leaks
            memory_leak_data = detect_memory_leak()
            if memory_leak_data and memory_leak_data['leak_score'] >= 2:
                trace_context = get_trace_context()
                system_metrics = get_system_metrics()
                
                logger.warning("Periodic health check: Memory leak indicators detected", extra={
                    'health_check': True,
                    'memory_leak_analysis': memory_leak_data,
                    'cache_size': len(cached_ids),
                    'request_count': self.request_count,
                    'system_metrics': system_metrics,
                    'trace_context': trace_context,
                    'service': 'recommendation-service',
                    'operation': 'health_check'
                })
            
            # Check for performance degradation
            performance_data = detect_performance_degradation()
            if performance_data and performance_data['degradation_score'] >= 2:
                trace_context = get_trace_context()
                system_metrics = get_system_metrics()
                
                logger.warning("Periodic health check: Performance degradation detected", extra={
                    'health_check': True,
                    'performance_analysis': performance_data,
                    'cache_size': len(cached_ids),
                    'request_count': self.request_count,
                    'system_metrics': system_metrics,
                    'trace_context': trace_context,
                    'service': 'recommendation-service',
                    'operation': 'health_check'
                })

    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING)

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)


def get_trace_context():
    """Get current OpenTelemetry trace context"""
    current_span = trace.get_current_span()
    span_context = current_span.get_span_context()
    
    return {
        'traceId': trace.format_trace_id(span_context.trace_id),
        'spanId': trace.format_span_id(span_context.span_id),
        'traceFlags': span_context.trace_flags,
        'isValid': span_context.is_valid
    }

def get_system_metrics():
    """Get comprehensive system resource metrics including performance data"""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        cpu_times = process.cpu_times()
        io_counters = process.io_counters() if hasattr(process, 'io_counters') else None
        
        # Get system-wide metrics
        system_memory = psutil.virtual_memory()
        system_cpu = psutil.cpu_percent(interval=None)
        
        return {
            'memory': {
                'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
                'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
                'percent': round(process.memory_percent(), 2),
                'shared_mb': round(getattr(memory_info, 'shared', 0) / 1024 / 1024, 2),
                'system_available_mb': round(system_memory.available / 1024 / 1024, 2),
                'system_used_percent': round(system_memory.percent, 2)
            },
            'cpu': {
                'percent': round(cpu_percent, 2),
                'num_threads': process.num_threads(),
                'user_time': round(cpu_times.user, 2),
                'system_time': round(cpu_times.system, 2),
                'system_cpu_percent': round(system_cpu, 2)
            },
            'io': {
                'read_count': io_counters.read_count if io_counters else 0,
                'write_count': io_counters.write_count if io_counters else 0,
                'read_bytes': io_counters.read_bytes if io_counters else 0,
                'write_bytes': io_counters.write_bytes if io_counters else 0
            },
            'process': {
                'uptime_seconds': round(time.time() - process.create_time(), 2),
                'pid': process.pid,
                'status': process.status(),
                'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0
            },
            'performance': {
                'context_switches_voluntary': getattr(process, 'num_ctx_switches', lambda: (0, 0))().voluntary,
                'context_switches_involuntary': getattr(process, 'num_ctx_switches', lambda: (0, 0))().involuntary,
                'page_faults_major': getattr(process.memory_full_info() if hasattr(process, 'memory_full_info') else memory_info, 'pfaults', 0),
                'page_faults_minor': getattr(process.memory_full_info() if hasattr(process, 'memory_full_info') else memory_info, 'pageins', 0)
            },
            'timestamp': time.time()
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {
            'memory': {'rss_mb': 0, 'vms_mb': 0, 'percent': 0, 'shared_mb': 0, 'system_available_mb': 0, 'system_used_percent': 0},
            'cpu': {'percent': 0, 'num_threads': 0, 'user_time': 0, 'system_time': 0, 'system_cpu_percent': 0},
            'io': {'read_count': 0, 'write_count': 0, 'read_bytes': 0, 'write_bytes': 0},
            'process': {'uptime_seconds': 0, 'pid': 0, 'status': 'unknown', 'num_fds': 0},
            'performance': {'context_switches_voluntary': 0, 'context_switches_involuntary': 0, 'page_faults_major': 0, 'page_faults_minor': 0},
            'timestamp': time.time()
        }

def calculate_cache_growth_rate():
    """Calculate cache growth rate based on size history"""
    global cache_stats
    if len(cache_stats['cache_size_history']) < 2:
        return 0.0
    
    recent_sizes = cache_stats['cache_size_history'][-10:]  # Last 10 measurements
    if len(recent_sizes) < 2:
        return 0.0
    
    # Calculate average growth per measurement
    total_growth = recent_sizes[-1] - recent_sizes[0]
    measurements = len(recent_sizes) - 1
    return total_growth / measurements if measurements > 0 else 0.0

def detect_memory_leak():
    """Detect potential memory leaks based on usage patterns"""
    global cache_stats
    
    if len(cache_stats['memory_usage_history']) < 10:
        return None
    
    recent_memory = cache_stats['memory_usage_history'][-10:]
    
    # Check for consistent memory growth
    growth_trend = sum(1 for i in range(len(recent_memory)-1) if recent_memory[i+1] > recent_memory[i])
    growth_percentage = growth_trend / (len(recent_memory) - 1)
    
    # Calculate memory growth rate
    memory_growth_rate = (recent_memory[-1] - recent_memory[0]) / len(recent_memory)
    
    leak_indicators = {
        'consistent_growth': growth_percentage > 0.7,  # 70% of measurements show growth
        'rapid_growth': memory_growth_rate > 5.0,  # More than 5MB growth per measurement
        'high_memory_usage': recent_memory[-1] > 500,  # More than 500MB
        'cache_size_correlation': len(cached_ids) > 1000 and recent_memory[-1] > 100
    }
    
    leak_score = sum(leak_indicators.values())
    
    return {
        'leak_score': leak_score,
        'leak_indicators': leak_indicators,
        'memory_growth_rate_mb': round(memory_growth_rate, 2),
        'growth_trend_percentage': round(growth_percentage * 100, 1),
        'current_memory_mb': round(recent_memory[-1], 2),
        'memory_increase_mb': round(recent_memory[-1] - recent_memory[0], 2)
    }

def detect_performance_degradation():
    """Detect performance degradation patterns"""
    global cache_stats
    
    current_time = time.time()
    
    # Calculate cache efficiency metrics
    total_requests = cache_stats['total_requests']
    if total_requests == 0:
        return None
    
    hit_rate = cache_stats['hits'] / total_requests
    cache_size = len(cached_ids)
    
    # Performance degradation indicators
    degradation_indicators = {
        'low_hit_rate': hit_rate < 0.3,  # Less than 30% hit rate
        'oversized_cache': cache_size > 2000,  # Cache too large
        'excessive_growth': cache_stats['growth_rate'] > 20,  # Rapid growth
        'memory_pressure': len(cache_stats['memory_usage_history']) > 0 and cache_stats['memory_usage_history'][-1] > 300
    }
    
    degradation_score = sum(degradation_indicators.values())
    
    return {
        'degradation_score': degradation_score,
        'degradation_indicators': degradation_indicators,
        'hit_rate': round(hit_rate, 3),
        'cache_size': cache_size,
        'growth_rate': round(cache_stats['growth_rate'], 2),
        'efficiency_ratio': round(hit_rate / max(cache_size / 100, 1), 3)  # Hits per 100 cache items
    }

def log_resource_exhaustion_warning():
    """Log detailed resource exhaustion warnings"""
    trace_context = get_trace_context()
    system_metrics = get_system_metrics()
    memory_leak_data = detect_memory_leak()
    performance_data = detect_performance_degradation()
    
    exhaustion_data = {
        'resource_exhaustion_event': True,
        'timestamp': time.time(),
        'system_metrics': system_metrics,
        'trace_context': trace_context,
        'cache_state': {
            'size': len(cached_ids),
            'unique_items': len(set(cached_ids)),
            'duplicate_ratio': round((len(cached_ids) - len(set(cached_ids))) / max(len(cached_ids), 1), 3),
            'memory_per_item_mb': round(system_metrics['memory']['rss_mb'] / max(len(cached_ids), 1), 3)
        },
        'performance_impact': performance_data,
        'memory_leak_analysis': memory_leak_data,
        'service': 'recommendation-service',
        'operation': 'resource_exhaustion_detection'
    }
    
    logger.warning("Resource exhaustion detected in recommendation service", extra=exhaustion_data)
    
    return exhaustion_data

def log_cache_operation(operation_type, cache_hit=None, cache_size=None, error=None, operation_start_time=None):
    """Log detailed cache operation with performance metrics"""
    global cache_stats
    
    trace_context = get_trace_context()
    system_metrics = get_system_metrics()
    current_time = time.time()
    
    # Calculate operation duration if start time provided
    operation_duration = None
    if operation_start_time:
        operation_duration = round((current_time - operation_start_time) * 1000, 2)  # Convert to milliseconds
    
    # Update cache statistics
    cache_stats['total_requests'] += 1
    if cache_hit is not None:
        if cache_hit:
            cache_stats['hits'] += 1
        else:
            cache_stats['misses'] += 1
    
    if cache_size is not None:
        cache_stats['cache_size_history'].append(cache_size)
        # Keep only last 50 measurements
        if len(cache_stats['cache_size_history']) > 50:
            cache_stats['cache_size_history'] = cache_stats['cache_size_history'][-50:]
    
    # Track memory usage history
    cache_stats['memory_usage_history'].append(system_metrics['memory']['rss_mb'])
    if len(cache_stats['memory_usage_history']) > 50:
        cache_stats['memory_usage_history'] = cache_stats['memory_usage_history'][-50:]
    
    # Calculate performance metrics
    hit_rate = cache_stats['hits'] / cache_stats['total_requests'] if cache_stats['total_requests'] > 0 else 0
    miss_rate = cache_stats['misses'] / cache_stats['total_requests'] if cache_stats['total_requests'] > 0 else 0
    cache_stats['growth_rate'] = calculate_cache_growth_rate()
    
    # Detect performance degradation
    if len(cache_stats['memory_usage_history']) >= 5:
        recent_memory = cache_stats['memory_usage_history'][-5:]
        if all(recent_memory[i] < recent_memory[i+1] for i in range(len(recent_memory)-1)):
            cache_stats['performance_degradation_count'] += 1
    
    log_data = {
        'operation': operation_type,
        'cache_metrics': {
            'hit_rate': round(hit_rate, 3),
            'miss_rate': round(miss_rate, 3),
            'total_hits': cache_stats['hits'],
            'total_misses': cache_stats['misses'],
            'total_requests': cache_stats['total_requests'],
            'current_size': cache_size or len(cached_ids),
            'growth_rate': round(cache_stats['growth_rate'], 3),
            'performance_degradation_events': cache_stats['performance_degradation_count']
        },
        'performance': {
            'operation_duration_ms': operation_duration,
            'throughput': 'normal' if operation_duration and operation_duration < 100 else 'degraded',
            'latency_category': 'low' if operation_duration and operation_duration < 50 else 'elevated'
        },
        'system_metrics': system_metrics,
        'trace_context': trace_context,
        'cache_efficiency': {
            'memory_per_item': round(system_metrics['memory']['rss_mb'] / max(len(cached_ids), 1), 3),
            'cache_utilization': 'high' if len(cached_ids) > 1000 else 'normal',
            'io_efficiency': round(system_metrics['io']['read_count'] / max(cache_stats['total_requests'], 1), 3)
        },
        'service': 'recommendation-service'
    }
    
    # Add memory leak detection to log data
    memory_leak_data = detect_memory_leak()
    if memory_leak_data:
        log_data['memory_leak_analysis'] = memory_leak_data
    
    # Add performance degradation detection
    performance_data = detect_performance_degradation()
    if performance_data:
        log_data['performance_analysis'] = performance_data
    
    # Determine log level and message based on conditions
    if error:
        log_data['error'] = error
        logger.error(f"Cache operation failed", extra=log_data)
    elif memory_leak_data and memory_leak_data['leak_score'] >= 3:
        logger.warning(f"Memory leak detected during {operation_type}", extra=log_data)
    elif performance_data and performance_data['degradation_score'] >= 3:
        logger.warning(f"Performance degradation detected during {operation_type}", extra=log_data)
    elif operation_type == 'cache_hit':
        logger.info(f"Cache hit - efficient retrieval", extra=log_data)
    elif operation_type == 'cache_miss':
        logger.info(f"Cache miss - fetching from catalog", extra=log_data)
    elif operation_type == 'cache_expansion':
        if cache_stats['growth_rate'] > 10:  # Rapid growth threshold
            logger.warning(f"Rapid cache expansion detected", extra=log_data)
        else:
            logger.info(f"Cache expanded with new products", extra=log_data)
    
    # Check for resource exhaustion conditions
    if (memory_leak_data and memory_leak_data['leak_score'] >= 2 and 
        performance_data and performance_data['degradation_score'] >= 2):
        log_resource_exhaustion_warning()

def get_product_list(request_product_ids):
    global first_run
    global cached_ids
    with tracer.start_as_current_span("get_product_list") as span:
        max_responses = 5

        # Formulate the list of characters to list of strings
        request_product_ids_str = ''.join(request_product_ids)
        request_product_ids = request_product_ids_str.split(',')

        # Feature flag scenario - Cache Leak with enhanced logging
        if check_feature_flag("recommendationCacheFailure"):
            span.set_attribute("app.recommendation.cache_enabled", True)
            
            # Simulate cache behavior with detailed logging
            if random.random() < 0.5 or first_run:
                # Cache miss scenario
                cache_operation_start = time.time()
                first_run = False
                span.set_attribute("app.cache_hit", False)
                
                try:
                    # Log cache miss with current state
                    log_cache_operation("cache_miss", cache_hit=False, cache_size=len(cached_ids), operation_start_time=cache_operation_start)
                    
                    # Fetch from product catalog
                    cat_response = product_catalog_stub.ListProducts(demo_pb2.Empty())
                    response_ids = [x.id for x in cat_response.products]
                    
                    # Simulate cache leak by duplicating entries
                    old_cache_size = len(cached_ids)
                    cached_ids = cached_ids + response_ids
                    cached_ids = cached_ids + cached_ids[:len(cached_ids) // 4]  # Add 25% more duplicates
                    
                    # Log cache expansion with growth details
                    new_cache_size = len(cached_ids)
                    expansion_ratio = new_cache_size / max(old_cache_size, 1)
                    
                    log_cache_operation("cache_expansion", cache_size=new_cache_size, operation_start_time=cache_operation_start)
                    
                    # Log potential memory leak warning and attempt cleanup
                    if new_cache_size > 1000:  # Threshold for concern
                        trace_context = get_trace_context()
                        system_metrics = get_system_metrics()
                        
                        logger.warning(f"Cache size exceeding normal limits", extra={
                            'cache_size': new_cache_size,
                            'expansion_ratio': round(expansion_ratio, 2),
                            'duplicate_entries': new_cache_size - len(set(cached_ids)),
                            'memory_leak_indicator': True,
                            'system_metrics': system_metrics,
                            'trace_context': trace_context,
                            'service': 'recommendation-service',
                            'operation': 'cache_expansion_warning'
                        })
                        
                        # Simulate cache cleanup attempt
                        if new_cache_size > 2000:  # Critical threshold
                            try:
                                old_size = len(cached_ids)
                                # Remove duplicates to simulate cleanup
                                cached_ids = list(set(cached_ids))
                                cleaned_size = len(cached_ids)
                                
                                trace_context = get_trace_context()
                                system_metrics_after = get_system_metrics()
                                
                                logger.info(f"Emergency cache cleanup performed", extra={
                                    'cache_cleanup': True,
                                    'old_size': old_size,
                                    'cleaned_size': cleaned_size,
                                    'items_removed': old_size - cleaned_size,
                                    'cleanup_efficiency': round((old_size - cleaned_size) / old_size, 3),
                                    'system_metrics_after_cleanup': system_metrics_after,
                                    'trace_context': trace_context,
                                    'service': 'recommendation-service',
                                    'operation': 'emergency_cache_cleanup'
                                })
                                
                            except Exception as cleanup_error:
                                trace_context = get_trace_context()
                                system_metrics = get_system_metrics()
                                
                                logger.error(f"Cache cleanup failed", extra={
                                    'cache_cleanup_error': True,
                                    'error_type': type(cleanup_error).__name__,
                                    'error_message': str(cleanup_error),
                                    'error_stack': str(cleanup_error.__traceback__) if hasattr(cleanup_error, '__traceback__') else 'unavailable',
                                    'cache_size': len(cached_ids),
                                    'system_metrics': system_metrics,
                                    'trace_context': trace_context,
                                    'service': 'recommendation-service',
                                    'operation': 'cache_cleanup_error'
                                })
                    
                    product_ids = cached_ids
                    
                except Exception as e:
                    # Log cache operation failure
                    error_details = {
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'cache_state': {
                            'size': len(cached_ids),
                            'first_run': first_run
                        }
                    }
                    log_cache_operation("cache_miss", cache_hit=False, error=error_details, operation_start_time=cache_operation_start)
                    raise e
                    
            else:
                # Cache hit scenario
                cache_operation_start = time.time()
                span.set_attribute("app.cache_hit", True)
                
                # Log successful cache hit with performance metrics
                log_cache_operation("cache_hit", cache_hit=True, cache_size=len(cached_ids), operation_start_time=cache_operation_start)
                
                product_ids = cached_ids
                
        else:
            # Normal operation without cache
            span.set_attribute("app.recommendation.cache_enabled", False)
            
            try:
                cat_response = product_catalog_stub.ListProducts(demo_pb2.Empty())
                product_ids = [x.id for x in cat_response.products]
                
                # Log normal operation
                trace_context = get_trace_context()
                system_metrics = get_system_metrics()
                
                logger.info("Product list retrieved directly from catalog", extra={
                    'operation': 'direct_catalog_fetch',
                    'product_count': len(product_ids),
                    'cache_enabled': False,
                    'system_metrics': system_metrics,
                    'trace_context': trace_context,
                    'service': 'recommendation-service'
                })
                
            except Exception as e:
                trace_context = get_trace_context()
                system_metrics = get_system_metrics()
                
                logger.error(f"Failed to fetch products from catalog", extra={
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'error_stack': str(e.__traceback__) if hasattr(e, '__traceback__') else 'unavailable',
                    'operation': 'direct_catalog_fetch',
                    'system_metrics': system_metrics,
                    'trace_context': trace_context,
                    'service': 'recommendation-service'
                })
                raise e

        span.set_attribute("app.products.count", len(product_ids))

        # Create a filtered list of products excluding the products received as input
        filtered_products = list(set(product_ids) - set(request_product_ids))
        num_products = len(filtered_products)
        span.set_attribute("app.filtered_products.count", num_products)
        num_return = min(max_responses, num_products)

        # Sample list of indicies to return
        indices = random.sample(range(num_products), num_return)
        # Fetch product ids from indices
        prod_list = [filtered_products[i] for i in indices]

        span.set_attribute("app.filtered_products.list", prod_list)

        return prod_list


def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value


def check_feature_flag(flag_name: str):
    # Initialize OpenFeature
    client = api.get_client()
    return client.get_boolean_value("recommendationCacheFailure", False)


if __name__ == "__main__":
    service_name = must_map_env('OTEL_SERVICE_NAME')
    api.set_provider(FlagdProvider(host=os.environ.get('FLAGD_HOST', 'flagd'), port=os.environ.get('FLAGD_PORT', 8013)))
    api.add_hooks([TracingHook()])

    # Initialize Traces and Metrics
    tracer = trace.get_tracer_provider().get_tracer(service_name)
    meter = metrics.get_meter_provider().get_meter(service_name)
    rec_svc_metrics = init_metrics(meter)

    # Initialize Logs
    logger_provider = LoggerProvider(
        resource=Resource.create(
            {
                'service.name': service_name,
            }
        ),
    )
    set_logger_provider(logger_provider)
    log_exporter = OTLPLogExporter(insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

    # Attach OTLP handler to logger
    logger = logging.getLogger('main')
    logger.addHandler(handler)

    catalog_addr = must_map_env('PRODUCT_CATALOG_ADDR')
    pc_channel = grpc.insecure_channel(catalog_addr)
    product_catalog_stub = demo_pb2_grpc.ProductCatalogServiceStub(pc_channel)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add class to gRPC server
    service = RecommendationService()
    demo_pb2_grpc.add_RecommendationServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)

    # Start server
    port = must_map_env('RECOMMENDATION_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Recommendation service started, listening on port {port}')
    server.wait_for_termination()
