## Product Catalog service failure

**Issue:** generates an error for `GetProduct` requests with the product ID: 
OLJCESPC7Z.

If you would like to follow along, navigate to src > flagd > demo.flagd.json,
and under `productCatalogFailure`, change the value for `defaultVariant` to `on`. 
Save the file, then restart the app. 

Wait a few minutes for the load generator to generate new data; you will pretty
quickly see that the error rates for a couple services have increased. First, go
to the `productcatalogservice` entity in your New Relic account and click on `Errors 
inbox`:

<img width="1401" alt="demo-productcatalogservice-01" src="https://github.com/user-attachments/assets/0105da4b-67d0-4ffe-96d7-fc34b163e6d5">

(In case you are wondering why the Error rate chart next to the Error count chart
appears empty, click on the `...` and select `View query`. You'll see that
this chart is querying for HTTP status code 500. Since this entity isn't 
reporting any 500s, this chart is empty.)

Select the error group `oteldemo.ProductCatalogService/GetProduct`, which will open up 
the error group summary and confirm that the feature flag was enabled:

<img width="1460" alt="demo-productcatalogservice02" src="https://github.com/user-attachments/assets/818f7340-340b-4489-961e-849653520d86">

(Note that there are no logs for this service at this time; per this [
table](https://opentelemetry.io/docs/demo/telemetry-features/log-coverage/), logs have not yet been 
added for `productcatalogservice`.)

Scroll down to `Attributes`, and you can see the attribute `app.product.id` with 
the value `OLJCESPC7Z` was captured:

<img width="1453" alt="demo-productcatalogservice03" src="https://github.com/user-attachments/assets/c4149479-9274-4e20-abb6-1c1db97819d6">

This in itself is not particularly interesting; head on over to the `checkoutservice`
entity and click on `Errors inbox`. You'll see an error group named 
`oteldemo.CheckoutService/PlaceOrder`, with the message `failed to prepare order: 
failed to get product #"OLJCESPC7Z"`:

<img width="1404" alt="demo-checkoutservice01" src="https://github.com/user-attachments/assets/a08c1ca3-376a-48b1-b154-095925668663">

Click on the blue icon under `Distributed Trace`:

<img width="1471" alt="demo-checkoutservice02" src="https://github.com/user-attachments/assets/2c0b69b2-a227-4d64-884c-93a17690dbc9">

You'll see a distributed trace that includes an entity map, showing you how the
error you enabled with the feature flag affected upstream services:

<img width="1333" alt="demo-checkoutservice03" src="https://github.com/user-attachments/assets/d21365d7-4fb3-4ecc-9719-9fb503f2b476">

Click on the "Errors" dropdown menu and select the `checkoutservice` span named
`oteldemo.CheckoutService/PlaceOrder`:

<img width="954" alt="demo-checkoutservice04" src="https://github.com/user-attachments/assets/54402a1e-c6b8-41fe-9c59-bdff62952d24">

On the right-hand panel, click on `View span events` to view more details about
the span event that was captured:

<img width="1330" alt="demo-checkoutservice-05" src="https://github.com/user-attachments/assets/06a29ac2-9492-4a0e-8f58-63d4f48c51b9">

<img width="1468" alt="demo-checkoutservice06" src="https://github.com/user-attachments/assets/dbf7100a-c831-4392-8c8e-ac19e4d95c97">
