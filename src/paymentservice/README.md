# Read Me

Get the name of the `paymentservice` container using the command

```shell
docker compose ps
```

Check the health of the service using a similar command to the following

```shell
docker inspect --format "{{json .State.Health }}" opentelemetry-demo-webstore-paymentservice-1
```

You should see output similar to the following when starting

```json
{
    "Status": "starting",
    "FailingStreak": 0,
    "Log": []
}
```

then after it is running

```json
{
    "Status": "healthy",
    "FailingStreak": 0,
    "Log": [
        {
            "Start": "2022-06-02T22:10:51.351468541Z",
            "End": "2022-06-02T22:10:51.49512054Z",
            "ExitCode": 0,
            "Output": "status: SERVING\n"
        }
    ]
}
```
