-- SQLite dump for Quote Management System
-- Converted from MySQL format
-- ------------------------------------------------------

-- Create table for customers
CREATE TABLE IF NOT EXISTS customers (
  customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  address TEXT,
  city TEXT,
  state TEXT,
  zip_code TEXT,
  country TEXT DEFAULT 'USA',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  status TEXT DEFAULT 'prospect' CHECK (status IN ('active','inactive','prospect'))
);

-- Insert data for customers
INSERT INTO customers VALUES 
(1,'Acme Corporation','John Smith','john.smith@acme.com','555-0101','123 Business Ave','New York','NY','10001','USA','2024-01-15 10:30:00','active'),
(2,'Tech Solutions Inc','Sarah Johnson','sarah.j@techsolutions.com','555-0102','456 Innovation Blvd','San Francisco','CA','94105','USA','2024-01-20 14:15:00','active'),
(3,'Global Enterprises','Mike Wilson','mwilson@globalent.com','555-0103','789 Corporate Dr','Chicago','IL','60601','USA','2024-02-01 09:45:00','active'),
(4,'StartUp Dynamics','Emily Chen','emily@startupdyn.com','555-0104','321 Startup St','Austin','TX','73301','USA','2024-02-10 16:20:00','prospect'),
(5,'Manufacturing Plus','Robert Brown','rbrown@mfgplus.com','555-0105','654 Factory Rd','Detroit','MI','48201','USA','2024-02-15 11:30:00','active'),
(6,'Retail Solutions','Lisa Davis','ldavis@retailsol.com','555-0106','987 Commerce Pkwy','Atlanta','GA','30301','USA','2024-03-01 13:45:00','prospect'),
(7,'Healthcare Systems','David Lee','dlee@healthsys.com','555-0107','147 Medical Plaza','Boston','MA','02101','USA','2024-03-05 08:15:00','active'),
(8,'Financial Partners','Jennifer White','jwhite@finpartners.com','555-0108','258 Banking Blvd','Charlotte','NC','28201','USA','2024-03-10 15:30:00','active'),
(9,'Education Network','Michael Green','mgreen@edunet.com','555-0109','369 Campus Dr','Denver','CO','80201','USA','2024-03-15 12:00:00','prospect'),
(10,'Logistics Corp','Amanda Taylor','ataylor@logicorp.com','555-0110','741 Distribution Way','Phoenix','AZ','85001','USA','2024-03-20 10:45:00','active');

