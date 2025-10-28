import grpc
from grpc import StatusCode
from grpc.aio import insecure_channel
from opentelemetry import trace
from retrying import retry

tracer = trace.get_tracer(__name__)

class RecommendationService:
    def __init__(self, flagd_addr):
        self.flagd_addr = flagd_addr
        self.channel = None
        self.stub = None
        self.connect_with_retry()

    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000)
    def connect_with_retry(self):
        try:
            self.channel = insecure_channel(self.flagd_addr)
            self.stub = FlagServiceStub(self.channel)
        except Exception as e:
            logger.error(f"Failed to connect to flagd: {e}")
            raise

    async def resolve_boolean(self, flag_key, default_value=False):
        try:
            with tracer.start_as_current_span("/flagd.evaluation.v1.Service/ResolveBoolean") as span:
                span.set_attribute("flag.key", flag_key)
                
                if not self.channel or self.channel.get_state() in [
                    grpc.ChannelConnectivity.SHUTDOWN,
                    grpc.ChannelConnectivity.TRANSIENT_FAILURE
                ]:
                    await self.connect_with_retry()

                request = ResolveBooleanRequest(flag_key=flag_key)
                response = await self.stub.ResolveBoolean(request, timeout=2)
                return response.value

        except grpc.RpcError as e:
            status_code = e.code()
            span.set_attribute("error", True)
            span.set_attribute("error.type", str(status_code))
            
            if status_code in [StatusCode.UNAVAILABLE, StatusCode.DEADLINE_EXCEEDED]:
                logger.warning(f"Flagd service unavailable: {e}, using default value")
                return default_value
            
            logger.error(f"Error resolving flag {flag_key}: {e}")
            return default_value

        except Exception as e:
            logger.error(f"Unexpected error resolving flag {flag_key}: {e}")
            return default_value