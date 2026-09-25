// Exercise the actual external page script with a minimal DOM and controlled network.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { execFileSync } = require("node:child_process");
const { fileURLToPath } = require("node:url");
const { test } = require("node:test");
const vm = require("node:vm");

const root = fileURLToPath(new URL("../", `file://${__filename}`));
const html = execFileSync(process.env.PYTHON || "python3", ["-c",
  "from scripts.build_site import ROOT, render_page; print(render_page(ROOT))"
], { cwd: root, encoding: "utf8" });
const script = readFileSync(new URL("../assets/main.js", `file://${__filename}`), "utf8");
const repos = [...html.matchAll(/data-repo="([^"]+)"/g)].map(m => m[1]);
const snapshot = () => ({
  generatedAt: "2026-09-25T23:17:00Z",
  projects: Object.fromEntries(repos.map(repo => [repo, {
    sha: "abcdef1", date: "2026-09-25", msg: '<img src=x onerror="alert(1)"> 中文', count: 123,
  }])),
});

async function runPage(fetcher, { hover = false, reduce = false, timeout = false } = {}) {
  function element() {
    const children = new Map();
    return {
      textContent: "", offsetTop: 0, offsetHeight: 10,
      style: { setProperty() {} }, classList: { add() {}, remove() {} },
      handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn; },
      querySelector(name) {
        if (!children.has(name)) children.set(name, element());
        return children.get(name);
      },
      appendChild(child) { this.commit = child; },
    };
  }
  const links = repos.map(repo => Object.assign(element(), {
    dataset: { repo, sha: "1111111", date: "2020-01-01", msg: "Fallback" },
  }));
  const requests = [], timers = new Map(), warnings = [];
  const context = {
    document: { querySelectorAll: () => links, createElement: element,
      getElementById: element, documentElement: { scrollHeight: 1000 } },
    matchMedia: query => ({ matches: query.includes("reduced-motion") ? reduce : hover }),
    fetch: (url, options) => { requests.push({ url, options }); return fetcher(url, options); },
    AbortController, console: { warn: (...args) => warnings.push(args) },
    setTimeout(fn, ms) { const id = timers.size + 1; timers.set(id, { fn, ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
    setInterval() { return 1; }, clearInterval() {},
    addEventListener() {}, requestAnimationFrame(fn) { fn(); }, innerHeight: 700, scrollY: 0,
  };
  vm.runInNewContext(script, context);
  if (timeout) [...timers.values()].find(timer => timer.ms === 10000).fn();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "./data/projects.json");
  assert.equal(requests[0].options.cache, "no-cache");
  assert.equal(timers.size, 0);
  return { links, requests, warnings };
}

test("one same-origin fetch updates every project and treats messages as text", async () => {
  const { links, warnings } = await runPage(async () => ({ ok: true, json: async () => snapshot() }));
  for (const link of links) {
    assert.equal(link.dataset.sha, "abcdef1");
    assert.equal(link.querySelector(".n").textContent, 123);
    assert.equal(link.commit.querySelector(".msg").textContent, snapshot().projects[link.dataset.repo].msg + "  · 2026-09-25");
  }
  assert.equal(warnings.length, 0);
});

test("network, HTTP, JSON and incomplete-snapshot failures retain every fallback", async () => {
  const partial = snapshot();
  delete partial.projects[repos.at(-1)];
  const invalid = snapshot();
  invalid.projects[repos.at(-1)].count = -1;
  for (const fetcher of [
    async () => { throw new Error("offline"); },
    async () => ({ ok: false, status: 404 }),
    async () => ({ ok: true, json: async () => { throw new Error("bad JSON"); } }),
    async () => ({ ok: true, json: async () => partial }),
    async () => ({ ok: true, json: async () => invalid }),
  ]) {
    const { links, warnings } = await runPage(fetcher);
    assert.ok(links.every(link => link.dataset.sha === "1111111"));
    assert.equal(warnings.length, 1);
  }
});

test("timeout aborts the request and retains fallback", async () => {
  const { links, requests } = await runPage((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener("abort", () => reject(new Error("aborted")));
  }), { timeout: true });
  assert.equal(requests[0].options.signal.aborted, true);
  assert.ok(links.every(link => link.dataset.sha === "1111111"));
});

test("hover handlers still work and reduced-motion/mobile use the filled text", async () => {
  for (const [hover, reduce] of [[true, false], [true, true], [false, false]]) {
    const { links } = await runPage(async () => ({ ok: true, json: async () => snapshot() }), { hover, reduce });
    for (const link of links) {
      assert.equal(Boolean(link.handlers.mouseenter), hover && !reduce);
      if (hover && !reduce) {
        link.handlers.mouseenter();
        link.handlers.mouseleave();
      }
      assert.ok(link.commit.querySelector(".msg").textContent.includes("中文"));
    }
  }
});
