FROM golang:1.24-alpine AS builder

WORKDIR /usr/src/app

COPY go.mod go.mod
COPY go.sum go.sum

RUN go mod download

COPY . .

RUN go build -o /usr/src/app/product-catalog .

#####################

FROM alpine AS release

WORKDIR /usr/src/app

COPY ./products ./products

COPY --from=builder /usr/src/app/product-catalog .

ENV PRODUCT_CATALOG_PORT=8088

ENTRYPOINT ["/usr/src/app/product-catalog"]
