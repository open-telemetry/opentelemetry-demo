# All documents to be used in spell check.
ALL_DOCS := $(shell find . -type f -name '*.md' -not -path './.github/*' -not -path './node_modules/*' | sort)
PWD := $(shell pwd)

TOOLS_DIR := ./internal/tools
MISSPELL_BINARY=bin/misspell
MISSPELL = $(TOOLS_DIR)/$(MISSPELL_BINARY)

# see https://github.com/open-telemetry/build-tools/releases for semconvgen updates
# Keep links in semantic_conventions/README.md and .vscode/settings.json in sync!
SEMCONVGEN_VERSION=0.11.0

# TODO: add `yamllint` step to `all` after making sure it works on Mac.
.PHONY: all
all: install-tools markdownlint misspell

$(MISSPELL):
	cd $(TOOLS_DIR) && go build -o $(MISSPELL_BINARY) github.com/client9/misspell/cmd/misspell

.PHONY: misspell
misspell:	$(MISSPELL)
	$(MISSPELL) -error $(ALL_DOCS)

.PHONY: misspell-correction
misspell-correction:	$(MISSPELL)
	$(MISSPELL) -w $(ALL_DOCS)

.PHONY: markdownlint
markdownlint:
	@if ! npm ls markdownlint; then npm install; fi
	@for f in $(ALL_DOCS); do \
		echo $$f; \
		npx --no -p markdownlint-cli markdownlint -c .markdownlint.yaml $$f \
			|| exit 1; \
	done

.PHONY: install-yamllint
install-yamllint:
    # Using a venv is recommended
	pip install -U yamllint~=1.26.1

.PHONY: yamllint
yamllint:
	yamllint .

# Run all checks in order of speed / likely failure.
.PHONY: check
check: misspell markdownlint
	@echo "All checks complete"

# Attempt to fix issues / regenerate tables.
.PHONY: fix
fix: misspell-correction
	@echo "All autofixes complete"

.PHONY: install-tools
install-tools: $(MISSPELL)
	npm install
	@echo "All tools installed"

.PHONY: build-docker-images
build-docker-images:
	docker compose -f docker-compose.yml build

.PHONY: push-docker-images
push-docker-images:
	docker compose -f docker-compose.yml push


.PHONY: k8s_local_apply_db
k8s_local_apply_db:
	kubectl apply -f k8s_local/redis.yaml
	kubectl apply -f k8s_local/postgres.yaml
	kubectl apply -f k8s_local/jaeger.yaml
	kubectl apply -f k8s_local/prometheus.yaml
	kubectl apply -f k8s_local/grafana.yaml
	kubectl apply -f k8s_local/otel-agent-daemonset.yaml

.PHONY: k8s_local_clean_db
k8s_local_clean_db:
	kubectl delete deployment redis
	kubectl delete deployment postgres
	kubectl delete deployment jaeger
	kubectl delete deployment prometheus
	kubectl delete deployment grafana
	kubectl delete daemonset otel-agent
	kubectl delete configmaps otel-agent-config
	kubectl delete configmaps prometheus-config
	kubectl delete configmaps grafana-config
	kubectl delete configmaps grafana-provisioning
	kubectl delete svc redis
	kubectl delete svc postgres
	kubectl delete svc jaeger
	kubectl delete svc prometheus
	kubectl delete svc grafana
	kubectl delete svc otel-agent


.PHONY: k8s_local_apply_services
k8s_local_apply_services:
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/adservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/cartservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/checkoutservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/currencyservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/emailservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/featureflagservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/frontend.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/paymentservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/productcatalogservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/recommendationservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/shippingservice.yaml | kubectl apply -f -
	DOCKER_IMAGE_VERSION=v0.2.0-alpha envsubst < k8s_local/loadgenerator.yaml | kubectl apply -f -

.PHONY: k8s_local_clean_services
k8s_local_clean_services:
	kubectl delete deployment loadgenerator
	kubectl delete deployment adservice
	kubectl delete deployment cartservice
	kubectl delete deployment checkoutservice
	kubectl delete deployment currencyservice
	kubectl delete deployment emailservice
	kubectl delete deployment featureflagservice
	kubectl delete deployment frontend
	kubectl delete deployment paymentservice
	kubectl delete deployment productcatalogservice
	kubectl delete deployment recommendationservice
	kubectl delete deployment shippingservice
	kubectl delete svc adservice
	kubectl delete svc cartservice
	kubectl delete svc checkoutservice
	kubectl delete svc currencyservice
	kubectl delete svc emailservice
	kubectl delete svc featureflagservice
	kubectl delete svc frontend
	kubectl delete svc paymentservice
	kubectl delete svc productcatalogservice
	kubectl delete svc recommendationservice
	kubectl delete svc shippingservice


.PHONY: k8s_local_apply
k8s_local_apply: k8s_local_apply_db k8s_local_apply_services

.PHONY: k8s_local_clean
k8s_local_clean: k8s_local_clean_services k8s_local_clean_db
