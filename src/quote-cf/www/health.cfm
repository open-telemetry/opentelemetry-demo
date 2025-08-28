<cfscript>
    // Set content type for health check
    cfheader(name="Content-Type", value="text/plain");
    
    try {
        // Test database connection with a simple query
        query name="healthCheck" datasource="mysql" {
            writeOutput("SELECT COUNT(*) as customer_count FROM customers");
        }
        
        // If we get here, database connection is working
        if (healthCheck.recordCount GT 0) {
            writeOutput("ok");
        } else {
            cfheader(statusCode="503", statusText="Service Unavailable");
            writeOutput("database_error: no results from health check query");
        }
        
    } catch (any e) {
        // Database connection failed
        cfheader(statusCode="503", statusText="Service Unavailable");
        writeOutput("database_error: " & e.message);
    }
</cfscript>