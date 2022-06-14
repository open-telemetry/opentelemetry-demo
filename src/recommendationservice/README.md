# Read Me

1. Expose the service's port to the localhost by modifying `/compose.yml`

    ```diff
    - - "${RECOMMENDATION_SERVICE_PORT}"
    + - "${RECOMMENDATION_SERVICE_PORT}:${RECOMMENDATION_SERVICE_PORT}"
    ```

1. To run the `./client.py` you must compile `/pb/demo.proto` into python code

    ```shell
    python -m grpc_tools.protoc -I./pb/ --python_out=./src/recommendationservice/ --grpc_python_out=./src/recommendationservice/ ./pb/demo.proto
    python ./src/recommendationservice/client.py
    ```

1. You should see output similar to the following

    ```json
    {
        "asctime": "2022-06-02 13:42:44,793",
        "levelname": "INFO",
        "name": "recommendationservice-server",
        "filename": "client.py",
        "lineno": 35,
        "otelTraceID": "00000000000000000000000000000000",
        "otelSpanID": "0000000000000000",
        "message": "product_ids: \"6E92ZMYYFZ\"\nproduct_ids: \"OLJCESPC7Z\"\nproduct_ids: \"LS4PSXUNUM\"\nproduct_ids: \"2ZYFJ3GM2N\"\nproduct_ids: \"1YMWWN1N4O\"\n"
    }
    ```
