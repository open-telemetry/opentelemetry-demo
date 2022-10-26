# Copyright 2020 Google LLC
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

FROM python:3.10

WORKDIR /usr/src/app/

COPY ./src/recommendationservice/ ./
COPY ./pb/ ./proto/

RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt

RUN opentelemetry-bootstrap -a install

# add files into working directory
RUN python -m pip install grpcio-tools==1.48.2
RUN python -m grpc_tools.protoc -I=./proto/ --python_out=./ --grpc_python_out=./ ./proto/demo.proto

EXPOSE ${RECOMMENDATION_SERVICE_PORT}
ENTRYPOINT [ "opentelemetry-instrument", "python", "recommendation_server.py" ]
