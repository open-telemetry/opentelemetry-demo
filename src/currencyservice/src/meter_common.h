//Add dependencies
#include "opentelemetry/exporters/otlp/otlp_grpc_metric_exporter_factory.h"
#include "opentelemetry/metrics/provider.h"
#include "opentelemetry/sdk/metrics/aggregation/default_aggregation.h"
#include "opentelemetry/sdk/metrics/export/periodic_exporting_metric_reader.h"
#include "opentelemetry/sdk/metrics/meter.h"
#include "opentelemetry/sdk/metrics/meter_provider.h"

//namespaces
namespace metric_sdk    = opentelemetry::sdk::metrics;
namespace common        = opentelemetry::common;
namespace metrics_api   = opentelemetry::metrics;
namespace otlp_exporter = opentelemetry::exporter::otlp;

namespace
{

	void initMeter() {
		std::string version{"0.1.0"};
		std::string name{"otel"};
		std::string schema{"https://opentelemetry.io/schemas/1.2.0"};

		//Build MetricExporter
		otlp_exporter::OtlpGrpcMetricExporterOptions otlpOptions;
		otlpOptions.endpoint = "otelcol:4317";
		otlpOptions.aggregation_temporality = metric_sdk::AggregationTemporality::kDelta;
		auto exporter = otlp_exporter::OtlpGrpcMetricExporterFactory::Create(otlpOptions);

		//Build MeterProvider and Reader
		metric_sdk::PeriodicExportingMetricReaderOptions options;
		options.export_interval_millis = std::chrono::milliseconds(1000);
		options.export_timeout_millis = std::chrono::milliseconds(500);
		std::unique_ptr<metric_sdk::MetricReader> reader{
			new metric_sdk::PeriodicExportingMetricReader(std::move(exporter), options) };
		auto provider = std::shared_ptr<metrics_api::MeterProvider>(new metric_sdk::MeterProvider());
		auto p = std::static_pointer_cast<metric_sdk::MeterProvider>(provider);
		p->AddMetricReader(std::move(reader));
		metrics_api::Provider::SetMeterProvider(provider);

		//TODO Set global??
		//Build Meter for Counter
		std::string counter_name = name + "_counter";
		std::unique_ptr<metric_sdk::InstrumentSelector> instrument_selector{
			new metric_sdk::InstrumentSelector(metric_sdk::InstrumentType::kCounter, counter_name) };
		std::unique_ptr<metric_sdk::MeterSelector> meter_selector{
			new metric_sdk::MeterSelector(name, version, schema) };
		std::unique_ptr<metric_sdk::View> sum_view{
			new metric_sdk::View{name, "description", metric_sdk::AggregationType::kSum} };
		p->AddView(std::move(instrument_selector), std::move(meter_selector), std::move(sum_view));

		//Build instrument
		auto meter = provider->GetMeter(name, "0.0.0");
		auto double_counter = meter->CreateDoubleCounter(counter_name);
		// Create a label set which annotates metric values
		std::map<std::string, std::string> labels = { {"key", "value"} };
		auto labelkv = common::KeyValueIterableView<decltype(labels)>{ labels };
		double_counter->Add(1.0, labelkv);

	}
}