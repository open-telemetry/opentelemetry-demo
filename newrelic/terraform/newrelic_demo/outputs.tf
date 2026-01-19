output "checkout_service_guid" {
  description = "The GUID of the checkout service entity"
  value       = data.newrelic_entity.checkout_service.guid
}

output "checkout_service_name" {
  description = "The name of the checkout service entity"
  value       = data.newrelic_entity.checkout_service.name
}

output "slo_id" {
  description = "The ID of the created SLO"
  value       = newrelic_service_level.checkout_slo.sli_id
}

output "slo_name" {
  description = "The name of the created SLO"
  value       = newrelic_service_level.checkout_slo.name
}
