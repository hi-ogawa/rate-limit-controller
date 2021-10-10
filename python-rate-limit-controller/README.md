- async utilities
  - retry
  - queue
  - rate limit controller

```sh
$ time poetry run python -m src < ../data/test1.json > ../data/test1-out.json
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
