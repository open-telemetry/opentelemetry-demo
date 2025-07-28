<cfscript>

sleep(randRange(0,300,'SHA1PRNG')+100);

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Function to calculate quote from request data
function calculateQuote(requestData) {
    var quote = 0.0;
    
    try {
        if (!structKeyExists(requestData, "numberOfItems")) {
            throw(type="InvalidArgumentException", message="numberOfItems not provided");
        }
        
        var numberOfItems = val(requestData.numberOfItems);
        var costPerItem = randRange(400, 1000) / 10.0;
        quote = round(costPerItem * numberOfItems * 100) / 100; // Round to 2 decimal places
        
    } catch (any e) {
        // Handle errors but still return quote
        writeLog(file="quote_errors", text="Quote calculation error: " & e.message);
    }
    
    return quote;
}

// Set the response content type to JSON
getPageContext().getResponse().setContentType("application/json");

// Read the request body as JSON
if (len(trim(getHTTPRequestData().content)) > 0) {
    requestData = deserializeJSON(toString(getHTTPRequestData().content));
} else {
    requestData = {};
}

try {
    // Validate input
    if (!structKeyExists(requestData, "numberOfItems")) {
        throw(type="InvalidArgumentException", message="numberOfItems not provided");
    }
    
    numberOfItems = val(requestData.numberOfItems);
    
    // Get customer information (simulate random customer)
    customerQuery = queryExecute("
        SELECT customer_id, company_name, contact_name, email, status
        FROM customers 
        WHERE status = 'active' 
        ORDER BY RANDOM() 
        LIMIT 1
    ", {}, {datasource: "mysql"});
    
    if (customerQuery.recordCount == 0) {
        throw(type="DataException", message="No active customers found");
    }
    
    // Get random services for the quote with join to show service details
    servicesQuery = queryExecute("
        SELECT s.service_id, s.service_name, s.description, s.category, 
               s.base_price, s.unit_type,
               CASE 
                   WHEN s.category = 'Technology' THEN s.base_price * 1.2
                   WHEN s.category = 'Consulting' THEN s.base_price * 1.1
                   ELSE s.base_price
               END as quoted_price
        FROM services s
        WHERE s.active = 1 
        ORDER BY RANDOM() 
        LIMIT :itemCount
    ", {
        itemCount: {value: numberOfItems, cfsqltype: "cf_sql_integer"}
    }, {datasource: "mysql"});
    
    if (servicesQuery.recordCount == 0) {
        throw(type="DataException", message="No services available");
    }
    
    // Calculate quote totals
    subtotal = 0;
    items = [];
    
    for (i = 1; i <= servicesQuery.recordCount; i++) {
        quantity = randRange(1, 5); // Random quantity 1-5
        unitPrice = servicesQuery.quoted_price[i];
        lineTotal = quantity * unitPrice;
        subtotal += lineTotal;
        
        arrayAppend(items, {
            "service_id": servicesQuery.service_id[i],
            "service_name": servicesQuery.service_name[i],
            "category": servicesQuery.category[i],
            "quantity": quantity,
            "unit_price": numberFormat(unitPrice, "999999.99"),
            "line_total": numberFormat(lineTotal, "999999.99")
        });
    }
    
    taxRate = 0.0875; // 8.75% tax rate
    taxAmount = subtotal * taxRate;
    totalAmount = subtotal + taxAmount;
    
    // Create quote record in database with complex join query to verify data integrity
    quoteNumber = "Q-" & year(now()) & "-" & (randRange(1000, 9999));
    
    quoteInsert = queryExecute("
        INSERT INTO quotes (customer_id, quote_number, quote_date, expiration_date, 
                           status, subtotal, tax_rate, tax_amount, total_amount, notes)
        SELECT c.customer_id, :quoteNumber, DATE('now'), DATE('now', '+30 days'),
               'draft', :subtotal, :taxRate, :taxAmount, :totalAmount, 
               'Auto-generated quote for ' || c.company_name || ' - ' || :itemCount || ' services'
        FROM customers c 
        WHERE c.customer_id = :customerId
    ", {
        quoteNumber: {value: quoteNumber, cfsqltype: "cf_sql_varchar"},
        customerId: {value: customerQuery.customer_id[1], cfsqltype: "cf_sql_integer"},
        subtotal: {value: subtotal, cfsqltype: "cf_sql_decimal", scale: 2},
        taxRate: {value: taxRate, cfsqltype: "cf_sql_decimal", scale: 4},
        taxAmount: {value: taxAmount, cfsqltype: "cf_sql_decimal", scale: 2},
        totalAmount: {value: totalAmount, cfsqltype: "cf_sql_decimal", scale: 2},
        itemCount: {value: numberOfItems, cfsqltype: "cf_sql_integer"}
    }, {datasource: "mysql"});
    
    // Get the inserted quote ID
    quoteIdQuery = queryExecute("SELECT last_insert_rowid() as quote_id", {}, {datasource: "mysql"});
    quoteId = quoteIdQuery.quote_id[1];
    
    // Simulate some processing time
    sleep(randRange(50, 200));
    
    // Build response with customer and quote details
    response = {
        "quote_id": quoteId,
        "quote_number": quoteNumber,
        "customer": {
            "company_name": customerQuery.company_name[1],
            "contact_name": customerQuery.contact_name[1],
            "email": customerQuery.email[1]
        },
        "quote_summary": {
            "subtotal": numberFormat(subtotal, "999999.99"),
            "tax_rate": numberFormat(taxRate * 100, "99.99") & "%",
            "tax_amount": numberFormat(taxAmount, "999999.99"),
            "total_amount": numberFormat(totalAmount, "999999.99")
        },
        "items": items,
        "item_count": numberOfItems,
        "services_selected": servicesQuery.recordCount,
        // total is REQUIRED by the otel demo!! needs to be a float!
        "total": calculateQuote(requestData),
    };
    
    // Output the response as JSON
    writeOutput(serializeJSON(response));
}
catch (any e) {
    // Handle errors and log to application
    writeLog(file="quote_errors", text="Quote generation error: " & e.message & " Detail: " & e.detail);
    
    getPageContext().getResponse().setStatus(500);
    writeOutput(serializeJSON({
        "error": e.message,
        "type": e.type,
        "timestamp": dateTimeFormat(now(), "yyyy-mm-dd HH:nn:ss")
    }));
}
</cfscript>