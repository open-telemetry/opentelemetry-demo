# Look up the checkout service entity
data "newrelic_entity" "checkout_service" {
  name   = var.checkout_service_name
  type   = "SERVICE"
  domain = "EXT"

  tag {
    key   = "accountId"
    value = var.account_id
  }
}

# Create SLO for the checkout service
resource "newrelic_service_level" "checkout_slo" {
  guid        = data.newrelic_entity.checkout_service.guid
  name        = "Checkout Service Availability"
  description = "Availability SLO for the checkout service in the OpenTelemetry Demo"

  events {
    account_id = var.account_id
    valid_events {
      from  = "Span"
      where = "entity.guid = '${data.newrelic_entity.checkout_service.guid}' AND span.kind = 'server'"
    }

    bad_events {
      from  = "Span"
      where = "entity.guid = '${data.newrelic_entity.checkout_service.guid}' AND span.kind = 'server' AND otel.status_code = 'ERROR'"
    }
  }

  objective {
    target = 99.5
    time_window {
      rolling {
        count = 1
        unit  = "DAY"
      }
    }
  }
}
