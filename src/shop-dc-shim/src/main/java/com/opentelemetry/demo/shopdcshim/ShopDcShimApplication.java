// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package com.opentelemetry.demo.shopdcshim;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableAsync
@EnableScheduling
public class ShopDcShimApplication {

    public static void main(String[] args) {
        System.out.println("Shop Datacenter Shim Service started - Bridging on-premises retail to cloud checkout");
        SpringApplication.run(ShopDcShimApplication.class, args);
    }
}
