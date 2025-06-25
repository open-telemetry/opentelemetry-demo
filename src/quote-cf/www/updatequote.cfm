<cfscript>

  myQuery = queryExecute(
   "SELECT q.quote_id, q.quote_number, q.status, q.total_amount,
           c.company_name, c.contact_name, c.email
    FROM quotes q
    JOIN customers c ON q.customer_id = c.customer_id
    WHERE q.status = 'draft'
    ORDER BY q.quote_date DESC
    LIMIT 5",
  {},
  {datasource = "mysql"}
    );

  sleep(randRange(0,150,'SHA1PRNG')+400);

  errors = createObject("component", "errors");
  int = randRange(1,100,'SHA1PRNG');

  // use for profiler on resource example
  //This will cause a timeout and large time in CFDUMP and file system
  if (int lt 15) {
    errors.handle();
  }

  //cfhttp(method="GET", charset="utf-8", url="https://some-random-api.ml/animal/kangaroo/", result="result") {
    //cfhttpparam(name="q", type="url", value="cfml");
    //}
</cfscript>
