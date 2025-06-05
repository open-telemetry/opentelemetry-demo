<cfscript>
// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

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
    
    // Calculate quote
    numberOfItems = val(requestData.numberOfItems);
    costPerItem = randRange(400, 1000) / 10;
    quoteTotal = round(costPerItem * numberOfItems * 100) / 100; // Round to 2 decimal places
    
    // Output the response as JSON
    writeOutput(serializeJSON(quoteTotal));
}
catch (any e) {
    // Handle errors
    getPageContext().getResponse().setStatus(500);
    writeOutput(serializeJSON({"error": e.message}));
}
</cfscript>