<cfscript>

  dur = randRange(50,250,'SHA1PRNG')+400;
  sleep(dur);

  // Determine quote ID to lookup - use invalid ID if error condition
  if (dur > 620) {
    quoteId = 99999; // Invalid quote ID that won't be found
  } else {
    // Get a random valid quote ID from database
    validQuoteQuery = queryExecute("
      SELECT quote_id FROM quotes ORDER BY RANDOM() LIMIT 1
    ", {}, {datasource: "mysql"});
    
    if (validQuoteQuery.recordCount > 0) {
      quoteId = validQuoteQuery.quote_id[1];
    } else {
      quoteId = 1; // Fallback to quote ID 1
    }
  }

  // Try to retrieve the quote from database
  quoteQuery = queryExecute("
    SELECT q.quote_id, q.quote_number, q.total_amount, q.status,
           c.company_name, c.contact_name, c.email
    FROM quotes q
    JOIN customers c ON q.customer_id = c.customer_id
    WHERE q.quote_id = :quoteId
  ", {
    quoteId: {value: quoteId, cfsqltype: "cf_sql_integer"}
  }, {datasource: "mysql"});

  if (quoteQuery.recordCount == 0) {
    throw(type="QuoteRetrivalError", message="Quote " & quoteId & " not available");
  }

  // Generate order data based on the quote
  orderData = {
    "email": quoteQuery.email[1],
    "order": {
      "order_id": quoteQuery.quote_number[1],
      "shipping_cost": {
        "currency_code": "USD",
        "units": randRange(5,25,'SHA1PRNG'),
        "nanos": 0
      },
      "shipping_address": {
        "street_address": "123 Main St",
        "city": "New York",
        "state": "NY",
        "country": "USA",
        "zip_code": "10001"
      },
      "items": [
        {
          "item": {
            "product_id": "QUOTE-" & quoteQuery.quote_id[1],
            "quantity": 1
          },
          "cost": {
            "currency_code": "USD",
            "units": int(quoteQuery.total_amount[1]),
            "nanos": 0
          }
        }
      ]
    }
  };
  
  // Call email service to send order confirmation (this uses HTTP)
  emailAddr = structKeyExists(server.system.environment, "EMAIL_ADDR") ? server.system.environment.EMAIL_ADDR : "http://email:6060";
  cfhttp(method="POST", charset="utf-8", url="#emailAddr#/send_order_confirmation", result="emailResult") {
    cfhttpparam(type="header", name="Content-Type", value="application/json");
    cfhttpparam(type="body", value="#serializeJSON(orderData)#");
  }
</cfscript>
