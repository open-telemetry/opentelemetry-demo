component {

this.Name = "QuoteCF";
this.javaSettings = { loadPaths: ["/var/www/lib/"], loadCFMLClassPath: false, reloadOnChange: false };

public boolean function onApplicationStart() {
    var apiKey = structKeyExists(server.system.environment, "BUGSNAG_API_KEY")
        ? server.system.environment["BUGSNAG_API_KEY"]
        : "";
    if (len(trim(apiKey))) {
        application.bugsnag = createObject("java", "com.bugsnag.Bugsnag").init(apiKey);
    }
    return true;
}

public void function onError(required any Exception, required string EventName) {
    if (isDefined("application.bugsnag") && isObject(application.bugsnag)) {
        // Lucee passes exceptions as CF structs; Bugsnag.notify() requires a Java Throwable.
        // Use the native Java exception if present, otherwise wrap the message in a RuntimeException.
        var throwable = "";
        if (structKeyExists(arguments.Exception, "nativeData") && isObject(arguments.Exception.nativeData)) {
            throwable = arguments.Exception.nativeData;
        } else {
            throwable = createObject("java", "java.lang.RuntimeException").init(
                arguments.Exception.type & ": " & arguments.Exception.message
            );
        }
        application.bugsnag.notify(throwable);
    }
}
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


}
