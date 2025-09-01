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
        q1.quote_id, q1.quote_number, CAST(q1.quote_date AS CHAR) as quote_date, q1.status, q1.total_amount,
        q2.quote_id as q2_id, q2.quote_number as q2_number, q2.total_amount as q2_total,
        q3.quote_id as q3_id, q3.quote_number as q3_number, q3.total_amount as q3_total,
        c1.company_name, c1.contact_name, c1.email,
        c2.company_name as c2_company, c2.contact_name as c2_contact,
        c3.company_name as c3_company, c3.contact_name as c3_contact,
        qi.quote_item_id, qi.quantity, qi.unit_price, qi.line_total,
        s.service_name, s.description, s.category, s.base_price,
        -- Complex string operations for 8-second target
        REPLACE(REPLACE(REPLACE(CONCAT(q1.quote_number, ' ', c1.company_name, ' ', IFNULL(s.description, ''), ' ', q2.quote_number, ' ', c2.company_name), 'Q', 'QUOTE'), 'T', 'TECH'), 'S', 'SERV') as memory_hog_field,
        -- Multiple correlated subqueries for controlled slowness
        (SELECT COUNT(*) FROM quotes q5 CROSS JOIN quotes q51 WHERE q5.customer_id = q1.customer_id AND q5.quote_date < q1.quote_date AND q51.quote_id <= 200) as prior_quotes_q1,
        (SELECT COUNT(*) FROM quotes q6 CROSS JOIN quotes q61 WHERE q6.customer_id = q2.customer_id AND q6.total_amount > q2.total_amount AND q61.quote_id <= 200) as higher_value_quotes_q2,
        (SELECT COUNT(*) FROM quotes q7 CROSS JOIN quotes q71 WHERE q7.customer_id = q3.customer_id AND q7.quote_date > q3.quote_date AND q71.quote_id <= 200) as future_quotes_q3,
        (SELECT AVG(qi2.unit_price) FROM quote_items qi2 CROSS JOIN quote_items qi21 WHERE qi2.quote_id = q1.quote_id AND qi21.quote_item_id <= 100) as avg_item_price_q1,
        (SELECT AVG(qi3.unit_price) FROM quote_items qi3 CROSS JOIN quote_items qi31 WHERE qi3.quote_id = q2.quote_id AND qi31.quote_item_id <= 100) as avg_item_price_q2,
        -- Expensive LIKE operations
        (SELECT COUNT(*) FROM customers cx1 CROSS JOIN customers cx11 WHERE cx1.company_name LIKE CONCAT('%', SUBSTR(c1.company_name, 1, 2), '%') AND cx11.customer_id <= 100) as similar_customers_c1,
        (SELECT COUNT(*) FROM customers cx2 CROSS JOIN customers cx22 WHERE cx2.company_name LIKE CONCAT('%', SUBSTR(c2.company_name, 1, 2), '%') AND cx22.customer_id <= 100) as similar_customers_c2,
        -- CPU-intensive functions for controlled delay
        REPLACE(UUID(), '-', '') as computed_hash_1,
        REPLACE(UUID(), '-', '') as computed_hash_2,
        REPLACE(UUID(), '-', '') as computed_hash_3,
        -- String manipulation for controlled processing time
        UPPER(LOWER(UPPER(CONCAT(c1.company_name, '_', c2.company_name, '_', c3.company_name)))) as case_combo,
        LENGTH(CONCAT(q1.quote_number, q2.quote_number, q3.quote_number)) as total_length,
        SUBSTR(CONCAT(c1.company_name, c2.company_name, c3.company_name), 1, 75) as company_combo,
        -- Mathematical operations for 6-8 second target
        (SELECT COUNT(*) * SQRT(q1.quote_id) FROM quotes qx1 CROSS JOIN quotes qx2 WHERE qx1.quote_id <= 100 AND qx2.quote_id <= 100) as math_delay1,
        (SELECT AVG(q6.total_amount * SQRT(q6.quote_id + 1)) FROM quotes q6 CROSS JOIN quotes q62 WHERE q6.quote_id <= 150 AND q62.quote_id <= 100) as log_delay1,
        (SELECT SUM(POWER(c5.customer_id, 2) * RAND()) FROM customers c5 CROSS JOIN customers c51 WHERE c5.customer_id <= 75 AND c51.customer_id <= 75) as power_delay1
      FROM quotes q1
      CROSS JOIN quotes q2 
      CROSS JOIN quotes q3
      JOIN customers c1 ON q1.customer_id = c1.customer_id
      JOIN customers c2 ON q2.customer_id = c2.customer_id
      JOIN customers c3 ON q3.customer_id = c3.customer_id
      LEFT JOIN quote_items qi ON q1.quote_id = qi.quote_id
      LEFT JOIN services s ON qi.service_id = s.service_id
      WHERE date(q1.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND date(q2.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND date(q3.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND q1.quote_id != q2.quote_id
      AND q2.quote_id != q3.quote_id
      AND q1.quote_id != q3.quote_id
      ORDER BY memory_hog_field, case_combo, total_length DESC
      LIMIT 10
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
        q1.quote_id, q1.quote_number, CAST(q1.quote_date AS CHAR) as quote_date, q1.status, q1.total_amount,
        q2.quote_id as q2_id, q2.quote_number as q2_number, q2.total_amount as q2_total,
        c1.company_name, c1.contact_name, c1.email,
        c2.company_name as c2_company, c2.contact_name as c2_contact,
        qi.quote_item_id, qi.quantity, qi.unit_price, qi.line_total,
        s.service_name, s.description, s.category, s.base_price,
        -- Match the slow query columns but with simpler operations
        CONCAT(q1.quote_number, ' ', c1.company_name, ' ', IFNULL(s.description, '')) as memory_hog_field,
        1 as prior_quotes,
        1 as higher_value_quotes,
        qi.unit_price as avg_item_price,
        1 as similar_customers,
        REPLACE(UUID(), '-', '') as computed_hash_1,
        REPLACE(UUID(), '-', '') as computed_hash_2,
        REPLACE(UUID(), '-', '') as computed_hash_3,
        REPLACE(UUID(), '-', '') as computed_hash_4,
        UPPER(c1.company_name) as case_combo,
        LENGTH(CONCAT(q1.quote_number, q2.quote_number)) as total_length,
        SUBSTR(CONCAT(c1.company_name, c2.company_name), 1, 50) as company_combo
      FROM quotes q1
      CROSS JOIN quotes q2 
      JOIN customers c1 ON q1.customer_id = c1.customer_id
      JOIN customers c2 ON q2.customer_id = c2.customer_id
      LEFT JOIN quote_items qi ON q1.quote_id = qi.quote_id
      LEFT JOIN services s ON qi.service_id = s.service_id
      WHERE DATE(q1.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
      AND DATE(q2.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
      AND q1.quote_id != q2.quote_id
      ORDER BY q1.quote_id DESC, q2.quote_id DESC, c1.company_name, s.service_name
      LIMIT 25
    ", {}, {datasource: "mysql"});
  }

  // Process the slow query results to use more memory
  largeDataArray = [];
  for (row = 1; row <= min(slowQuery.recordCount, 1000); row++) {
    arrayAppend(largeDataArray, {
      "data": slowQuery.computed_hash_1[row] & slowQuery.memory_hog_field[row],
      "processed_at": now(),
      "row_number": row
    });
  }

  // Get old quotes to potentially remove
  oldQuotesQuery = queryExecute("
    SELECT quote_id, quote_number, CAST(quote_date AS CHAR) as quote_date, status, total_amount
    FROM quotes 
    WHERE date(quote_date) < DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    AND status IN ('draft', 'rejected', 'expired')
    ORDER BY quote_id ASC
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
