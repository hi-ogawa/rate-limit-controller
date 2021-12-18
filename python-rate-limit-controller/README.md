- async utilities
  - retry
  - queue
  - rate limit controller

```sh
$ time poetry run python -m src < ../data/test2.json > ../data/test2-out.json
...
real    0m6,938s
user    0m0,959s
sys     0m0,144s

$ time poetry run python -m src < ../data/test1.json > ../data/test1-out.json
...
real    3m59,296s
user    0m16,203s
sys     0m2,289s
```

```sh
#
# Estimating performance
#
#  s0              = average request latency (in seconds)
#  (x1, x2, ...xn) = per-second rate limit of n keys
#  m               = number of requests
#             ⇓⇓⇓
#  total seconds = s0 + m / (x1 + ... + xn)  (i.e. per-second rate limit is a sum of rate limits of all keys)
#
# NOTE
#  - When you have more connections simultaneously, the latency becomes larger
#

# start server
export APIKEYS="..."
poetry run python -m src.resource_scheduler

# start client
export demo_count=100 && time bash demo.sh
```
