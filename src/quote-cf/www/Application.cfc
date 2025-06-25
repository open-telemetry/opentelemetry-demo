component {

this.Name = "QuoteCF";
this.applicationTimeout = createTimeSpan(0,2,0,0);
this.sessionManagement = true;
this.sessionTimeout = createTimeSpan(0,0,30,0);
this.setClientCookies = true;
this.requestTimeOut = createTimeSpan(0,0,10,0);
this.defaultdatasource="mysql";

  // Get MySQL connection details from environment variables
  mysqlHost = structKeyExists(server.system.environment, "MYSQL_HOST") ? server.system.environment.MYSQL_HOST : "mysql-quote";
  mysqlPort = structKeyExists(server.system.environment, "MYSQL_PORT") ? server.system.environment.MYSQL_PORT : "3306";
  mysqlDatabase = structKeyExists(server.system.environment, "MYSQL_DATABASE") ? server.system.environment.MYSQL_DATABASE : "quotes";
  mysqlUser = structKeyExists(server.system.environment, "MYSQL_USER") ? server.system.environment.MYSQL_USER : "root";
  mysqlPassword = structKeyExists(server.system.environment, "MYSQL_PASSWORD") ? server.system.environment.MYSQL_PASSWORD : "quote_password";

  this.datasources["mysql"] = {
	  class: 'com.mysql.cj.jdbc.Driver'
	, bundleName: 'com.mysql.cj'
	, bundleVersion: '8.0.19'
	, connectionString: 'jdbc:mysql://' & mysqlHost & ':' & mysqlPort & '/' & mysqlDatabase & '?characterEncoding=UTF-8&serverTimezone=Europe/Berlin&maxReconnects=3'
	, username: mysqlUser
	, password: mysqlPassword

	// optional settings
	, connectionLimit:100 // default:-1
	, liveTimeout:60 // default: -1; unit: minutes
	, alwaysSetTimeout:true // default: false
	, validate:false // default: false
};

}
