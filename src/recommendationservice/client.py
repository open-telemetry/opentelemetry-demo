#!/usr/bin/python
#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Python
import os

# Pip
import dotenv
import grpc

# Local
import demo_pb2
import demo_pb2_grpc
from logger import getJSONLogger

logger = getJSONLogger('recommendationservice-server')

if __name__ == "__main__":
    dotenv.load_dotenv()

    # set up server stub
    port = os.getenv('RECOMMENDATION_SERVICE_PORT')
    channel = grpc.insecure_channel(f'localhost:{port}')
    stub = demo_pb2_grpc.RecommendationServiceStub(channel)

    # form request
    request = demo_pb2.ListRecommendationsRequest(user_id="test", product_ids=["test"])

    # make call to server
    response = stub.ListRecommendations(request)
    logger.info(response)
