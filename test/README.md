Testing services directly with a gRPC clients.

1. Start the services you want to test with `docker compose up <service>`
1. Run `npm test` or `npx ava <filename>` if you want to test a specific file or `npx ava --match='*payment*'`
