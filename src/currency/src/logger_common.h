// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

#include "opentelemetry/logs/provider.h"
#include "opentelemetry/sdk/logs/logger.h"
#include "opentelemetry/sdk/logs/logger_provider_factory.h"
#include "opentelemetry/sdk/logs/batch_log_record_processor_factory.h"
#include "opentelemetry/sdk/logs/logger_context_factory.h"
#include "opentelemetry/exporters/otlp/otlp_http_log_record_exporter_factory.h"

using namespace std;
namespace nostd     = opentelemetry::nostd;
namespace otlp      = opentelemetry::exporter::otlp;
namespace logs      = opentelemetry::logs;
namespace logs_sdk  = opentelemetry::sdk::logs;

namespace
{
  std::shared_ptr<logs_sdk::LoggerProvider> initLogger() {
    otlp::OtlpHttpLogRecordExporterOptions loggerOptions;
    auto exporter  = otlp::OtlpHttpLogRecordExporterFactory::Create(loggerOptions);
    auto processor = logs_sdk::BatchLogRecordProcessorFactory::Create(std::move(exporter), {});
    std::vector<std::unique_ptr<logs_sdk::LogRecordProcessor>> processors;
    processors.push_back(std::move(processor));
    auto context = logs_sdk::LoggerContextFactory::Create(std::move(processors));
    std::shared_ptr<logs_sdk::LoggerProvider> provider =
        logs_sdk::LoggerProviderFactory::Create(std::move(context));
    std::shared_ptr<logs::LoggerProvider> api_provider = provider;
    opentelemetry::logs::Provider::SetLoggerProvider(api_provider);
    return provider;
  }

  nostd::shared_ptr<opentelemetry::logs::Logger> getLogger(std::string name){
    auto provider = logs::Provider::GetLoggerProvider();
    return provider->GetLogger(name + "_logger", name, OPENTELEMETRY_SDK_VERSION);
  }
}
