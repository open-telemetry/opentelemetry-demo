![](fluentbit.png)

## Fluent-bit 

Fluent-bit is a lightweight and flexible data collector and forwarder, designed to handle a large volume of log data in real-time.
It is an open-source projectpart of the Cloud Native Computing Foundation (CNCF). and has gained popularity among developers for simplicity and ease of use.

Fluent-bit is designed to be lightweight, which means that it has a small footprint and can be installed on resource-constrained environments like embedded systems or containers. It is written in C language, making it fast and efficient, and it has a low memory footprint, which allows it to consume minimal system resources.

Fluent-bit is a versatile tool that can collect data from various sources, including files, standard input, syslog, and TCP/UDP sockets. It also supports parsing different log formats like JSON, Apache, and Syslog. Fluent-bit provides a flexible configuration system that allows users to tailor their log collection needs, which makes it easy to adapt to different use cases.

One of the main advantages of Fluent-bit is its ability to forward log data to various destinations, including Opensearch, InfluxDB, and Kafka. Fluent-bit provides multiple output plugins that allow users to route their log data to different destinations based on their requirements. This feature makes Fluent-bit ideal for distributed systems where log data needs to be collected and centralized in a central repository.

Fluent-bit also provides a powerful filtering mechanism that allows users to manipulate log data in real-time. It supports various filter plugins, including record modifiers, parsers, and field extraction. With these filters, users can parse and enrich log data, extract fields, and modify records before sending them to their destination.

## Setting Up Fluent-bit agent 

For setting up a fluent-bit agent on Nginx, please follow the next instructions

- Install Fluent-bit on the Nginx server. You can download the latest package from the official Fluent-bit website or use your package manager to install it.

- Once Fluent-bit is installed, create a configuration file named fluent-bit.conf in the /etc/fluent-bit/ directory. Add the following configuration to the file:

```text
[SERVICE]
    Flush        1
    Log_Level    info
    Parsers_File parsers.conf

[Filter]
    Name    lua
    Match   *
    code    function cb_filter(a,b,c)local d={}local e=os.date("!%Y-%m-%dT%H:%M:%S.000Z")d["observerTime"]=e;d["body"]=c.remote.." "..c.host.." "..c.user.." ["..os.date("%d/%b/%Y:%H:%M:%S %z").."] \""..c.method.." "..c.path.." HTTP/1.1\" "..c.code.." "..c.size.." \""..c.referer.."\" \""..c.agent.."\""d["trace_id"]="102981ABCD2901"d["span_id"]="abcdef1010"d["attributes"]={}d["attributes"]["data_stream"]={}d["attributes"]["data_stream"]["dataset"]="nginx.access"d["attributes"]["data_stream"]["namespace"]="production"d["attributes"]["data_stream"]["type"]="logs"d["event"]={}d["event"]["category"]={"web"}d["event"]["name"]="access"d["event"]["domain"]="nginx.access"d["event"]["kind"]="event"d["event"]["result"]="success"d["event"]["type"]={"access"}d["http"]={}d["http"]["request"]={}d["http"]["request"]["method"]=c.method;d["http"]["response"]={}d["http"]["response"]["bytes"]=tonumber(c.size)d["http"]["response"]["status_code"]=c.code;d["http"]["flavor"]="1.1"d["http"]["url"]=c.path;d["communication"]={}d["communication"]["source"]={}d["communication"]["source"]["address"]="127.0.0.1"d["communication"]["source"]["ip"]=c.remote;return 1,b,d end
    call    cb_filter

[INPUT]
    Name              tail
    Path              /var/log/nginx/access.log
    Tag               nginx.access
    DB                /var/log/flb_input.access.db
    Mem_Buf_Limit     5MB
    Skip_Long_Lines   On

[OUTPUT]
    Name        opensearch
    Match       nginx.*
    Host        <OSS_HOST>
    Port        <OSS_PORT>
    Index       sso_nginx-access-%Y.%m.%d
```
Here, we specify the input plugin as tail, set the path to the Nginx access log file, and specify a tag to identify the logs in Fluent-bit. We also set some additional parameters such as memory buffer limit and skipping long lines.

For the output, we use the `opensearch` plugin to send the logs to Opensearch. We specify the Opensearch host, port, and index name.

   - Modify the Opensearch host and port in the configuration file to match your Opensearch installation.
   - Depending on the system where Fluent Bit is installed:
     - Start the Fluent-bit service by running the following command:

```text
sudo systemctl start fluent-bit
```
- Verify that Fluent-bit is running by checking its status:
```text
sudo systemctl status fluent-bit
```