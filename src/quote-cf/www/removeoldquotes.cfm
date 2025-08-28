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
        q4.quote_id as q4_id, q4.quote_number as q4_number, q4.total_amount as q4_total,
        c1.company_name, c1.contact_name, c1.email,
        c2.company_name as c2_company, c2.contact_name as c2_contact,
        c3.company_name as c3_company, c3.contact_name as c3_contact,
        c4.company_name as c4_company, c4.contact_name as c4_contact,
        qi.quote_item_id, qi.quantity, qi.unit_price, qi.line_total,
        s.service_name, s.description, s.category, s.base_price,
        -- Very expensive string operations - repeat many times
        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
          CONCAT(q1.quote_number, ' ', c1.company_name, ' ', IFNULL(s.description, ''), ' ',
          q2.quote_number, ' ', c2.company_name, ' ',
          q3.quote_number, ' ', c3.company_name, ' ',
          q4.quote_number, ' ', c4.company_name)
        , 'Q', 'QUOTE'), 'T', 'TECH'), 'S', 'SERV'), 'C', 'COMP'), 'A', 'ACME') as memory_hog_field,
        -- Multiple correlated subqueries to force row-by-row processing WITH SLEEP
        (SELECT COUNT(*) + ABS(RAND() % 100) * 0 FROM quotes q5 WHERE q5.customer_id = q1.customer_id AND q5.quote_date < q1.quote_date AND 1) as prior_quotes_q1,
        (SELECT COUNT(*) + ABS(RAND() % 100) * 0 FROM quotes q6 WHERE q6.customer_id = q2.customer_id AND q6.total_amount > q2.total_amount AND 1) as higher_value_quotes_q2,
        (SELECT COUNT(*) + ABS(RAND() % 100) * 0 FROM quotes q7 WHERE q7.customer_id = q3.customer_id AND q7.quote_date > q3.quote_date AND 1) as future_quotes_q3,
        (SELECT COUNT(*) + ABS(RAND() % 100) * 0 FROM quotes q8 WHERE q8.customer_id = q4.customer_id AND q8.total_amount < q4.total_amount AND 1) as lower_value_quotes_q4,
        (SELECT AVG(qi2.unit_price) FROM quote_items qi2 WHERE qi2.quote_id = q1.quote_id) as avg_item_price_q1,
        (SELECT AVG(qi3.unit_price) FROM quote_items qi3 WHERE qi3.quote_id = q2.quote_id) as avg_item_price_q2,
        (SELECT MAX(qi4.unit_price) FROM quote_items qi4 WHERE qi4.quote_id = q3.quote_id) as max_item_price_q3,
        (SELECT MIN(qi5.unit_price) FROM quote_items qi5 WHERE qi5.quote_id = q4.quote_id) as min_item_price_q4,
        -- Expensive LIKE operations on all customers
        (SELECT COUNT(*) FROM customers cx1 WHERE cx1.company_name LIKE CONCAT('%', SUBSTR(c1.company_name, 1, 2), '%')) as similar_customers_c1,
        (SELECT COUNT(*) FROM customers cx2 WHERE cx2.company_name LIKE CONCAT('%', SUBSTR(c2.company_name, 1, 2), '%')) as similar_customers_c2,
        (SELECT COUNT(*) FROM customers cx3 WHERE cx3.company_name LIKE CONCAT('%', SUBSTR(c3.company_name, 1, 2), '%')) as similar_customers_c3,
        (SELECT COUNT(*) FROM customers cx4 WHERE cx4.company_name LIKE CONCAT('%', SUBSTR(c4.company_name, 1, 2), '%')) as similar_customers_c4,
        -- More CPU-intensive functions
        REPLACE(UUID(), '-', '') as computed_hash_1,
        REPLACE(UUID(), '-', '') as computed_hash_2,
        REPLACE(UUID(), '-', '') as computed_hash_3,
        REPLACE(UUID(), '-', '') as computed_hash_4,
        -- Force massive string manipulation
        UPPER(LOWER(UPPER(LOWER(CONCAT(c1.company_name, '_', c2.company_name, '_', c3.company_name, '_', c4.company_name))))) as case_combo,
        LENGTH(CONCAT(q1.quote_number, q2.quote_number, q3.quote_number, q4.quote_number)) as total_length,
        SUBSTR(CONCAT(c1.company_name, c2.company_name, c3.company_name, c4.company_name), 1, 50) as company_combo,
        -- Force extremely expensive operations to simulate 5+ second slow processing
        (SELECT COUNT(*) * SQRT(POW(q1.quote_id, 2) + POW(q2.quote_id, 2)) FROM quotes qx1 CROSS JOIN quotes qx2 CROSS JOIN quotes qx3 WHERE qx1.quote_id <= 100 AND qx2.quote_id <= 100 AND qx3.quote_id <= 100) as math_delay1,
        (SELECT SUM(q5.quote_id * SIN(q5.quote_id) * COS(q5.quote_id)) FROM quotes q5 CROSS JOIN quotes q51 CROSS JOIN quotes q52 WHERE q51.quote_id <= 50 AND q52.quote_id <= 50) as trig_delay1,
        (SELECT AVG(q6.total_amount * SQRT(q6.quote_id) * LOG(q6.quote_id + 1)) FROM quotes q6 CROSS JOIN quotes q61 CROSS JOIN quotes q62 WHERE q61.quote_id <= 50 AND q62.quote_id <= 50) as log_delay1,
        (SELECT MAX(LENGTH(REPEAT(c5.company_name, 10)) * q7.quote_id * RAND()) FROM quotes q7 JOIN customers c5 ON q7.customer_id = c5.customer_id CROSS JOIN quotes q71 CROSS JOIN quotes q72 WHERE q71.quote_id <= 30 AND q72.quote_id <= 30) as string_delay1,
        (SELECT MIN(POWER(q8.quote_id, 2) + POWER(c6.customer_id, 2) * RAND()) FROM quotes q8 JOIN customers c6 ON q8.customer_id = c6.customer_id CROSS JOIN quotes q81 CROSS JOIN quotes q82 WHERE q81.quote_id <= 30 AND q82.quote_id <= 30) as power_delay1,
        (SELECT COUNT(DISTINCT CONCAT(c7.company_name, '_', FLOOR(RAND() * 1000))) FROM customers c7 CROSS JOIN quotes q9 CROSS JOIN quotes q91 CROSS JOIN quotes q92 WHERE q9.quote_id <= 25 AND q91.quote_id <= 25 AND q92.quote_id <= 25) as distinct_delay1
      FROM quotes q1
      CROSS JOIN quotes q2 
      CROSS JOIN quotes q3
      CROSS JOIN quotes q4
      JOIN customers c1 ON q1.customer_id = c1.customer_id
      JOIN customers c2 ON q2.customer_id = c2.customer_id
      JOIN customers c3 ON q3.customer_id = c3.customer_id
      JOIN customers c4 ON q4.customer_id = c4.customer_id
      LEFT JOIN quote_items qi ON q1.quote_id = qi.quote_id
      LEFT JOIN services s ON qi.service_id = s.service_id
      WHERE date(q1.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND date(q2.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND date(q3.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND date(q4.quote_date) >= DATE_SUB(CURDATE(), INTERVAL 730 DAY)
      AND q1.quote_id != q2.quote_id
      AND q2.quote_id != q3.quote_id
      AND q3.quote_id != q4.quote_id
      AND q1.quote_id != q3.quote_id
      AND q1.quote_id != q4.quote_id
      AND q2.quote_id != q4.quote_id
      -- Force sorting on computed expensive fields
      ORDER BY memory_hog_field, case_combo, total_length DESC
      LIMIT 15
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
