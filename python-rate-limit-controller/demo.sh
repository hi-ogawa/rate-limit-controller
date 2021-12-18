#!/bin/bash

demo_count="${demo_count:-10}"
demo_datadir="data/"

for ((i = 1; i <= $demo_count; i++)); do
  curl "http://localhost:8080/bsc/api?action=txlist&address=0x2170ed0880ac9a755fd29b2688956bd959f933f8&module=account&startblock=$i&page=1&offset=5000&sort=asc" > "$demo_datadir/test-$i.json" &
done

for job in `jobs -p`; do
  wait "$job"
done
echo ":: DONE"
