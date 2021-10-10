import fetch from "node-fetch";
import * as fs from "fs";
import * as assert from "assert/strict";
import { fileURLToPath } from "url";
import * as process from "process";
import promiseRetry from "promise-retry";
import type { PromiseType } from "utility-types";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class Queue<T> {
  private xs: T[] = [];
  private resolves: (() => void)[] = [];

  async get(): Promise<T> {
    await new Promise((resolve) => {
      this.resolves.push(resolve as () => void);
    });
    return this.xs.shift()!;
  }

  push(x: T) {
    this.xs.push(x);
    if (this.resolves.length > 0) {
      const resolve = this.resolves.shift()!;
      resolve();
    }
  }
}

function now(): number {
  return Date.now();
}

interface Log {
  id: number;
  begin: number;
  inflight: boolean;
}

class RateLimitController {
  private logs: Log[] = [];
  private id: number = 0;
  private signal: Queue<void> = new Queue();

  constructor(
    private readonly rate: number,
    private readonly interval: number,
    private readonly jitter = 0
  ) {}

  private get inflightLogs(): Log[] {
    return this.logs.filter((log) => log.inflight);
  }

  async onBegin() {
    while (true) {
      assert.ok(this.inflightLogs.length <= this.rate);

      if (this.inflightLogs.length >= this.rate) {
        // Wait for the signal of inflight count decrease
        await this.signal.get();

        // Continue waiting
        if (this.inflightLogs.length >= this.rate) continue;
      }

      // Cleanup unnecessary logs
      const t = now();
      this.logs = this.logs.filter(
        (log) => log.inflight || log.begin >= t - this.interval - this.jitter
      );

      // Sleep to satisfy rate limit
      let t_last = Number.NEGATIVE_INFINITY;
      let dt_jitter = 0;
      if (this.logs.length >= this.rate) {
        t_last = this.logs[this.logs.length - this.rate].begin!;
        dt_jitter = Math.random() * this.jitter;
      }
      const dt = Math.max(0, t_last + this.interval - t);
      await sleep(dt + dt_jitter);

      // Continue waiting
      if (this.inflightLogs.length >= this.rate) continue;

      break;
    }

    const id = this.id++;
    this.logs.push({
      id: id,
      begin: now(),
      inflight: true,
    });
    return id;
  }

  onEnd(id: number) {
    const log = this.logs.find((log) => log.id === id);
    assert.ok(log);
    log.inflight = false;
    this.signal.push();
  }

  decorate<F extends (...args: any[]) => any>(f: F) {
    return async (
      ...args: Parameters<F>
    ): Promise<PromiseType<ReturnType<F>>> => {
      const id = await this.onBegin();
      const result = await f(...args);
      this.onEnd(id);
      return result;
    };
  }
}

const API_KEY = process.env.API_KEY as string;
const API_ENDPOINT = "https://api.bscscan.com/api";
assert.ok(API_KEY);

let count = 0;

async function request(txhash: string): Promise<Record<string, string>> {
  console.error(`BEGIN (${txhash.slice(0, 10)})`, new Date(), ++count);

  const params = {
    module: "proxy",
    action: "eth_getTransactionByHash",
    txhash: txhash,
    apikey: API_KEY,
  };
  const url = `${API_ENDPOINT}?${new URLSearchParams(params).toString()}`;
  const res = await fetch(url);

  console.error(`END   (${txhash.slice(0, 10)})`, new Date(), --count);

  if (!res.ok) {
    const text = await res.text();
    throw Error(`fetch error: status = ${res.status}, text = ${text}`);
  }
  const json: any = await res.json();
  if (json.status === "0") {
    throw Error(`api error: ${JSON.stringify(json)}`);
  }
  return json.result;
}

interface Data {
  transactions: { txnHash: string }[];
}

// const RATE = 1, INTERVAL = 0, JITTER = 0;
// const RATE = 2, INTERVAL = 500, JITTER = 0;
// const RATE = 4, INTERVAL = 1500, JITTER = 0;
// const RATE = 5, INTERVAL = 1500, JITTER = 500;
// const RATE = 5, INTERVAL = 1700, JITTER = 300;
// const RATE = 5, INTERVAL = 1000, JITTER = 1000;
const RATE = 5,
  INTERVAL = 1200,
  JITTER = 300;

function retryDecorate<F extends (...args: any[]) => any>(
  f: F,
  options: any = {}
) {
  return async function (
    ...args: Parameters<F>
  ): Promise<PromiseType<ReturnType<F>>> {
    return promiseRetry(options, (retry: any) =>
      f(...args).catch((e: Error) => {
        console.error("retry", e);
        retry(e);
      })
    );
  };
}

async function main() {
  const controller = new RateLimitController(RATE, INTERVAL, JITTER);
  const requestDecorated = controller.decorate(retryDecorate(request));

  const data: Data = JSON.parse(fs.readFileSync(process.stdin.fd).toString());
  const hashes = data.transactions.map((txn) => txn.txnHash);
  console.error(`count = ${hashes.length}`);

  const results = await Promise.all(hashes.map(requestDecorated));

  fs.writeFileSync(process.stdout.fd, JSON.stringify(results, null, 2));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}
