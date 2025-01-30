-- Copyright SmartBear Software
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  picture TEXT NOT NULL
);

CREATE TABLE product_prices (
  id INTEGER PRIMARY KEY,
  product_id TEXT NOT NULL,
  currency TEXT NOT NULL,
  units INTEGER NOT NULL,
  nanos INTEGER NOT NULL ON CONFLICT REPLACE DEFAULT 0,
  UNIQUE (product_id, currency),
  FOREIGN KEY (product_id) 
    REFERENCES products (id) 
      ON DELETE CASCADE 
      ON UPDATE NO ACTION
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE product_categories (
  product_id TEXT,
  category_id INTEGER,
  PRIMARY KEY (product_id, category_id),
  FOREIGN KEY (product_id) 
    REFERENCES products (id) 
      ON DELETE CASCADE 
      ON UPDATE NO ACTION,
  FOREIGN KEY (category_id) 
    REFERENCES categories (id) 
      ON DELETE CASCADE 
      ON UPDATE NO ACTION
);

INSERT INTO categories (name)
VALUES
  ("telescopes"),
  ("travel"),
  ("binoculars"),
  ("accessories"),
  ("flashlights"),
  ("assembly"),
  ("books");

INSERT INTO products (id, name, description, picture)
VALUES
  ("OLJCESPC7Z", "National Park Foundation Explorascope", "The National Park Foundation’s (NPF) Explorascope 60AZ is a manual alt-azimuth, refractor telescope perfect for celestial viewing on the go. The NPF Explorascope 60 can view the planets, moon, star clusters and brighter deep sky objects like the Orion Nebula and Andromeda Galaxy.", "NationalParkFoundationExplorascope.jpg"),
  ("66VCHSJNUP", "Starsense Explorer Refractor Telescope", "The first telescope that uses your smartphone to analyze the night sky and calculate its position in real time. StarSense Explorer is ideal for beginners thanks to the app’s user-friendly interface and detailed tutorials. It’s like having your own personal tour guide of the night sky", "StarsenseExplorer.jpg"),
  ("1YMWWN1N4O", "Eclipsmart Travel Refractor Telescope", "Dedicated white-light solar scope for the observer on the go. The 50mm refracting solar scope uses Solar Safe, ISO compliant, full-aperture glass filter material to ensure the safest view of solar events.  The kit comes complete with everything you need, including the dedicated travel solar scope, a Solar Safe finderscope, tripod, a high quality 20mm (18x) Kellner eyepiece and a nylon backpack to carry everything in.  This Travel Solar Scope makes it easy to share the Sun as well as partial and total solar eclipses with the whole family and offers much higher magnifications than you would otherwise get using handheld solar viewers or binoculars.", "EclipsmartTravelRefractorTelescope.jpg"),
  ("L9ECAV7KIM", "Lens Cleaning Kit", "Wipe away dust, dirt, fingerprints and other particles on your lenses to see clearly with the Lens Cleaning Kit. This cleaning kit works on all glass and optical surfaces, including telescopes, binoculars, spotting scopes, monoculars, microscopes, and even your camera lenses, computer screens, and mobile devices.  The kit comes complete with a retractable lens brush to remove dust particles and dirt and two options to clean smudges and fingerprints off of your optics, pre-moistened lens wipes and a bottled lens cleaning fluid with soft cloth.", "LensCleaningKit.jpg"),
  ("2ZYFJ3GM2N", "Roof Binoculars", "This versatile, all-around binocular is a great choice for the trail, the stadium, the arena, or just about anywhere you want a close-up view of the action without sacrificing brightness or detail. It’s an especially great companion for nature observation and bird watching, with ED glass that helps you spot the subtlest field markings and a close focus of just 6.5 feet.", "RoofBinoculars.jpg"),
  ("0PUK6V6EV0", "Solar System Color Imager", "You have your new telescope and have observed Saturn and Jupiter. Now you're ready to take the next step and start imaging them. But where do you begin? The NexImage 10 Solar System Imager is the perfect solution.", "SolarSystemColorImager.jpg"),
  ("LS4PSXUNUM", "Red Flashlight", "This 3-in-1 device features a 3-mode red flashlight, a hand warmer, and a portable power bank for recharging your personal electronics on the go. Whether you use it to light the way at an astronomy star party, a night walk, or wildlife research, ThermoTorch 3 Astro Red’s rugged, IPX4-rated design will withstand your everyday activities.", "RedFlashlight.jpg"),
  ("9SIQT8TOJO", "Optical Tube Assembly", "Capturing impressive deep-sky astroimages is easier than ever with Rowe-Ackermann Schmidt Astrograph (RASA) V2, the perfect companion to today’s top DSLR or astronomical CCD cameras. This fast, wide-field f/2.2 system allows for shorter exposure times compared to traditional f/10 astroimaging, without sacrificing resolution. Because shorter sub-exposure times are possible, your equatorial mount won’t need to accurately track over extended periods. The short focal length also lessens equatorial tracking demands. In many cases, autoguiding will not be required.", "OpticalTubeAssembly.jpg"),
  ("6E92ZMYYFZ", "Solar Filter", "Enhance your viewing experience with EclipSmart Solar Filter for 8” telescopes. With two Velcro straps and four self-adhesive Velcro pads for added safety, you can be assured that the solar filter cannot be accidentally knocked off and will provide Solar Safe, ISO compliant viewing.", "SolarFilter.jpg"),
  ("HQTGWGPNH4", "The Comet Book", "A 16th-century treatise on comets, created anonymously in Flanders (now northern France) and now held at the Universitätsbibliothek Kassel. Commonly known as The Comet Book (or Kometenbuch in German), its full title translates as “Comets and their General and Particular Meanings, According to Ptolomeé, Albumasar, Haly, Aliquind and other Astrologers”. The image is from https://publicdomainreview.org/collection/the-comet-book, made available by the Universitätsbibliothek Kassel under a CC-BY SA 4.0 license (https://creativecommons.org/licenses/by-sa/4.0/)", "TheCometBook.jpg");

INSERT INTO product_categories (product_id, category_id) 
VALUES
  ("OLJCESPC7Z", (SELECT id FROM categories WHERE name = "telescopes")),
  ("66VCHSJNUP", (SELECT id FROM categories WHERE name = "telescopes")),
  ("1YMWWN1N4O", (SELECT id FROM categories WHERE name = "telescopes")),
  ("1YMWWN1N4O", (SELECT id FROM categories WHERE name = "travel")),
  ("L9ECAV7KIM", (SELECT id FROM categories WHERE name = "accessories")),
  ("2ZYFJ3GM2N", (SELECT id FROM categories WHERE name = "binoculars")),
  ("0PUK6V6EV0", (SELECT id FROM categories WHERE name = "accessories")),
  ("0PUK6V6EV0", (SELECT id FROM categories WHERE name = "telescopes")),
  ("LS4PSXUNUM", (SELECT id FROM categories WHERE name = "accessories")),
  ("LS4PSXUNUM", (SELECT id FROM categories WHERE name = "flashlights")),
  ("9SIQT8TOJO", (SELECT id FROM categories WHERE name = "accessories")),
  ("9SIQT8TOJO", (SELECT id FROM categories WHERE name = "telescopes")),
  ("9SIQT8TOJO", (SELECT id FROM categories WHERE name = "assembly")),
  ("6E92ZMYYFZ", (SELECT id FROM categories WHERE name = "accessories")),
  ("6E92ZMYYFZ", (SELECT id FROM categories WHERE name = "telescopes")),
  ("HQTGWGPNH4", (SELECT id FROM categories WHERE name = "books"));

INSERT INTO product_prices (product_id, currency, units, nanos) 
VALUES
  ("OLJCESPC7Z", "USD", 101, 960000000),
  ("66VCHSJNUP", "USD", 349, 950000000),
  ("1YMWWN1N4O", "USD", 129, 950000000),
  ("L9ECAV7KIM", "USD", 21, 950000000),
  ("2ZYFJ3GM2N", "USD", 209, 950000000),
  ("0PUK6V6EV0", "USD", 175, 0),
  ("LS4PSXUNUM", "USD", 57, 80000000),
  ("9SIQT8TOJO", "USD", 3599, 0),
  ("6E92ZMYYFZ", "USD", 69, 950000000),
  ("HQTGWGPNH4", "USD", 0, 990000000);
  