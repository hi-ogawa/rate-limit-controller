# Rate limit controller

Build

```sh
$ npx tsc --watch
```

Test

```sh
$ export API_KEY=...

$ time node main.js < data/test2.json > data/test2-out.json
count = 22

...

real    0m6,989s
user    0m0,581s
sys     0m0,101s

$ time node main.js < data/test1.json > data/test1-out.json
count = 991

...

real    4m38,076s
user    0m14,138s
sys     0m2,138s
```
