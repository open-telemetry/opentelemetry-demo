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
	, connectionString: 'jdbc:mysql://' & mysqlHost & ':3306/quotes?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC'
	, username: mysqlUsername
	, password: mysqlPassword

	// optional settings
	, connectionLimit:100 // default:-1
	, liveTimeout:60 // default: -1; unit: minutes
	, alwaysSetTimeout:true // default: false
	, validate:true // default: false
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
    // Read the SQL initialization file content
    var sqlFilePath = "/var/www/sql/init_quotes.sql";
    
    if (!fileExists(sqlFilePath)) {
        throw(message="SQL file not found at: " & sqlFilePath);
    }
    
    var sqlContent = fileRead(sqlFilePath);
    
    // Split SQL content by semicolons to get individual statements
    var statements = listToArray(sqlContent, ";", false, true);
    
    // Execute each SQL statement
    for (var i = 1; i <= arrayLen(statements); i++) {
        var statement = trim(statements[i]);
        
        // Skip empty statements and comments
        if (len(statement) > 0 && !left(statement, 2) == "--" && !left(statement, 2) == "/*") {
            try {
                query datasource="mysql" {
                    writeOutput(statement);
                }
                writeLog("Executed SQL: " & left(statement, 100) & "...");
            } catch (any e) {
                // Log the error but continue with other statements
                writeLog("SQL Error: " & e.message & " Statement: " & left(statement, 200));
                // Don't throw here - some statements might fail (like DROP TABLE if table doesn't exist)
            }
        }
    }
}

}
