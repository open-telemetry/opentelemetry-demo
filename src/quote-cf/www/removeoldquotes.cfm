<cfscript>

  dur = randRange(0,75,'SHA1PRNG')+100;
  sleep(dur);

  // 5% chance to run a deliberately slow query (5-8 seconds)
  slowQueryChance = randRange(1, 100, 'SHA1PRNG');
  
  if (slowQueryChance <= 5) {
    // Deliberately slow JDBC query using computationally expensive operations
    // This simulates real-world performance issues like bad indexing, complex calculations
    
    slowQuery = queryExecute("
      SELECT 
        q1.quote_id, q1.quote_number, q1.quote_date, q1.status, q1.total_amount,
        q2.quote_id as q2_id, q2.quote_number as q2_number, q2.total_amount as q2_total,
        c1.company_name, c1.contact_name, c1.email,
        c2.company_name as c2_company, c2.contact_name as c2_contact,
        qi.quote_item_id, qi.quantity, qi.unit_price, qi.line_total,
        s.service_name, s.description, s.category, s.base_price,
        -- Expensive string operations but not excessive
        REPEAT(CONCAT(q1.quote_number, ' ', c1.company_name, ' ', s.description), 150) as memory_hog_field,
        -- Correlated subqueries to force row-by-row processing
        (SELECT COUNT(*) FROM quotes q3 WHERE q3.customer_id = q1.customer_id AND q3.quote_date < q1.quote_date) as prior_quotes,
        (SELECT COUNT(*) FROM quotes q4 WHERE q4.customer_id = q2.customer_id AND q4.total_amount > q2.total_amount) as higher_value_quotes,
        (SELECT AVG(qi2.unit_price) FROM quote_items qi2 WHERE qi2.quote_id = q1.quote_id) as avg_item_price,
        -- Moderate LIKE operations
        (SELECT COUNT(*) FROM customers cx WHERE cx.company_name LIKE CONCAT('%', SUBSTRING(c1.company_name, 1, 3), '%')) as similar_customers,
        -- CPU-intensive functions
        MD5(CONCAT(q1.quote_number, c1.company_name, s.description, q1.quote_date)) as computed_hash,
        SHA1(CONCAT(c1.email, qi.unit_price, s.service_name)) as security_hash,
        -- Force some string manipulation
        UPPER(CONCAT(REVERSE(c1.company_name), '_', REVERSE(s.service_name))) as reversed_combo
      FROM quotes q1
      CROSS JOIN quotes q2 
      JOIN customers c1 ON q1.customer_id = c1.customer_id
      JOIN customers c2 ON q2.customer_id = c2.customer_id
      LEFT JOIN quote_items qi ON q1.quote_id = qi.quote_id
      LEFT JOIN services s ON qi.service_id = s.service_id
      WHERE q1.quote_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND q2.quote_date >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND q1.quote_id != q2.quote_id
      -- Force sorting on computed expensive fields
      ORDER BY computed_hash, memory_hog_field, prior_quotes DESC, similar_customers DESC
      LIMIT 25
    ", {}, {datasource: "mysql"});
    
    writeLog(
      text="Executed computationally expensive slow query",
      type="information",
      application="yes",
      file="quote_cleanup"
    );
  } else {
    // Normal fast query (95% of the time)
    slowQuery = queryExecute("
      SELECT 
        q1.quote_id, q1.quote_number, q1.quote_date, q1.status, q1.total_amount,
        q2.quote_id as q2_id, q2.quote_number as q2_number, q2.total_amount as q2_total,
        c1.company_name, c1.contact_name, c1.email,
        c2.company_name as c2_company, c2.contact_name as c2_contact,
        qi.quote_item_id, qi.quantity, qi.unit_price, qi.line_total,
        s.service_name, s.description, s.category, s.base_price,
        -- Match the slow query columns but with simpler operations
        CONCAT(q1.quote_number, ' ', c1.company_name, ' ', s.description) as memory_hog_field,
        1 as prior_quotes,
        1 as higher_value_quotes,
        qi.unit_price as avg_item_price,
        1 as similar_customers,
        MD5(q1.quote_number) as computed_hash,
        SHA1(c1.email) as security_hash,
        UPPER(c1.company_name) as reversed_combo
      FROM quotes q1
      CROSS JOIN quotes q2 
      JOIN customers c1 ON q1.customer_id = c1.customer_id
      JOIN customers c2 ON q2.customer_id = c2.customer_id
      LEFT JOIN quote_items qi ON q1.quote_id = qi.quote_id
      LEFT JOIN services s ON qi.service_id = s.service_id
      WHERE q1.quote_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
      AND q2.quote_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
      AND q1.quote_id != q2.quote_id
      ORDER BY q1.quote_date DESC, q2.quote_date DESC, c1.company_name, s.service_name
      LIMIT 25
    ", {}, {datasource: "mysql"});
  }

  // Process the slow query results to use more memory
  largeDataArray = [];
  for (row = 1; row <= min(slowQuery.recordCount, 1000); row++) {
    arrayAppend(largeDataArray, {
      "data": slowQuery.computed_hash[row] & slowQuery.memory_hog_field[row],
      "processed_at": now(),
      "row_number": row
    });
  }

  // Get old quotes to potentially remove
  oldQuotesQuery = queryExecute("
    SELECT quote_id, quote_number, quote_date, status, total_amount
    FROM quotes 
    WHERE quote_date < DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    AND status IN ('draft', 'rejected', 'expired')
    ORDER BY quote_date ASC
    LIMIT 10
  ", {}, {datasource: "mysql"});

  deletedCount = 0;
  
  // Process each old quote
  for (i = 1; i <= oldQuotesQuery.recordCount; i++) {
    quoteId = oldQuotesQuery.quote_id[i];
    quoteStatus = oldQuotesQuery.status[i];
    
    // Create error condition based on duration
    if (dur > 150 && i == 1) {
      // Simulate error by trying to delete a quote that doesn't exist
      throw(type="DatabaseException", message="Cannot delete quote " & (quoteId + 99999) & " - foreign key constraint violation");
    }
    
    try {
      // Delete quote items first (foreign key dependency)
      queryExecute("
        DELETE FROM quote_items WHERE quote_id = :quoteId
      ", {
        quoteId: {value: quoteId, cfsqltype: "cf_sql_integer"}
      }, {datasource: "mysql"});
      
      // Then delete the quote
      deleteResult = queryExecute("
        DELETE FROM quotes WHERE quote_id = :quoteId
      ", {
        quoteId: {value: quoteId, cfsqltype: "cf_sql_integer"}
      }, {datasource: "mysql"});
      
      deletedCount++;
      
      // Log successful deletion
      writeLog(
        text="Deleted old quote: " & oldQuotesQuery.quote_number[i] & " (ID: " & quoteId & ")",
        type="information",
        application="yes",
        file="quote_cleanup"
      );
      
    } catch (any e) {
      // Log deletion errors
      writeLog(
        text="Error deleting quote " & quoteId & ": " & e.message,
        type="error",
        application="yes",
        file="quote_cleanup"
      );
      
      // Re-throw if it's our deliberate error
      if (findNoCase("foreign key constraint", e.message)) {
        throw(e);
      }
    }
  }

  // Return cleanup summary
  cleanupSummary = {
    "quotes_found": oldQuotesQuery.recordCount,
    "quotes_deleted": deletedCount,
    "cleanup_date": dateTimeFormat(now(), "yyyy-mm-dd HH:nn:ss")
  };
  
  writeOutput(serializeJSON(cleanupSummary));

</cfscript>
