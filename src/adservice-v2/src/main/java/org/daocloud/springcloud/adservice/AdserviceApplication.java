package org.daocloud.springcloud.adservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication
@EnableDiscoveryClient
public class AdserviceApplication {

    public static void main(String[] args) {
        SpringApplication.run(AdserviceApplication.class, args);
    }
}

