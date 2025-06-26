component {

this.Name = "QuoteCF";
this.applicationTimeout = createTimeSpan(0,2,0,0);
this.sessionManagement = true;
this.sessionTimeout = createTimeSpan(0,0,30,0);
this.setClientCookies = true;
this.requestTimeOut = createTimeSpan(0,0,10,0);
this.defaultdatasource="mysql";

  // SQLite datasource configuration
  sqliteDbPath = structKeyExists(server.system.environment, "SQLITE_DB_PATH") ? server.system.environment.SQLITE_DB_PATH : "/data/quotes.db";

  this.datasources["mysql"] = {
	  class: 'org.sqlite.JDBC'
	, bundleName: 'org.xerial.sqlite-jdbc'
	, bundleVersion: '3.45.1.0'
	, connectionString: 'jdbc:sqlite:' & sqliteDbPath

	// optional settings
	, connectionLimit:100 // default:-1
	, liveTimeout:60 // default: -1; unit: minutes
	, alwaysSetTimeout:true // default: false
	, validate:false // default: false
};

}
