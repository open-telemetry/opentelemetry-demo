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
        Advertise ad = new Advertise();
        ad.setAdKey("binoculars");
        ad.setRedirectURL("/product/2ZYFJ3GM2N");
        ad.setContent("Roof Binoculars for sale. 50% off.");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("telescopes");
        ad.setRedirectURL("/product/66VCHSJNUP");
        ad.setContent("Starsense Explorer Refractor Telescope for sale. 20% off.");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("accessories");
        ad.setRedirectURL("/product/0PUK6V6EV0");
        ad.setContent("Solar System Color Imager for sale. 30% off.");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("accessories");
        ad.setRedirectURL("/product/6E92ZMYYFZ");
        ad.setContent("Solar Filter for sale. Buy two, get third one for free");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("accessories");
        ad.setRedirectURL("/product/L9ECAV7KIM");
        ad.setContent("Lens Cleaning Kit for sale. Buy one, get second one for free");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("assembly");
        ad.setRedirectURL("/product/9SIQT8TOJO");
        ad.setContent("Optical Tube Assembly for sale. 10% off.");
        advertiseRepository.save(ad);

        ad = new Advertise();
        ad.setAdKey("travel");
        ad.setRedirectURL("/product/1YMWWN1N4O");
        ad.setContent("Eclipsmart Travel Refractor Telescope for sale. Buy one, get second kit for free");
        advertiseRepository.save(ad);

        logger.info("init data success.");
    }
}