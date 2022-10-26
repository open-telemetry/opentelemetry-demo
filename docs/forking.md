# Forking this Repository

This repository is designed to be forked and used as a tool to show off what you
are doing with OpenTelemetry.

Setting up a fork or a demo usually only requires overriding some environment
variables and possibly replacing some container images.

Live demos can be added to the
[README](https://github.com/open-telemetry/opentelemetry-demo/blob/main/README.md?plain=1#L186).

## Suggestions for Fork Maintainers

- If you'd like to enhance the telemetry data emitted or collected by the demo,
  then we strongly encourage you to backport your changes to this repository.
  For vendor or implementation specific changes, a strategy of modifying
  telemetry in the pipeline via config is preferable to underlying code changes.
- Extend rather than replace. Adding net-new services that interface with the
  existing API is a great way to add vendor-specific or tool-specific features
  that can't be accomplished through telemetry modification.
- To support extensibility, please use repository or facade patterns around
  resources like queues, databases, caches, etc. This will allow for different
  implementations of these services to be shimmed in for different platforms.
- Please do not attempt to backport vendor or tool-specific enhancements to this
  repository.

If you have any questions or would like to suggest ways that we can make your
life easier as a fork maintainer, please open an issue.
