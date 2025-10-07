-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

-- Switch to the new database
USE reviews;

-- Feature Flags created and initialized on startup
INSERT INTO productreviews (product_id, username, description, score)
VALUES
    ('OLJCESPC7Z', 'saltman', 'Amazing, just buy it!', '4.5'),
    ('OLJCESPC7Z', 'emusk', NULL, '3.5'),
    ('OLJCESPC7Z', 'jbezos', 'It broke after a few hours, quality issues!', '1.0'),
    ('66VCHSJNUP', 'bgates', 'High quality telescope, I recommend it!', '5.0'),
    ('66VCHSJNUP', 'emusk', 'Great telescope. The smartphone app needs some work though.', '4.0');