-- Create table for services
CREATE TABLE IF NOT EXISTS services (
  service_id INTEGER PRIMARY KEY AUTOINCREMENT,
  service_name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  base_price DECIMAL(10,2) NOT NULL,
  unit_type TEXT DEFAULT 'each',
  active INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert data for services
INSERT INTO services VALUES 
(1,'Web Development','Custom website development','Technology',2500.00,'project',1,'2024-01-01 00:00:00'),
(2,'Mobile App Development','iOS and Android app development','Technology',5000.00,'project',1,'2024-01-01 00:00:00'),
(3,'Database Design','Database architecture and implementation','Technology',1500.00,'project',1,'2024-01-01 00:00:00'),
(4,'Cloud Migration','Move systems to cloud infrastructure','Technology',3500.00,'project',1,'2024-01-01 00:00:00'),
(5,'Security Audit','Comprehensive security assessment','Security',2000.00,'project',1,'2024-01-01 00:00:00'),
(6,'Technical Consulting','Expert technology consultation','Consulting',150.00,'hour',1,'2024-01-01 00:00:00'),
(7,'Project Management','Full project management services','Consulting',125.00,'hour',1,'2024-01-01 00:00:00'),
(8,'Data Analytics','Business intelligence and reporting','Analytics',1800.00,'project',1,'2024-01-01 00:00:00'),
(9,'System Integration','Connect disparate systems','Technology',2800.00,'project',1,'2024-01-01 00:00:00'),
(10,'Training Services','Staff training and development','Training',100.00,'hour',1,'2024-01-01 00:00:00'),
(11,'Maintenance Support','Ongoing system maintenance','Support',75.00,'hour',1,'2024-01-01 00:00:00'),
(12,'Performance Optimization','System performance tuning','Technology',1200.00,'project',1,'2024-01-01 00:00:00'),
(13,'API Development','Custom API creation','Technology',2200.00,'project',1,'2024-01-01 00:00:00'),
(14,'Quality Assurance','Testing and QA services','Testing',90.00,'hour',1,'2024-01-01 00:00:00'),
(15,'Documentation','Technical documentation services','Documentation',65.00,'hour',1,'2024-01-01 00:00:00');

-- Create table for quotes
CREATE TABLE IF NOT EXISTS quotes (
  quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL,
  quote_number TEXT NOT NULL UNIQUE,
  quote_date DATE NOT NULL,
  expiration_date DATE NOT NULL,
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft','sent','accepted','rejected','expired')),
  subtotal DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  tax_rate DECIMAL(5,4) DEFAULT 0.0875,
  tax_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  total_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT DEFAULT 'system',
  FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- Create index for quotes
CREATE INDEX IF NOT EXISTS idx_quotes_customer_id ON quotes(customer_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_quotes_date ON quotes(quote_date);

-- Insert data for quotes
INSERT INTO quotes VALUES 
(1,1,'Q-2024-001','2024-03-01','2024-03-31','sent',7500.00,0.0875,656.25,8156.25,'Initial web development proposal','2024-03-01 10:00:00','2024-03-01 10:00:00','system'),
(2,2,'Q-2024-002','2024-03-02','2024-04-01','accepted',12000.00,0.0875,1050.00,13050.00,'Mobile app development for iOS and Android','2024-03-02 11:15:00','2024-03-05 14:30:00','system'),
(3,3,'Q-2024-003','2024-03-05','2024-04-04','sent',4200.00,0.0875,367.50,4567.50,'Database design and cloud migration','2024-03-05 09:30:00','2024-03-05 09:30:00','system'),
(4,4,'Q-2024-004','2024-03-08','2024-04-07','draft',2500.00,0.0875,218.75,2718.75,'Web development for startup','2024-03-08 16:45:00','2024-03-08 16:45:00','system'),
(5,5,'Q-2024-005','2024-03-10','2024-04-09','accepted',8500.00,0.0875,743.75,9243.75,'System integration and security audit','2024-03-10 13:20:00','2024-03-12 10:15:00','system'),
(6,6,'Q-2024-006','2024-03-12','2024-04-11','sent',3600.00,0.0875,315.00,3915.00,'Data analytics solution','2024-03-12 14:00:00','2024-03-12 14:00:00','system'),
(7,7,'Q-2024-007','2024-03-15','2024-04-14','rejected',6800.00,0.0875,595.00,7395.00,'Healthcare system integration','2024-03-15 08:45:00','2024-03-18 16:20:00','system'),
(8,8,'Q-2024-008','2024-03-18','2024-04-17','accepted',4500.00,0.0875,393.75,4893.75,'Financial API development','2024-03-18 11:30:00','2024-03-20 09:45:00','system'),
(9,9,'Q-2024-009','2024-03-20','2024-04-19','sent',3200.00,0.0875,280.00,3480.00,'Education platform consulting','2024-03-20 15:15:00','2024-03-20 15:15:00','system'),
(10,10,'Q-2024-010','2024-03-22','2024-04-21','draft',5500.00,0.0875,481.25,5981.25,'Logistics system optimization','2024-03-22 12:00:00','2024-03-22 12:00:00','system');

-- Create table for quote_items
CREATE TABLE IF NOT EXISTS quote_items (
  quote_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  quote_id INTEGER NOT NULL,
  service_id INTEGER NOT NULL,
  quantity DECIMAL(8,2) NOT NULL DEFAULT 1.00,
  unit_price DECIMAL(10,2) NOT NULL,
  discount_percent DECIMAL(5,2) DEFAULT 0.00,
  line_total DECIMAL(12,2) NOT NULL,
  description TEXT,
  sort_order INTEGER DEFAULT 0,
  FOREIGN KEY (quote_id) REFERENCES quotes (quote_id) ON DELETE CASCADE,
  FOREIGN KEY (service_id) REFERENCES services (service_id)
);

-- Create indexes for quote_items
CREATE INDEX IF NOT EXISTS idx_quote_items_quote_id ON quote_items(quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_items_service_id ON quote_items(service_id);

-- Insert data for quote_items
INSERT INTO quote_items VALUES 
(1,1,1,1.00,2500.00,0.00,2500.00,'Custom corporate website',1),
(2,1,3,1.00,1500.00,0.00,1500.00,'Database design for customer portal',2),
(3,1,6,24.00,150.00,0.00,3600.00,'Technical consulting hours',3),
(4,2,2,1.00,5000.00,0.00,5000.00,'Mobile app development',1),
(5,2,13,1.00,2200.00,0.00,2200.00,'API development for mobile backend',2),
(6,2,6,32.00,150.00,0.00,4800.00,'Consulting and project management',3),
(7,3,3,1.00,1500.00,0.00,1500.00,'Database architecture',1),
(8,3,4,1.00,3500.00,10.00,3150.00,'Cloud migration with discount',2),
(9,4,1,1.00,2500.00,0.00,2500.00,'Startup website development',1),
(10,5,9,1.00,2800.00,0.00,2800.00,'System integration',1),
(11,5,5,1.00,2000.00,0.00,2000.00,'Security audit',2),
(12,5,6,24.00,150.00,5.00,3420.00,'Consulting with volume discount',3),
(13,6,8,1.00,1800.00,0.00,1800.00,'Data analytics implementation',1),
(14,6,10,18.00,100.00,0.00,1800.00,'Staff training on analytics tools',2),
(15,7,9,1.00,2800.00,0.00,2800.00,'Healthcare system integration',1),
(16,7,5,1.00,2000.00,0.00,2000.00,'HIPAA compliance audit',2),
(17,7,6,16.00,150.00,8.00,2208.00,'Specialized healthcare consulting',3),
(18,8,13,1.00,2200.00,0.00,2200.00,'Financial services API',1),
(19,8,12,1.00,1200.00,0.00,1200.00,'Performance optimization',2),
(20,8,7,8.00,125.00,0.00,1000.00,'Project management',3),
(21,9,6,20.00,150.00,0.00,3000.00,'Educational platform consulting',1),
(22,9,14,20.00,90.00,10.00,1800.00,'QA testing with education discount',2),
(23,10,12,1.00,1200.00,0.00,1200.00,'Logistics system optimization',1),
(24,10,8,1.00,1800.00,0.00,1800.00,'Performance analytics',2),
(25,10,6,20.00,150.00,0.00,3000.00,'Optimization consulting',3);