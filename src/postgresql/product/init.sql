
    DROP TABLE IF EXISTS "product";
    DROP TABLE IF EXISTS "productstate";
    CREATE TABLE "product" (
    "id"	VARCHAR(20),
    "name"	VARCHAR(100),
    "description"	VARCHAR(1000),
    "picture"	VARCHAR(512),
    "priceusdcurrencycode"	VARCHAR(512),
    "priceusdunits"	VARCHAR(512),
    "priceusdnanos"	INT,
    "categories"	VARCHAR(1000)
    );

    INSERT INTO "product" ("id", "name", "description", "picture", "priceusdcurrencycode", "priceusdunits", "priceusdnanos", "categories") VALUES
    ('OLJCESPC7Z', 'National Park Foundation Explorascope', 'The National Park Foundation’s (NPF) Explorascope 60AZ is a manual alt-azimuth, refractor telescope perfect for celestial viewing on the go. The NPF Explorascope 60 can view the planets, moon, star clusters and brighter deep sky objects like the Orion Nebula and Andromeda Galaxy.', 'NationalParkFoundationExplorascope.jpg', 'USD', '101', '960000000', 'telescopes'),
    ('66VCHSJNUP', 'Starsense Explorer Refractor Telescope', 'The first telescope that uses your smartphone to analyze the night sky and calculate its position in real time. StarSense Explorer is ideal for beginners thanks to the app’s user-friendly interface and detailed tutorials. It’s like having your own personal tour guide of the night sky', 'StarsenseExplorer.jpg', 'USD', '349', '950000000', 'telescopes'),
    ('1YMWWN1N4O', 'Eclipsmart Travel Refractor Telescope', 'Dedicated white-light solar scope for the observer on the go. The 50mm refracting solar scope uses Solar Safe, ISO compliant, full-aperture glass filter material to ensure the safest view of solar events.  The kit comes complete with everything you need, including the dedicated travel solar scope, a Solar Safe finderscope, tripod, a high quality 20mm (18x) Kellner eyepiece and a nylon backpack to carry everything in.  This Travel Solar Scope makes it easy to share the Sun as well as partial and total solar eclipses with the whole family and offers much higher magnifications than you would otherwise get using handheld solar viewers or binoculars.', 'EclipsmartTravelRefractorTelescope.jpg', 'USD', '129', '950000000', 'telescopes,travel'),
    ('L9ECAV7KIM', 'Lens Cleaning Kit', 'Wipe away dust, dirt, fingerprints and other particles on your lenses to see clearly with the Lens Cleaning Kit. This cleaning kit works on all glass and optical surfaces, including telescopes, binoculars, spotting scopes, monoculars, microscopes, and even your camera lenses, computer screens, and mobile devices.  The kit comes complete with a retractable lens brush to remove dust particles and dirt and two options to clean smudges and fingerprints off of your optics, pre-moistened lens wipes and a bottled lens cleaning fluid with soft cloth.', 'LensCleaningKit.jpg', 'USD', '21', '950000000', 'accessories'),
    ('2ZYFJ3GM2N', 'Roof Binoculars', 'This versatile, all-around binocular is a great choice for the trail, the stadium, the arena, or just about anywhere you want a close-up view of the action without sacrificing brightness or detail. It’s an especially great companion for nature observation and bird watching, with ED glass that helps you spot the subtlest field markings and a close focus of just 6.5 feet.', 'RoofBinoculars.jpg', 'USD', '209', '950000000', 'binoculars'),
    ('0PUK6V6EV0', 'Solar System Color Imager', 'You have your new telescope and have observed Saturn and Jupiter. Now you are ready to take the next step and start imaging them. But where do you begin? The NexImage 10 Solar System Imager is the perfect solution.', 'SolarSystemColorImager.jpg', 'USD', '175', '0', 'accessories,telescopes'),
    ('LS4PSXUNUM', 'Red Flashlight', 'This 3-in-1 device features a 3-mode red flashlight, a hand warmer, and a portable power bank for recharging your personal electronics on the go. Whether you use it to light the way at an astronomy star party, a night walk, or wildlife research, ThermoTorch 3 Astro Red’s rugged, IPX4-rated design will withstand your everyday activities.', 'RedFlashlight.jpg', 'USD', '57', '80000000', 'accessories,flashlights'),
    ('9SIQT8TOJO', 'Optical Tube Assembly', 'Capturing impressive deep-sky astroimages is easier than ever with Rowe-Ackermann Schmidt Astrograph (RASA) V2, the perfect companion to today’s top DSLR or astronomical CCD cameras. This fast, wide-field f/2.2 system allows for shorter exposure times compared to traditional f/10 astroimaging, without sacrificing resolution. Because shorter sub-exposure times are possible, your equatorial mount won’t need to accurately track over extended periods. The short focal length also lessens equatorial tracking demands. In many cases, autoguiding will not be required.', 'OpticalTubeAssembly.jpg', 'USD', '3599', '0', 'accessories,telescopes,assembly'),
    ('6E92ZMYYFZ', 'Solar Filter', 'Enhance your viewing experience with EclipSmart Solar Filter for 8” telescopes. With two Velcro straps and four self-adhesive Velcro pads for added safety, you can be assured that the solar filter cannot be accidentally knocked off and will provide Solar Safe, ISO compliant viewing.', 'SolarFilter.jpg', 'USD', '69', '950000000', 'accessories,telescopes'),
    ('HQTGWGPNH4', 'The Comet Book', 'A 16th-century treatise on comets, created anonymously in Flanders (now northern France) and now held at the Universitätsbibliothek Kassel. Commonly known as The Comet Book (or Kometenbuch in German), its full title translates as “Comets and their General and Particular Meanings, According to Ptolomeé, Albumasar, Haly, Aliquind and other Astrologers”. The image is from https://publicdomainreview.org/collection/the-comet-book, made available by the Universitätsbibliothek Kassel under a CC-BY SA 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/)', 'TheCometBook.jpg', 'USD', '0', '990000000', 'books');

    CREATE VIEW state AS
      SELECT f.id AS key , f.id as etag, json_build_object('Id', json_agg(f.id),'Name', json_agg(f.name),'Picture',json_agg(f.picture),'PriceUSCurrencyCode',json_agg(f.priceusdcurrencycode), 'PriceUSUnits', json_agg(f.priceusdunits), 'PriceUSNano', json_agg(f.priceusdnanos), 'Categories', json_agg(f.categories)) AS value
      FROM product f GROUP BY f.id;

    CREATE TABLE "productstate" (
       "key"	VARCHAR(20),
       "value"	jsonb
       );


       INSERT INTO "productstate" ("key", "value") VALUES
       ('OLJCESPC7Z', '{
      "id": "OLJCESPC7Z",
        "name": "National Park Foundation Explorascope",
        "description": "The National Park Foundation’s (NPF) Explorascope 60AZ is a manual alt-azimuth, refractor telescope perfect for celestial viewing on the go. The NPF Explorascope 60 can view the planets, moon, star clusters and brighter deep sky objects like the Orion Nebula and Andromeda Galaxy.",
        "picture": "NationalParkFoundationExplorascope.jpg",
        "priceUsd": {
          "currencyCode": "USD",
          "units": 101,
          "nanos": 960000000
        },
        "categories": ["telescopes"]
      }'),
    ('66VCHSJNUP', '{
        "id": "66VCHSJNUP",
        "name": "Starsense Explorer Refractor Telescope",
        "description": "The first telescope that uses your smartphone to analyze the night sky and calculate its position in real time. StarSense Explorer is ideal for beginners thanks to the app’s user-friendly interface and detailed tutorials. It’s like having your own personal tour guide of the night sky",
        "picture": "StarsenseExplorer.jpg",
        "priceUsd": {
          "currencyCode": "USD",
          "units": 349,
          "nanos": 950000000
        },
        "categories": ["telescopes"]
        }'),
         ('1YMWWN1N4O', '{
      "id": "1YMWWN1N4O",
      "name": "Eclipsmart Travel Refractor Telescope",
      "description": "Dedicated white-light solar scope for the observer on the go. The 50mm refracting solar scope uses Solar Safe, ISO compliant, full-aperture glass filter material to ensure the safest view of solar events.  The kit comes complete with everything you need, including the dedicated travel solar scope, a Solar Safe finderscope, tripod, a high quality 20mm (18x) Kellner eyepiece and a nylon backpack to carry everything in.  This Travel Solar Scope makes it easy to share the Sun as well as partial and total solar eclipses with the whole family and offers much higher magnifications than you would otherwise get using handheld solar viewers or binoculars.",
      "picture": "EclipsmartTravelRefractorTelescope.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 129,
        "nanos": 950000000
      },
      "categories": ["telescopes", "travel"]
    }'),
       ('L9ECAV7KIM', '{
      "id": "L9ECAV7KIM",
      "name": "Lens Cleaning Kit",
      "description": "Wipe away dust, dirt, fingerprints and other particles on your lenses to see clearly with the Lens Cleaning Kit. This cleaning kit works on all glass and optical surfaces, including telescopes, binoculars, spotting scopes, monoculars, microscopes, and even your camera lenses, computer screens, and mobile devices.  The kit comes complete with a retractable lens brush to remove dust particles and dirt and two options to clean smudges and fingerprints off of your optics, pre-moistened lens wipes and a bottled lens cleaning fluid with soft cloth.",
      "picture": "LensCleaningKit.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 21,
        "nanos": 950000000
      },
      "categories": ["accessories"]
    }'),
       ('2ZYFJ3GM2N', '{
      "id": "2ZYFJ3GM2N",
      "name": "Roof Binoculars",
      "description": "This versatile, all-around binocular is a great choice for the trail, the stadium, the arena, or just about anywhere you want a close-up view of the action without sacrificing brightness or detail. It’s an especially great companion for nature observation and bird watching, with ED glass that helps you spot the subtlest field markings and a close focus of just 6.5 feet.",
      "picture": "RoofBinoculars.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 209,
        "nanos": 950000000
      },
      "categories": ["binoculars"]
    }'),
       ('0PUK6V6EV0', '{
      "id": "0PUK6V6EV0",
      "name": "Solar System Color Imager",
      "description": "You have your new telescope and have observed Saturn and Jupiter. Now you are ready to take the next step and start imaging them. But where do you begin? The NexImage 10 Solar System Imager is the perfect solution.",
      "picture": "SolarSystemColorImager.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 175,
        "nanos": 0
      },
      "categories": ["accessories", "telescopes"]
     }'),
       ('LS4PSXUNUM', '{
      "id": "LS4PSXUNUM",
      "name": "Red Flashlight",
      "description": "This 3-in-1 device features a 3-mode red flashlight, a hand warmer, and a portable power bank for recharging your personal electronics on the go. Whether you use it to light the way at an astronomy star party, a night walk, or wildlife research, ThermoTorch 3 Astro Red’s rugged, IPX4-rated design will withstand your everyday activities.",
      "picture": "RedFlashlight.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 57,
        "nanos": 80000000
      },
      "categories": ["accessories", "flashlights"]
      }'),
       ('9SIQT8TOJO', '{
      "id": "9SIQT8TOJO",
      "name": "Optical Tube Assembly",
      "description": "Capturing impressive deep-sky astroimages is easier than ever with Rowe-Ackermann Schmidt Astrograph (RASA) V2, the perfect companion to today’s top DSLR or astronomical CCD cameras. This fast, wide-field f/2.2 system allows for shorter exposure times compared to traditional f/10 astroimaging, without sacrificing resolution. Because shorter sub-exposure times are possible, your equatorial mount won’t need to accurately track over extended periods. The short focal length also lessens equatorial tracking demands. In many cases, autoguiding will not be required.",
      "picture": "OpticalTubeAssembly.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 3599,
        "nanos": 0
      },
      "categories": ["accessories", "telescopes", "assembly"]
      }'),
       ('6E92ZMYYFZ', '{
      "id": "6E92ZMYYFZ",
      "name": "Solar Filter",
      "description": "Enhance your viewing experience with EclipSmart Solar Filter for 8” telescopes. With two Velcro straps and four self-adhesive Velcro pads for added safety, you can be assured that the solar filter cannot be accidentally knocked off and will provide Solar Safe, ISO compliant viewing.",
      "picture": "SolarFilter.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 69,
        "nanos": 950000000
      },
      "categories": ["accessories", "telescopes"]
    }'),
       ('HQTGWGPNH4', '{
      "id": "HQTGWGPNH4",
      "name": "The Comet Book",
      "description": "A 16th-century treatise on comets, created anonymously in Flanders (now northern France) and now held at the Universitätsbibliothek Kassel. Commonly known as The Comet Book (or Kometenbuch in German), its full title translates as “Comets and their General and Particular Meanings, According to Ptolomeé, Albumasar, Haly, Aliquind and other Astrologers”. The image is from https://publicdomainreview.org/collection/the-comet-book, made available by the Universitätsbibliothek Kassel under a CC-BY SA 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/)",
      "picture": "TheCometBook.jpg",
      "priceUsd": {
        "currencyCode": "USD",
        "units": 0,
        "nanos": 990000000
      },
      "categories": ["books"]
    }');