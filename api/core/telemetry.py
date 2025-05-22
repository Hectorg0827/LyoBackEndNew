"""
OpenTelemetry setup module.

This module provides functionality to set up OpenTelemetry for tracing and metrics.
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from fastapi import FastAPI, Request
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from api.core.config import settings

logger = logging.getLogger(__name__)


# Create metrics for AI performance tracking
meter = metrics.get_meter("lyo.ai")
model_inference_time = meter.create_histogram(
    name="ai.model.inference.time",
    description="Time taken for AI model inference",
    unit="ms",
)

recommendation_quality = meter.create_histogram(
    name="ai.recommendation.quality",
    description="Quality score of recommendations",
    unit="score",
)

engagement_counter = meter.create_counter(
    name="user.engagement",
    description="User engagement with content",
)

error_counter = meter.create_counter(
    name="ai.errors",
    description="AI component errors",
)


def register_error_monitoring(app: FastAPI, error_classes: List[Type[Exception]]) -> None:
    """
    Register error monitoring for specific error types.
    
    Args:
        app: FastAPI application
        error_classes: List of exception classes to monitor
    """
    for error_class in error_classes:
        # Store the original exception handler
        original_handler = app.exception_handlers.get(error_class)
        
        # Define a new handler that tracks metrics then calls the original handler
        async def error_tracking_handler(request: Request, exc: Exception):
            # Get error details
            error_type = exc.__class__.__name__
            error_code = getattr(exc, "code", "unknown")
            
            # Track error in metrics
            error_counter.add(
                1,
                {
                    "error_type": error_type,
                    "error_code": error_code,
                    "path": request.url.path,
                }
            )
            
            # Log error with tracing context
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(f"ai_error_{error_type}"):
                span = trace.get_current_span()
                span.set_attribute("error.type", error_type)
                span.set_attribute("error.message", str(exc))
                
                if hasattr(exc, "data") and exc.data:
                    span.set_attribute("error.context", str(exc.data))
                    
                span.record_exception(exc)
                
                # Call original handler if it exists
                if original_handler:
                    return await original_handler(request, exc)
                else:
                    # Fallback to default error handling in FastAPI
                    raise exc
                
        # Register the new handler
        app.add_exception_handler(error_class, error_tracking_handler)
        logger.info(f"Registered error monitoring for {error_class.__name__}")


def setup_telemetry() -> None:
    """
    Set up OpenTelemetry for tracing and metrics.
    
    This function configures OpenTelemetry to export traces and metrics
    to the configured OTLP endpoint.
    """
    if not settings.OTLP_ENDPOINT:
        logger.warning("OTLP_ENDPOINT not set. Skipping OpenTelemetry setup.")
        return
    
    try:
        # Create a resource with service information
        resource = Resource.create(
            {
                "service.name": settings.APP_NAME,
                "service.version": "1.0.0",
                "environment": settings.ENVIRONMENT,
            }
        )
        
        # Set up trace provider
        trace_provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTLP_ENDPOINT, insecure=True)
        trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Set the trace provider as the global provider
        trace.set_tracer_provider(trace_provider)
        
        # Initialize FastAPI instrumentation
        # Note: This will be called after FastAPI app is created
        logger.info("OpenTelemetry setup complete")
    except Exception as e:
        logger.exception(f"Failed to set up OpenTelemetry: {e}")


def instrument_fastapi(app) -> None:
    """
    Instrument a FastAPI application with OpenTelemetry.
    
    Args:
        app: The FastAPI application to instrument
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation complete")
    except Exception as e:
        logger.exception(f"Failed to instrument FastAPI: {e}")
