package io.daocloud.dataservice;

import io.daocloud.dataservice.entity.Advertise;
import io.daocloud.dataservice.repository.AdvertiseRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(1)
class MockDataCommandLineRunner implements CommandLineRunner {

    Logger logger = LoggerFactory.getLogger(MockDataCommandLineRunner.class);

    private final AdvertiseRepository advertiseRepository;

    public MockDataCommandLineRunner(final AdvertiseRepository advertiseRepository) {
        this.advertiseRepository = advertiseRepository;
    }

    @Override
    public void run(String... args) throws Exception {
        for (int i = 0; i < 100; i++) {
            Advertise ad = new Advertise();
            ad.setId(i + 1);
            ad.setContent("mock ad content " + i + 1);
            advertiseRepository.save(ad);
        }
        logger.info("init mock data success.");
    }

}