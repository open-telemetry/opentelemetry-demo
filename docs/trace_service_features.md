# Trace Feature Coverage by Service

Emoji Legend

- Completed: :100:
- Not Applicable: :no_bell:
- Not Present (Yet): :construction:

| Service            | Language        | Instrumentation Libraries | Manual Span Creation | Span Data Enrichment | RPC Context Propagation | Span Links     | Baggage        | Resource Detection |
|--------------------|-----------------|---------------------------|----------------------|----------------------|-------------------------|----------------|----------------|--------------------|
| Accounting Service | Go              | :construction:            | :construction:       | :construction:       | :construction:          | :construction: | :construction: | :100:              |
| Ad                 | Java            | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Cart               | .NET            | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :100:              |
| Checkout           | Go              | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :100:              |
| Currency           | C++             | :no_bell:                 | :100:                | :100:                | :100:                   | :no_bell:      | :no_bell:      | :construction:     |
| Email              | Ruby            | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Feature Flag       | Erlang / Elixir | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Fraud Detection    | Kotlin          | :100:                     | :construction:       | :construction:       | :construction:          | :construction: | :construction: | :construction:     |
| Frontend           | JavaScript      | :100:                     | :100:                | :100:                | :no_bell:               | :100:          | :100:          | :100:              |
| Payment            | JavaScript      | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :100:          | :100:              |
| Product Catalog    | Go              | :100:                     | :no_bell:            | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Quote Service      | PHP             | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Recommendation     | Python          | :100:                     | :100:                | :100:                | :no_bell:               | :no_bell:      | :no_bell:      | :construction:     |
| Shipping           | Rust            | :no_bell:                 | :100:                | :100:                | :100:                   | :no_bell:      | :no_bell:      | :construction:     |
