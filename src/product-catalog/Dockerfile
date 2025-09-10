FROM golang:1.25-alpine AS builder

WORKDIR /app

COPY go.sum go.mod ./
RUN go mod download

COPY . .
RUN go build -o /go/bin/product-catalog .

FROM alpine AS release

WORKDIR /app

COPY ./products ./products
COPY --from=builder /go/bin/product-catalog ./product-catalog

EXPOSE ${PRODUCT_CATALOG_PORT}
ENTRYPOINT ["./product-catalog"]