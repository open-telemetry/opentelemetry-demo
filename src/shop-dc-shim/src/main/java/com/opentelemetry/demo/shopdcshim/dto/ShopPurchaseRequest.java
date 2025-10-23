// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.math.BigDecimal;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ShopPurchaseRequest {

    @NotBlank(message = "Customer name is required")
    private String customerName;

    @NotBlank(message = "Email is required")
    @Email(message = "Valid email is required")
    private String customerEmail;

    @NotNull(message = "Total amount is required")
    @Positive(message = "Total amount must be positive")
    private BigDecimal totalAmount;

    @NotBlank(message = "Currency code is required")
    private String currencyCode;

    @NotBlank(message = "Store location is required")
    private String storeLocation;

    @NotBlank(message = "Terminal ID is required")
    private String terminalId;

    @NotNull(message = "Shipping address is required")
    private ShippingAddress shippingAddress;

    @NotNull(message = "Credit card info is required")
    private CreditCardInfo creditCard;

    private List<PurchaseItem> items;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ShippingAddress {
        @NotBlank(message = "Street address is required")
        private String streetAddress;

        @NotBlank(message = "City is required")  
        private String city;

        @NotBlank(message = "State is required")
        private String state;

        @NotBlank(message = "Country is required")
        private String country;

        @NotBlank(message = "ZIP code is required")
        private String zipCode;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CreditCardInfo {
        @NotBlank(message = "Credit card number is required")
        private String creditCardNumber;

        @NotNull(message = "Credit card CVV is required")
        private Integer creditCardCvv;

        @NotNull(message = "Expiration month is required")
        private Integer expirationMonth;

        @NotNull(message = "Expiration year is required")
        private Integer expirationYear;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PurchaseItem {
        @NotBlank(message = "Product ID is required")
        private String productId;

        @NotNull(message = "Quantity is required")
        @Positive(message = "Quantity must be positive")
        private Integer quantity;

        private BigDecimal unitPrice;
        private String productName;
    }
}
