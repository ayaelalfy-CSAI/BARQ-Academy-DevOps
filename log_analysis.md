# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

## 1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?

- `in the application.log and the access.log files: ` 

`script for UTC interval` :  
```bash       
python3 -c "
import json                                         
for f in ['logs/access.log','logs/application.log']:
    times=[]
    with open(f) as fh:
        for line in fh:
            try:                                           
                times.append(json.loads(line)['timestamp'])
            except: pass
    print(f, 'from', min(times), 'to', max(times))
"
```

`Answer`:
logs/access.log from 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z
logs/application.log from 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z


`script for valid,mailformed and duplicated` :  
```bash
python3 -c "
import json
for f in ['logs/access.log','logs/application.log']:
    total = malformed = 0
    with open(f) as fh:
        for line in fh:
            total += 1
            try:
                json.loads(line)
            except:
                malformed += 1
    valid = total - malformed
    print(f, 'total:', total, 'valid:', valid, 'malformed:', malformed)
"
```
`Answer`:
logs/access.log total: 726 valid: 725 malformed: 1
logs/application.log total: 730 valid: 729 malformed: 1


- `in the error.log file:`

`script` :
```bash
head -1 logs/error.log | grep -oP '^\S+ \S+'
tail -2 logs/error.log | head -1 | grep -oP '^\S+ \S+'

python3 -c "
import re
pattern = re.compile(r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[\w+\]')
total = valid = malformed = 0
with open('logs/error.log') as fh:
    for line in fh:
        total += 1
        if pattern.match(line):
            valid += 1
        else:
            malformed += 1
print('total:', total, 'valid:', valid, 'malformed:', malformed)
"
```
`Answer`:
2026/08/20 11:05:02
2026/08/20 11:26:47

total: 68 valid: 68 malformed: 0


## 2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?

`script`
```bash
python3 -c "
import json
ids=set()
with open('logs/access.log') as fh:
    for line in fh:
        try:
            ids.add(json.loads(line)['request_id'])
        except: pass
print('distinct request_id count:', len(ids))
"
```
`Answer`
distinct request_id count: 720


I deduplicated client requests using the `request_id` field from the access log. I extracted the `request_id` from each valid log entry and stored the IDs in a Python `set`, which automatically keeps only unique values. Therefore, if the same `request_id` appeared multiple times because the client retried the request, it was counted only once. Malformed lines or entries without a valid `request_id` were ignored during this step.

This means that each unique `request_id` represents one distinct client request, while repeated occurrences of the same `request_id` were treated as retries/duplicates and were not counted again.


## 3. What are the final client status counts and error rate? State your denominator.

`script`
```bash
python3 -c "
import json
from collections import Counter
c=Counter()
n=0
with open('logs/access.log') as fh:
    for line in fh:
        try:
            d=json.loads(line)
            c[d['status']]+=1
            n+=1
        except: pass
print(c)
errors=sum(v for k,v in c.items() if k>=400)
print('error rate:', errors, '/', n, '=', round(errors/n*100,2), '%')
"
```
`Answer`
Counter({200: 620, 503: 47, 502: 40, 404: 10, 504: 8})
error rate: 105 / 725 = 14.48 %


## 4. Which paths, time windows and backends account for the failures?

`script`
```bash
python3 -c "
import json
from collections import Counter
by_path=Counter(); by_backend=Counter()
with open('logs/access.log') as fh:
    for line in fh:
        try:
            d=json.loads(line)
            if d['status']>=400:
                by_path[d['path']]+=1
                by_backend[d.get('upstream','?')]+=1
        except: pass
print('by path:', by_path)
print('by backend:', by_backend)
"
```

`Answer`
by path: Counter({'/records': 26, '/counter': 26, '/ready': 23, '/missing': 10, '/health': 10, '/': 10})
by backend: Counter({'172.23.0.12:8080': 73, '172.23.0.11:8080': 32})


## 5. What are the median and p95 client latencies? State the percentile method and units.

