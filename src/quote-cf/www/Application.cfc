component {

this.Name = "QuoteCF";
this.applicationTimeout = createTimeSpan(0,2,0,0);
this.sessionManagement = true;
this.sessionTimeout = createTimeSpan(0,0,30,0);
this.setClientCookies = true;
this.requestTimeOut = createTimeSpan(0,0,10,0);
this.defaultdatasource="mysql";

  // MySQL datasource configuration
  mysqlHost = structKeyExists(server.system.environment, "mysql-host") ? server.system.environment["mysql-host"] : "mysql";
  mysqlUsername = structKeyExists(server.system.environment, "mysql-username") ? server.system.environment["mysql-username"] : "quotes_user";
  mysqlPassword = structKeyExists(server.system.environment, "mysql-password") ? server.system.environment["mysql-password"] : "quotes_password";

  this.datasources["mysql"] = {
	  class: 'com.mysql.cj.jdbc.Driver'
	, connectionString: 'jdbc:mysql://' & mysqlHost & ':3306/quotes?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC&connectTimeout=30000&socketTimeout=30000'
	, username: mysqlUsername
	, password: mysqlPassword

	// optional settings
	, connectionLimit:100 // default:-1
	, liveTimeout:60 // default: -1; unit: minutes
	, alwaysSetTimeout:true // default: false
	, validate:true // default: false
};

  // Separate datasource for database initialization with longer timeouts
  this.datasources["mysql_admin"] = {
	  class: 'com.mysql.cj.jdbc.Driver'
	, connectionString: 'jdbc:mysql://' & mysqlHost & ':3306/quotes?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC&connectTimeout=120000&socketTimeout=120000'
	, username: mysqlUsername
	, password: mysqlPassword

	// optional settings for admin operations
	, connectionLimit:10 // fewer connections needed for admin tasks
	, liveTimeout:120 // longer timeout for admin operations
	, alwaysSetTimeout:true 
	, validate:true
};

public boolean function onApplicationStart() {
    try {
        // Initialize/reinitialize the database on application startup
        initializeDatabase();
        writeLog("Database reinitialized successfully on application startup");
        return true;
    } catch (any e) {
        writeLog("Failed to initialize database on startup: " & e.message);
        throw e;
    }
}

private void function initializeDatabase() {
    writeLog("Starting database initialization...");
    
    try {
        // Drop tables in reverse dependency order using admin datasource
        query datasource="mysql_admin" {
            writeOutput("DROP TABLE IF EXISTS quote_items");
        }
        writeLog("Dropped table: quote_items");
        
        query datasource="mysql_admin" {
            writeOutput("DROP TABLE IF EXISTS quotes");
        }
        writeLog("Dropped table: quotes");
        
        query datasource="mysql_admin" {
            writeOutput("DROP TABLE IF EXISTS services");
        }
        writeLog("Dropped table: services");
        
        query datasource="mysql_admin" {
            writeOutput("DROP TABLE IF EXISTS customers");
        }
        writeLog("Dropped table: customers");
        
        // Create customers table using admin datasource
        query datasource="mysql_admin" {
            writeOutput("
                CREATE TABLE customers (
                  customer_id INT NOT NULL AUTO_INCREMENT,
                  company_name VARCHAR(255) NOT NULL,
                  contact_name VARCHAR(255) NOT NULL,
                  email VARCHAR(255) NOT NULL,
                  phone VARCHAR(50) DEFAULT NULL,
                  address TEXT,
                  city VARCHAR(100) DEFAULT NULL,
                  state VARCHAR(50) DEFAULT NULL,
                  zip_code VARCHAR(20) DEFAULT NULL,
                  country VARCHAR(100) DEFAULT 'USA',
                  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  status ENUM('active','inactive','prospect') DEFAULT 'prospect',
                  PRIMARY KEY (customer_id),
                  UNIQUE KEY email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            ");
        }
        writeLog("Created table: customers");
        
        // Create services table  
        query datasource="mysql_admin" {
            writeOutput("
                CREATE TABLE services (
                  service_id INT NOT NULL AUTO_INCREMENT,
                  service_name VARCHAR(255) NOT NULL,
                  description TEXT,
                  category VARCHAR(100) NOT NULL,
                  base_price DECIMAL(10,2) NOT NULL,
                  unit_type VARCHAR(50) DEFAULT 'each',
                  active TINYINT(1) DEFAULT '1',
                  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (service_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            ");
        }
        writeLog("Created table: services");
        
        // Create quotes table
        query datasource="mysql_admin" {
            writeOutput("
                CREATE TABLE quotes (
                  quote_id INT NOT NULL AUTO_INCREMENT,
                  customer_id INT NOT NULL,
                  quote_number VARCHAR(50) NOT NULL,
                  quote_date DATE NOT NULL,
                  expiration_date DATE NOT NULL,
                  status ENUM('draft','sent','accepted','rejected','expired') DEFAULT 'draft',
                  subtotal DECIMAL(12,2) NOT NULL DEFAULT '0.00',
                  tax_rate DECIMAL(5,4) DEFAULT '0.0875',
                  tax_amount DECIMAL(12,2) NOT NULL DEFAULT '0.00',
                  total_amount DECIMAL(12,2) NOT NULL DEFAULT '0.00',
                  notes TEXT,
                  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  created_by VARCHAR(100) DEFAULT 'system',
                  PRIMARY KEY (quote_id),
                  UNIQUE KEY quote_number (quote_number),
                  KEY customer_id (customer_id),
                  KEY status (status),
                  KEY quote_date (quote_date),
                  CONSTRAINT quotes_ibfk_1 FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            ");
        }
        writeLog("Created table: quotes");
        
        // Create quote_items table
        query datasource="mysql_admin" {
            writeOutput("
                CREATE TABLE quote_items (
                  quote_item_id INT NOT NULL AUTO_INCREMENT,
                  quote_id INT NOT NULL,
                  service_id INT NOT NULL,
                  quantity DECIMAL(8,2) NOT NULL DEFAULT '1.00',
                  unit_price DECIMAL(10,2) NOT NULL,
                  discount_percent DECIMAL(5,2) DEFAULT '0.00',
                  line_total DECIMAL(12,2) NOT NULL,
                  description TEXT,
                  sort_order INT DEFAULT '0',
                  PRIMARY KEY (quote_item_id),
                  KEY quote_id (quote_id),
                  KEY service_id (service_id),
                  CONSTRAINT quote_items_ibfk_1 FOREIGN KEY (quote_id) REFERENCES quotes (quote_id) ON DELETE CASCADE,
                  CONSTRAINT quote_items_ibfk_2 FOREIGN KEY (service_id) REFERENCES services (service_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            ");
        }
        writeLog("Created table: quote_items");
        
        // Insert sample customers (50 rows)
        query datasource="mysql_admin" {
            writeOutput("
                INSERT INTO customers VALUES 
                (1,'Acme Corporation','John Smith','john.smith@acme.com','555-0101','123 Business Ave','New York','NY','10001','USA','2024-01-15 10:30:00','active'),
                (2,'Tech Solutions Inc','Sarah Johnson','sarah.j@techsolutions.com','555-0102','456 Innovation Blvd','San Francisco','CA','94105','USA','2024-01-20 14:15:00','active'),
                (3,'Global Enterprises','Mike Wilson','mwilson@globalent.com','555-0103','789 Corporate Dr','Chicago','IL','60601','USA','2024-02-01 09:45:00','active'),
                (4,'StartUp Dynamics','Emily Chen','emily@startupdyn.com','555-0104','321 Startup St','Austin','TX','73301','USA','2024-02-10 16:20:00','prospect'),
                (5,'Manufacturing Plus','Robert Brown','rbrown@mfgplus.com','555-0105','654 Factory Rd','Detroit','MI','48201','USA','2024-02-15 11:30:00','active'),
                (6,'Digital Solutions Corp','Maria Garcia','maria.garcia@digitalsol.com','555-0106','987 Tech Plaza','Seattle','WA','98101','USA','2024-01-25 09:15:00','active'),
                (7,'Innovation Labs','David Kim','david.kim@innovlabs.com','555-0107','456 Research Dr','Austin','TX','78701','USA','2024-02-05 11:45:00','active'),
                (8,'Cloud Systems LLC','Jennifer Lee','jen.lee@cloudsys.com','555-0108','789 Cloud St','Denver','CO','80201','USA','2024-02-12 14:20:00','prospect'),
                (9,'Data Analytics Pro','Michael Wang','m.wang@dataanalytics.com','555-0109','321 Analytics Ave','Boston','MA','02101','USA','2024-02-18 16:30:00','active'),
                (10,'Cyber Security Inc','Lisa Rodriguez','lisa.r@cybersec.com','555-0110','654 Security Blvd','Miami','FL','33101','USA','2024-02-22 13:10:00','active'),
                (11,'AI Innovations','James Thompson','james.t@aiinnov.com','555-0111','147 AI Way','San Jose','CA','95101','USA','2024-03-01 10:00:00','active'),
                (12,'Blockchain Ventures','Sarah Kim','sarah.kim@blockchain.com','555-0112','258 Crypto Dr','Portland','OR','97201','USA','2024-03-05 15:45:00','prospect'),
                (13,'Mobile First LLC','Robert Chen','rob.chen@mobilefirst.com','555-0113','369 Mobile St','Atlanta','GA','30301','USA','2024-03-08 12:30:00','active'),
                (14,'Web Design Studio','Amanda Taylor','amanda@webdesign.com','555-0114','741 Design Ave','Nashville','TN','37201','USA','2024-03-12 09:20:00','active'),
                (15,'E-commerce Solutions','Brian Davis','brian.d@ecommerce.com','555-0115','852 Commerce Rd','Phoenix','AZ','85001','USA','2024-03-15 14:15:00','prospect'),
                (16,'Gaming Studios','Kelly Johnson','kelly.j@gaming.com','555-0116','963 Game Blvd','Las Vegas','NV','89101','USA','2024-03-18 11:40:00','active'),
                (17,'FinTech Innovations','Mark Wilson','mark.w@fintech.com','555-0117','741 Finance St','Charlotte','NC','28201','USA','2024-03-20 16:25:00','active'),
                (18,'Healthcare IT','Patricia Brown','pat.brown@healthit.com','555-0118','852 Medical Dr','Houston','TX','77001','USA','2024-03-22 13:50:00','prospect'),
                (19,'Education Tech','Christopher Lee','chris.lee@edutech.com','555-0119','963 Learning Ave','Minneapolis','MN','55401','USA','2024-03-25 10:35:00','active'),
                (20,'Retail Systems','Michelle Garcia','michelle.g@retail.com','555-0120','147 Retail Blvd','Detroit','MI','48201','USA','2024-03-28 15:20:00','active'),
                (21,'Transportation Tech','Daniel Martinez','dan.martinez@transtech.com','555-0121','258 Transport St','San Diego','CA','92101','USA','2024-04-01 09:45:00','prospect'),
                (22,'Energy Solutions','Rachel Adams','rachel.a@energy.com','555-0122','369 Power Ave','Dallas','TX','75201','USA','2024-04-03 12:10:00','active'),
                (23,'Real Estate Tech','Steven Clark','steve.clark@retech.com','555-0123','741 Property Dr','Orlando','FL','32801','USA','2024-04-05 14:55:00','active'),
                (24,'Agriculture Tech','Laura Lewis','laura.l@agtech.com','555-0124','852 Farm Rd','Kansas City','MO','64101','USA','2024-04-08 11:30:00','prospect'),
                (25,'Manufacturing Tech','Kevin Walker','kevin.w@mfgtech.com','555-0125','963 Factory St','Pittsburgh','PA','15201','USA','2024-04-10 16:05:00','active'),
                (26,'Logistics Pro','Nicole Hall','nicole.h@logistics.com','555-0126','147 Shipping Ave','Baltimore','MD','21201','USA','2024-04-12 08:40:00','active'),
                (27,'Media Solutions','Timothy Allen','tim.allen@media.com','555-0127','258 Media Blvd','Los Angeles','CA','90001','USA','2024-04-15 13:25:00','prospect'),
                (28,'Sports Tech','Kimberly Young','kim.young@sports.com','555-0128','369 Sports Dr','Philadelphia','PA','19101','USA','2024-04-18 10:15:00','active'),
                (29,'Travel Systems','Jason King','jason.king@travel.com','555-0129','741 Tourism St','Salt Lake City','UT','84101','USA','2024-04-20 15:50:00','active'),
                (30,'Food Tech','Stephanie Wright','steph.wright@food.com','555-0130','852 Culinary Ave','New Orleans','LA','70112','USA','2024-04-22 12:35:00','prospect'),
                (31,'Fashion Tech','Ryan Lopez','ryan.lopez@fashion.com','555-0131','963 Style Blvd','New York','NY','10002','USA','2024-04-25 09:20:00','active'),
                (32,'Fitness Solutions','Crystal Hill','crystal.h@fitness.com','555-0132','147 Wellness Dr','San Francisco','CA','94102','USA','2024-04-28 14:40:00','active'),
                (33,'Pet Care Tech','Brandon Scott','brandon.s@petcare.com','555-0133','258 Animal St','Chicago','IL','60602','USA','2024-05-01 11:55:00','prospect'),
                (34,'Home Automation','Melissa Green','melissa.g@homeauto.com','555-0134','369 Smart Ave','Austin','TX','78702','USA','2024-05-03 16:30:00','active'),
                (35,'Environmental Tech','Gregory Adams','greg.adams@envirotech.com','555-0135','741 Green Blvd','Seattle','WA','98102','USA','2024-05-05 08:15:00','active'),
                (36,'Security Systems','Tiffany Baker','tiffany.b@security.com','555-0136','852 Safe Dr','Denver','CO','80202','USA','2024-05-08 13:00:00','prospect'),
                (37,'Consulting Group','Jordan Gonzalez','jordan.g@consulting.com','555-0137','963 Advisory St','Boston','MA','02102','USA','2024-05-10 10:45:00','active'),
                (38,'Research Institute','Samantha Nelson','sam.nelson@research.com','555-0138','147 Discovery Ave','Miami','FL','33102','USA','2024-05-12 15:20:00','active'),
                (39,'Innovation Hub','Tyler Carter','tyler.c@innovation.com','555-0139','258 Creative Blvd','Portland','OR','97202','USA','2024-05-15 12:05:00','prospect'),
                (40,'Development Labs','Vanessa Mitchell','vanessa.m@devlabs.com','555-0140','369 Code Dr','San Jose','CA','95102','USA','2024-05-18 09:30:00','active'),
                (41,'Design Studio Pro','Eric Perez','eric.p@design.com','555-0141','741 Art Ave','Nashville','TN','37202','USA','2024-05-20 14:50:00','active'),
                (42,'Marketing Tech','Andrea Roberts','andrea.r@marketing.com','555-0142','852 Brand St','Atlanta','GA','30302','USA','2024-05-22 11:25:00','prospect'),
                (43,'Analytics Corp','Marcus Turner','marcus.t@analytics.com','555-0143','963 Data Blvd','Phoenix','AZ','85002','USA','2024-05-25 16:10:00','active'),
                (44,'Platform Solutions','Natalie Phillips','natalie.p@platform.com','555-0144','147 System Dr','Las Vegas','NV','89102','USA','2024-05-28 08:35:00','active'),
                (45,'Integration Services','Cameron Campbell','cam.campbell@integration.com','555-0145','258 Connect Ave','Charlotte','NC','28202','USA','2024-06-01 13:15:00','prospect'),
                (46,'Optimization Inc','Sierra Parker','sierra.p@optimization.com','555-0146','369 Efficiency St','Houston','TX','77002','USA','2024-06-03 10:00:00','active'),
                (47,'Performance Labs','Austin Evans','austin.e@performance.com','555-0147','741 Speed Blvd','Minneapolis','MN','55402','USA','2024-06-05 15:25:00','active'),
                (48,'Quality Systems','Destiny Edwards','destiny.e@quality.com','555-0148','852 Excellence Dr','Detroit','MI','48202','USA','2024-06-08 12:40:00','prospect'),
                (49,'Reliability Corp','Jaxon Collins','jaxon.c@reliability.com','555-0149','963 Dependable Ave','San Diego','CA','92102','USA','2024-06-10 09:55:00','active'),
                (50,'Excellence Group','Skylar Stewart','skylar.s@excellence.com','555-0150','147 Superior St','Dallas','TX','75202','USA','2024-06-12 14:20:00','active')
            ");
        }
        writeLog("Inserted 50 sample customers");
        
        // Insert sample services (50 rows)
        query datasource="mysql_admin" {
            writeOutput("
                INSERT INTO services VALUES 
                (1,'Web Development','Custom website development','Technology',2500.00,'project',1,'2024-01-01 00:00:00'),
                (2,'Mobile App Development','iOS and Android app development','Technology',5000.00,'project',1,'2024-01-01 00:00:00'),
                (3,'Database Design','Database architecture and implementation','Technology',1500.00,'project',1,'2024-01-01 00:00:00'),
                (4,'Cloud Migration','Move systems to cloud infrastructure','Technology',3500.00,'project',1,'2024-01-01 00:00:00'),
                (5,'Security Audit','Comprehensive security assessment','Security',2000.00,'project',1,'2024-01-01 00:00:00'),
                (6,'API Development','RESTful API creation and integration','Technology',2800.00,'project',1,'2024-01-01 00:00:00'),
                (7,'DevOps Setup','CI/CD pipeline implementation','Technology',3200.00,'project',1,'2024-01-01 00:00:00'),
                (8,'UI/UX Design','User interface and experience design','Design',2200.00,'project',1,'2024-01-01 00:00:00'),
                (9,'Data Analytics','Business intelligence and reporting','Analytics',1800.00,'project',1,'2024-01-01 00:00:00'),
                (10,'Machine Learning','AI and ML solution development','Technology',4500.00,'project',1,'2024-01-01 00:00:00'),
                (11,'Blockchain Development','Distributed ledger solutions','Technology',5500.00,'project',1,'2024-01-01 00:00:00'),
                (12,'IoT Integration','Internet of Things connectivity','Technology',3800.00,'project',1,'2024-01-01 00:00:00'),
                (13,'Performance Optimization','System performance tuning','Technology',1200.00,'project',1,'2024-01-01 00:00:00'),
                (14,'Technical Consulting','Expert technology consultation','Consulting',150.00,'hour',1,'2024-01-01 00:00:00'),
                (15,'Project Management','Full project management services','Consulting',125.00,'hour',1,'2024-01-01 00:00:00'),
                (16,'Quality Assurance','Testing and QA services','Testing',90.00,'hour',1,'2024-01-01 00:00:00'),
                (17,'Documentation','Technical documentation services','Documentation',65.00,'hour',1,'2024-01-01 00:00:00'),
                (18,'Training Services','Staff training and development','Training',100.00,'hour',1,'2024-01-01 00:00:00'),
                (19,'Maintenance Support','Ongoing system maintenance','Support',75.00,'hour',1,'2024-01-01 00:00:00'),
                (20,'Code Review','Professional code review services','Consulting',110.00,'hour',1,'2024-01-01 00:00:00'),
                (21,'System Architecture','Enterprise system design','Technology',4200.00,'project',1,'2024-01-01 00:00:00'),
                (22,'Microservices Design','Microservices architecture','Technology',3600.00,'project',1,'2024-01-01 00:00:00'),
                (23,'Container Orchestration','Docker and Kubernetes setup','Technology',2900.00,'project',1,'2024-01-01 00:00:00'),
                (24,'Monitoring Setup','Application monitoring solutions','Technology',1600.00,'project',1,'2024-01-01 00:00:00'),
                (25,'Backup Solutions','Data backup and recovery','Technology',2100.00,'project',1,'2024-01-01 00:00:00'),
                (26,'Network Security','Network security implementation','Security',3300.00,'project',1,'2024-01-01 00:00:00'),
                (27,'Penetration Testing','Security penetration testing','Security',2700.00,'project',1,'2024-01-01 00:00:00'),
                (28,'Compliance Audit','Regulatory compliance assessment','Security',2400.00,'project',1,'2024-01-01 00:00:00'),
                (29,'Data Encryption','Data encryption implementation','Security',1900.00,'project',1,'2024-01-01 00:00:00'),
                (30,'Identity Management','User identity and access management','Security',3100.00,'project',1,'2024-01-01 00:00:00'),
                (31,'E-commerce Platform','Online store development','Technology',4800.00,'project',1,'2024-01-01 00:00:00'),
                (32,'CMS Development','Content management system','Technology',3400.00,'project',1,'2024-01-01 00:00:00'),
                (33,'CRM Integration','Customer relationship management','Technology',2800.00,'project',1,'2024-01-01 00:00:00'),
                (34,'ERP Solutions','Enterprise resource planning','Technology',6200.00,'project',1,'2024-01-01 00:00:00'),
                (35,'Business Intelligence','BI dashboard development','Analytics',3700.00,'project',1,'2024-01-01 00:00:00'),
                (36,'Data Warehouse','Data warehousing solutions','Analytics',4100.00,'project',1,'2024-01-01 00:00:00'),
                (37,'ETL Processes','Extract, transform, load processes','Analytics',2600.00,'project',1,'2024-01-01 00:00:00'),
                (38,'Real-time Analytics','Live data analytics platform','Analytics',3900.00,'project',1,'2024-01-01 00:00:00'),
                (39,'Predictive Analytics','Predictive modeling services','Analytics',4300.00,'project',1,'2024-01-01 00:00:00'),
                (40,'Data Visualization','Interactive data visualization','Analytics',2300.00,'project',1,'2024-01-01 00:00:00'),
                (41,'Agile Coaching','Agile methodology coaching','Consulting',180.00,'hour',1,'2024-01-01 00:00:00'),
                (42,'Scrum Master','Certified Scrum Master services','Consulting',160.00,'hour',1,'2024-01-01 00:00:00'),
                (43,'Digital Transformation','Digital transformation consulting','Consulting',200.00,'hour',1,'2024-01-01 00:00:00'),
                (44,'Technology Assessment','Technology stack evaluation','Consulting',140.00,'hour',1,'2024-01-01 00:00:00'),
                (45,'Vendor Selection','Technology vendor evaluation','Consulting',130.00,'hour',1,'2024-01-01 00:00:00'),
                (46,'Risk Assessment','Technology risk evaluation','Consulting',155.00,'hour',1,'2024-01-01 00:00:00'),
                (47,'Process Automation','Business process automation','Technology',3500.00,'project',1,'2024-01-01 00:00:00'),
                (48,'Integration Platform','System integration platform','Technology',4600.00,'project',1,'2024-01-01 00:00:00'),
                (49,'Workflow Management','Workflow management system','Technology',3000.00,'project',1,'2024-01-01 00:00:00'),
                (50,'Legacy Modernization','Legacy system modernization','Technology',5200.00,'project',1,'2024-01-01 00:00:00')
            ");
        }
        writeLog("Inserted 50 sample services");
        
        // Insert sample quotes (30 rows)
        query datasource="mysql_admin" {
            writeOutput("
                INSERT INTO quotes VALUES 
                (1,1,'Q-2024-001','2024-03-01','2024-03-31','sent',7500.00,0.0875,656.25,8156.25,'Initial web development proposal','2024-03-01 10:00:00','2024-03-01 10:00:00','system'),
                (2,2,'Q-2024-002','2024-03-02','2024-04-01','accepted',12000.00,0.0875,1050.00,13050.00,'Mobile app development for iOS and Android','2024-03-02 11:15:00','2024-03-05 14:30:00','system'),
                (3,3,'Q-2024-003','2024-03-05','2024-04-04','sent',4200.00,0.0875,367.50,4567.50,'Database design and cloud migration','2024-03-05 09:30:00','2024-03-05 09:30:00','system'),
                (4,6,'Q-2024-004','2024-03-08','2024-04-07','draft',8500.00,0.0875,743.75,9243.75,'Digital transformation project','2024-03-08 14:20:00','2024-03-08 14:20:00','system'),
                (5,7,'Q-2024-005','2024-03-10','2024-04-09','accepted',15500.00,0.0875,1356.25,16856.25,'Innovation lab setup','2024-03-10 09:45:00','2024-03-12 16:30:00','system'),
                (6,9,'Q-2024-006','2024-03-12','2024-04-11','sent',9800.00,0.0875,857.50,10657.50,'Data analytics platform','2024-03-12 11:15:00','2024-03-12 11:15:00','system'),
                (7,11,'Q-2024-007','2024-03-15','2024-04-14','rejected',22000.00,0.0875,1925.00,23925.00,'AI solution development','2024-03-15 13:40:00','2024-03-18 10:20:00','system'),
                (8,13,'Q-2024-008','2024-03-18','2024-04-17','accepted',6500.00,0.0875,568.75,7068.75,'Mobile-first application','2024-03-18 15:50:00','2024-03-20 12:15:00','system'),
                (9,17,'Q-2024-009','2024-03-20','2024-04-19','sent',11200.00,0.0875,980.00,12180.00,'FinTech integration platform','2024-03-20 10:30:00','2024-03-20 10:30:00','system'),
                (10,20,'Q-2024-010','2024-03-22','2024-04-21','draft',7800.00,0.0875,682.50,8482.50,'Retail system upgrade','2024-03-22 14:05:00','2024-03-22 14:05:00','system'),
                (11,22,'Q-2024-011','2024-03-25','2024-04-24','accepted',13500.00,0.0875,1181.25,14681.25,'Energy management platform','2024-03-25 09:20:00','2024-03-27 16:45:00','system'),
                (12,25,'Q-2024-012','2024-03-28','2024-04-27','sent',9200.00,0.0875,805.00,10005.00,'Manufacturing automation','2024-03-28 11:35:00','2024-03-28 11:35:00','system'),
                (13,28,'Q-2024-013','2024-04-01','2024-05-01','draft',5600.00,0.0875,490.00,6090.00,'Sports analytics dashboard','2024-04-01 13:15:00','2024-04-01 13:15:00','system'),
                (14,31,'Q-2024-014','2024-04-03','2024-05-03','accepted',18000.00,0.0875,1575.00,19575.00,'Fashion e-commerce platform','2024-04-03 15:30:00','2024-04-05 12:20:00','system'),
                (15,34,'Q-2024-015','2024-04-05','2024-05-05','sent',14200.00,0.0875,1242.50,15442.50,'Home automation system','2024-04-05 10:45:00','2024-04-05 10:45:00','system'),
                (16,37,'Q-2024-016','2024-04-08','2024-05-08','rejected',8900.00,0.0875,778.75,9678.75,'Consulting engagement','2024-04-08 14:10:00','2024-04-10 09:30:00','system'),
                (17,40,'Q-2024-017','2024-04-10','2024-05-10','accepted',16800.00,0.0875,1470.00,18270.00,'Development lab infrastructure','2024-04-10 12:25:00','2024-04-12 15:40:00','system'),
                (18,43,'Q-2024-018','2024-04-12','2024-05-12','sent',10500.00,0.0875,918.75,11418.75,'Analytics platform upgrade','2024-04-12 16:55:00','2024-04-12 16:55:00','system'),
                (19,46,'Q-2024-019','2024-04-15','2024-05-15','draft',12800.00,0.0875,1120.00,13920.00,'System optimization project','2024-04-15 08:40:00','2024-04-15 08:40:00','system'),
                (20,49,'Q-2024-020','2024-04-18','2024-05-18','accepted',7400.00,0.0875,647.50,8047.50,'Reliability enhancement','2024-04-18 11:20:00','2024-04-20 14:35:00','system'),
                (21,4,'Q-2024-021','2024-04-20','2024-05-20','sent',19500.00,0.0875,1706.25,21206.25,'Startup platform development','2024-04-20 13:45:00','2024-04-20 13:45:00','system'),
                (22,8,'Q-2024-022','2024-04-22','2024-05-22','draft',11700.00,0.0875,1023.75,12723.75,'Cloud migration project','2024-04-22 15:10:00','2024-04-22 15:10:00','system'),
                (23,12,'Q-2024-023','2024-04-25','2024-05-25','accepted',25000.00,0.0875,2187.50,27187.50,'Blockchain implementation','2024-04-25 09:55:00','2024-04-27 12:40:00','system'),
                (24,16,'Q-2024-024','2024-04-28','2024-05-28','sent',8700.00,0.0875,761.25,9461.25,'Gaming platform features','2024-04-28 14:30:00','2024-04-28 14:30:00','system'),
                (25,21,'Q-2024-025','2024-05-01','2024-05-31','rejected',13200.00,0.0875,1155.00,14355.00,'Transportation management','2024-05-01 10:15:00','2024-05-03 16:20:00','system'),
                (26,26,'Q-2024-026','2024-05-03','2024-06-02','accepted',15800.00,0.0875,1382.50,17182.50,'Logistics optimization','2024-05-03 12:50:00','2024-05-05 09:10:00','system'),
                (27,30,'Q-2024-027','2024-05-05','2024-06-04','sent',9600.00,0.0875,840.00,10440.00,'Food tech solution','2024-05-05 15:25:00','2024-05-05 15:25:00','system'),
                (28,35,'Q-2024-028','2024-05-08','2024-06-07','draft',17200.00,0.0875,1505.00,18705.00,'Environmental monitoring','2024-05-08 11:40:00','2024-05-08 11:40:00','system'),
                (29,41,'Q-2024-029','2024-05-10','2024-06-09','accepted',6800.00,0.0875,595.00,7395.00,'Design studio platform','2024-05-10 13:05:00','2024-05-12 10:25:00','system'),
                (30,47,'Q-2024-030','2024-05-12','2024-06-11','sent',14500.00,0.0875,1268.75,15768.75,'Performance testing suite','2024-05-12 16:15:00','2024-05-12 16:15:00','system')
            ");
        }
        writeLog("Inserted 30 sample quotes");
        
        // Insert sample quote items (50 rows)
        query datasource="mysql_admin" {
            writeOutput("
                INSERT INTO quote_items VALUES 
                (1,1,1,1.00,2500.00,0.00,2500.00,'Custom corporate website',1),
                (2,1,3,1.00,1500.00,0.00,1500.00,'Database design for customer portal',2),
                (3,1,6,1.00,2800.00,5.00,2660.00,'API development with discount',3),
                (4,2,2,1.00,5000.00,0.00,5000.00,'Mobile app development',1),
                (5,2,13,1.00,1200.00,0.00,1200.00,'Performance optimization',2),
                (6,2,16,48.00,90.00,0.00,4320.00,'QA testing hours',3),
                (7,2,15,24.00,125.00,0.00,3000.00,'Project management',4),
                (8,3,3,1.00,1500.00,0.00,1500.00,'Database architecture',1),
                (9,3,4,1.00,3500.00,10.00,3150.00,'Cloud migration with discount',2),
                (10,4,7,1.00,3200.00,0.00,3200.00,'DevOps setup',1),
                (11,4,21,1.00,4200.00,0.00,4200.00,'System architecture',2),
                (12,4,14,16.00,150.00,5.00,2280.00,'Technical consulting hours',3),
                (13,5,10,1.00,4500.00,0.00,4500.00,'Machine learning solution',1),
                (14,5,35,1.00,3700.00,0.00,3700.00,'Business intelligence',2),
                (15,5,41,32.00,180.00,10.00,5184.00,'Agile coaching with volume discount',3),
                (16,6,9,1.00,1800.00,0.00,1800.00,'Data analytics',1),
                (17,6,37,1.00,2600.00,0.00,2600.00,'ETL processes',2),
                (18,6,40,1.00,2300.00,0.00,2300.00,'Data visualization',3),
                (19,6,18,40.00,100.00,15.00,3400.00,'Training services with discount',4),
                (20,7,11,1.00,5500.00,0.00,5500.00,'Blockchain development',1),
                (21,7,10,2.00,4500.00,5.00,8550.00,'AI solution development',2),
                (22,7,43,80.00,200.00,8.00,14720.00,'Digital transformation consulting',3),
                (23,8,2,1.00,5000.00,0.00,5000.00,'Mobile app development',1),
                (24,8,8,1.00,2200.00,0.00,2200.00,'UI/UX design',2),
                (25,9,6,1.00,2800.00,0.00,2800.00,'API development',1),
                (26,9,33,1.00,2800.00,0.00,2800.00,'CRM integration',2),
                (27,9,26,1.00,3300.00,0.00,3300.00,'Network security',3),
                (28,9,46,20.00,155.00,0.00,3100.00,'Risk assessment hours',4),
                (29,10,32,1.00,3400.00,0.00,3400.00,'CMS development',1),
                (30,10,31,1.00,4800.00,10.00,4320.00,'E-commerce platform with discount',2),
                (31,11,22,1.00,3600.00,0.00,3600.00,'Microservices design',1),
                (32,11,12,1.00,3800.00,0.00,3800.00,'IoT integration',2),
                (33,11,24,1.00,1600.00,0.00,1600.00,'Monitoring setup',3),
                (34,11,19,64.00,75.00,5.00,4560.00,'Maintenance support hours',4),
                (35,12,47,1.00,3500.00,0.00,3500.00,'Process automation',1),
                (36,12,49,1.00,3000.00,0.00,3000.00,'Workflow management',2),
                (37,12,48,1.00,4600.00,8.00,4232.00,'Integration platform with discount',3),
                (38,13,38,1.00,3900.00,0.00,3900.00,'Real-time analytics',1),
                (39,13,28,1.00,2400.00,0.00,2400.00,'Sports compliance audit',2),
                (40,14,31,1.00,4800.00,0.00,4800.00,'E-commerce platform',1),
                (41,14,32,1.00,3400.00,0.00,3400.00,'CMS development',2),
                (42,14,8,2.00,2200.00,5.00,4180.00,'UI/UX design with discount',3),
                (43,14,18,60.00,100.00,10.00,5400.00,'Training services for fashion team',4),
                (44,15,12,1.00,3800.00,0.00,3800.00,'IoT integration',1),
                (45,15,47,1.00,3500.00,0.00,3500.00,'Process automation',2),
                (46,15,30,1.00,3100.00,0.00,3100.00,'Identity management',3),
                (47,15,44,32.00,140.00,8.00,4121.60,'Technology assessment hours',4),
                (48,16,43,60.00,200.00,15.00,10200.00,'Digital transformation consulting',1),
                (49,17,50,1.00,5200.00,0.00,5200.00,'Legacy modernization',1),
                (50,17,34,1.00,6200.00,0.00,6200.00,'ERP solutions',2)
            ");
        }
        writeLog("Inserted 50 sample quote items");
        
    } catch (any e) {
        writeLog("Database initialization error: " & e.message);
        throw e;
    }
}

}