`script`
```bash
python3 -c "
import json
import numpy as np

requests = {}

with open('logs/access.log') as fh:
    for line in fh:
        try:
            d = json.loads(line)

            request_id = d['request_id']
            request_time = float(d['request_time'])
            timestamp = d['timestamp']

            if (request_id not in requests or
                timestamp > requests[request_id]['timestamp']):
                requests[request_id] = {
                    'timestamp': timestamp,
                    'request_time': request_time
                }

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

times = [r['request_time'] for r in requests.values()]

if not times:
    print('No valid request_time values found.')
else:
    median = np.percentile(times, 50, method='linear')
    p95 = np.percentile(times, 95, method='linear')

    print('Distinct requests:', len(times))
    print('Median (p50) =', round(median, 6), 'seconds')
    print('P95 =', round(p95, 6), 'seconds')
    print('Percentile method: linear interpolation')
    print('Units: seconds')
"
```

`Answer`

Distinct requests: 720
Median (p50) = 0.054 seconds
P95 = 2.001 seconds
Percentile method: linear interpolation
Units: seconds


## 6. Which requests retried upstream? How many succeeded after retrying?

`script`
```bash
python3 -c "
import json
retried=0; succeeded=0             
with open('logs/access.log') as fh:
    for line in fh:
        try:
            d=json.loads(line)
            if ',' in str(d.get('upstream','')):
                retried+=1
                if d['status']<400: succeeded+=1
        except: pass                               
print('retried:', retried, 'succeeded after retry:', succeeded)
"
```

`Answer`
retried: 19 succeeded after retry: 19


## 7. Build an incident timeline using evidence from access, error AND application logs. 

`script for access.log`
```bash
python3 -c "
import json

with open('logs/access.log') as fh:
    for line in fh:
        try:
            d = json.loads(line)

            if d.get('status', 0) >= 400:
                print(
                    d.get('timestamp'),
                    '| ACCESS',
                    '| request_id:', d.get('request_id'),
                    '| path:', d.get('path'),
                    '| status:', d.get('status'),
                    '| upstream_status:', d.get('upstream_status'),
                    '| upstream:', d.get('upstream')
                )
        except (json.JSONDecodeError, KeyError):
            pass
"
```
`Answer`

`I will use it as an example`
{"timestamp":"2026-08-20T11:05:12.503Z","request_id":"lab-000126","method":"GET","path":"/records","status":502,"upstream":"172.23.0.12:8080","upstream_status":"502","request_time":0.003,"client":"192.0.2.24"}

`and then Ran` 
```bash
 grep 'lab-000126' logs/error.log
 ```
2026/08/20 11:05:12 [error] 31#31: *126 connect() failed (111: Connection refused) while connecting to upstream, request_id=lab-000126, request: "GET /records HTTP/1.1", upstream: "http://172.23.0.12:8080/records"

```bash
- grep 'lab-000126' logs/application.log
```
nothing output

`Incident Timeline`

- 11:05:12.503 UTC — `lab-000126`

  - The `access.log` shows a `GET /records` request that returned **HTTP 502**. The request was sent to upstream backend **172.23.0.12:8080**, with an upstream status of 502 and a request time of 0.003 seconds.
  - The `error.log` confirms that the reverse proxy could not connect to the upstream backend because the connection was **refused** while connecting to `172.23.0.12:8080/records`.
  - There is **no matching `lab-000126` entry in `application.log`**, so there is no application-level evidence for this specific request.
  - This indicates that the failure occurred **between the proxy and the upstream backend**, before the request could be processed by the application.


## 8. Show one correlated failed request and one successful request. Include IDs and timestamps.

`script for successful request`
```bash
python3 -c "
import json

with open('logs/access.log') as fh:
    for line in fh:
        try:
            d = json.loads(line)

            if d.get('status', 0) == 200:
                print(
                    d.get('timestamp'),
                    '| ACCESS',
                    '| request_id:', d.get('request_id'),
                    '| path:', d.get('path'),
                    '| status:', d.get('status'),
                    '| upstream_status:', d.get('upstream_status'),
                    '| upstream:', d.get('upstream')
                )
        except (json.JSONDecodeError, KeyError):
            pass
"
```
`select from the response` 
2026-08-20T11:29:07.558Z | ACCESS | request_id: lab-000700 | path: /ready | status: 200 | upstream_status: 200 | upstream: 172.23.0.12:8080

`and Ran`
```bash
 grep 'lab-000700' logs/application.log
 ```
{"timestamp": "2026-08-20T11:29:07.558Z", "level": "INFO", "event": "http_request", "request_id": "lab-000700", "instance_id": "app-02", "method": "GET", "path": "/ready", "status": 200, "duration_ms": 58.0}

```bash
 grep 'lab-000700' logs/error.log
```
nothing response


`script for failed request`
```bash
python3 -c "
import json

with open('logs/access.log') as fh:
    for line in fh:
        try:
            d = json.loads(line)

            if d.get('status', 0) >= 400:
                print(
                    d.get('timestamp'),
                    '| ACCESS',
                    '| request_id:', d.get('request_id'),
                    '| path:', d.get('path'),
                    '| status:', d.get('status'),
                    '| upstream_status:', d.get('upstream_status'),
                    '| upstream:', d.get('upstream')
                )
        except (json.JSONDecodeError, KeyError): "

```
  

`select from response`
2026-08-20T11:03:17.578Z | ACCESS | request_id: lab-000080 | path: /missing | status: 404 | upstream_status: 404 | upstream: 172.23.0.12:8080

`and Ran`
```bash
 grep 'lab-000080' logs/application.log
```
{"timestamp": "2026-08-20T11:03:17.578Z", "level": "WARN", "event": "http_request", "request_id": "lab-000080", "instance_id": "app-02", "method": "GET", "path": "/missing", "status": 404, "duration_ms": 78.0}

```bash
 grep 'lab-000080' logs/error.log
```
nothing

`this meaning`
lab-000080 was successfully proxied by NGINX to the Flask application. The Flask application returned HTTP 404 because `/missing` was not found. NGINX correctly returned this response to the client


## 9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?

`Proxy/connectivity issue: `
 lab-000126 returned HTTP 502. The error.log shows that NGINX failed to connect to the upstream 172.23.0.12:8080 with “connection refused.” There is also no matching lab-000126 entry in application.log, proving that the request did not reach the Flask application.


`Example`
```bash
 grep 'lab-000126' logs/access.log
 ```
{"timestamp":"2026-08-20T11:05:12.503Z","request_id":"lab-000126","method":"GET","path":"/records","status":502,"upstream":"172.23.0.12:8080","upstream_status":"502","request_time":0.003,"client":"192.0.2.24"}

```bash
grep 'lab-000126' logs/application.log
```
nothing

```bash
grep 'lab-000126' logs/error.log
```
2026/08/20 11:05:12 [error] 31#31: *126 connect() failed (111: Connection refused) while connecting to upstream, request_id=lab-000126, request: "GET /records HTTP/1.1", upstream: "http://172.23.0.12:8080/records"


`Application issue: `
lab-000080 reached the Flask application successfully, but the application returned HTTP 404 for GET /missing. The same request ID and timestamp appear in both access.log and application.log, while there is no NGINX error. This proves that NGINX successfully proxied the request and the 404 response came from the application.


`Example `
```bash
grep 'lab-000080' logs/application.log
```
{"timestamp": "2026-08-20T11:03:17.578Z", "level": "WARN", "event": "http_request", "request_id": "lab-000080", "instance_id": "app-02", "method": "GET", "path": "/missing", "status": 404, "duration_ms": 78.0}

```bash
 grep 'lab-000080' logs/error.log
```
nothing

```bash
 grep 'lab-000080' logs/access.log
 ```
{"timestamp":"2026-08-20T11:03:17.578Z","request_id":"lab-000080","method":"GET","path":"/missing","status":404,"upstream":"172.23.0.12:8080","upstream_status":"404","request_time":0.078,"client":"192.0.2.24"}



## 10. What do the logs not prove? What would you check next in a running environment?

`Answer`
The logs do not prove the exact root cause of the failures. For example, “connection refused” proves that NGINX could not connect to the upstream at that time, but it does not prove whether the application was down, restarting, not listening on port 8080, or there was a network/service configuration problem.

The logs also do not prove the internal cause of an application error or whether a dependency such as a database or Redis was responsible.

In a running environment, I would check:

- Application/container/pod status and restart history.
- Application logs and stack traces.
- Whether the application is listening on port 8080.
- NGINX upstream and configuration.
- Service endpoints and DNS resolution.
- Network connectivity between NGINX and the application.
- Database/Redis health and connectivity.

This would help identify the actual root cause rather than relying only on the log symptoms.


## Commands / scripts
## Results
## Timeline and correlated examples
## Conclusions and limits
