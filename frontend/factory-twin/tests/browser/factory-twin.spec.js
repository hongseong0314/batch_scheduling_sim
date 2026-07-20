import { expect, test } from "@playwright/test";

async function openTwin(page, request) {
  await request.post("/api/v2/simulation/reset", { data: {} });
  await page.goto("/mes#factory-twin");
  await expect(page.locator("body")).toHaveClass(/factory-twin-page-active/);
  await expect(page.locator("#factory-twin-connection")).toHaveText("LIVE");
  await expect(page.locator("#factory-twin-canvas canvas")).toHaveCount(1);
}

async function webglPixelEvidence(page) {
  return page.locator("#factory-twin-canvas canvas").evaluate(async canvas => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const gl = canvas.getContext("webgl2");
    if (!gl) return { webgl: false, colors: 0, opaque: 0 };
    const pixel = new Uint8Array(4);
    const colors = new Set();
    let opaque = 0;
    for (let row = 1; row <= 12; row += 1) {
      for (let column = 1; column <= 24; column += 1) {
        const x = Math.min(canvas.width - 1, Math.floor((canvas.width * column) / 25));
        const y = Math.min(canvas.height - 1, Math.floor((canvas.height * row) / 13));
        gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
        colors.add(Array.from(pixel).join(","));
        if (pixel[3] > 0) opaque += 1;
      }
    }
    return { webgl: true, colors: colors.size, opaque };
  });
}

test("desktop scene is nonblank, framed, live, and interactive", async ({ page, request }) => {
  const browserErrors = [];
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("console", message => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  await openTwin(page, request);

  const canvasBox = await page.locator("#factory-twin-canvas canvas").boundingBox();
  expect(canvasBox.width).toBeGreaterThan(700);
  expect(canvasBox.height).toBeGreaterThan(400);
  const pixelEvidence = await webglPixelEvidence(page);
  expect(pixelEvidence.webgl).toBe(true);
  expect(pixelEvidence.opaque).toBeGreaterThan(250);
  expect(pixelEvidence.colors).toBeGreaterThan(5);
  expect((await page.locator("#factory-twin-canvas canvas").screenshot()).byteLength).toBeGreaterThan(10_000);

  const frames = await page.evaluate(async () => {
    let count = 0;
    const started = performance.now();
    await new Promise(resolve => {
      const tick = now => {
        count += 1;
        if (now - started >= 500) resolve();
        else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    return count;
  });
  expect(frames).toBeGreaterThan(20);

  await request.post("/api/v2/harness/run-cycle", { data: { target_stage: "AUTO" } });
  await expect(page.locator("#factory-twin-status-summary")).toContainText("5/11 processing");
  await page.evaluate(() => {
    const app = window.factoryTwinApp;
    app.select(
      { entityType: "equipment", entityId: "A_0" },
      app.topology.entities.get("equipment:A_0"),
    );
  });
  await expect(page.locator("#factory-twin-inspector")).toBeVisible();
  await expect(page.locator("#factory-twin-entity-title")).toHaveText("LITHO-01");
  await page.keyboard.press("Escape");
  await expect(page.locator("#factory-twin-inspector")).toBeHidden();
  await page.evaluate(() => {
    const app = window.factoryTwinApp;
    app.select(
      { entityType: "equipment", entityId: "A_0" },
      app.topology.entities.get("equipment:A_0"),
    );
  });
  await page.getByRole("button", { name: "Machine Detail", exact: true }).click();
  await expect(page).toHaveURL(/#machine$/);
  await expect(page.locator("#machine-subtitle")).toContainText("LITHO-01");
  expect(browserErrors).toEqual([]);
});

test("carrier follows authoritative progress and reconnects after a dropped socket", async ({ page, request }) => {
  await openTwin(page, request);
  for (let cycle = 0; cycle < 21; cycle += 1) {
    await request.post("/api/v2/harness/run-cycle", { data: { target_stage: "AUTO" } });
  }
  await expect(page.locator("#factory-twin-transfer-summary")).toContainText("1 carriers");
  await page.waitForTimeout(350);
  const routeHighlight = await page.evaluate(() => {
    const app = window.factoryTwinApp;
    const entry = app.materialFlow.carriers.values().next().value;
    app.select(
      { entityType: "carrier", entityId: entry.state.carrier_id },
      entry.group,
    );
    return app.topology.routes.get(entry.state.route_id).mesh.material.color.getHexString();
  });
  expect(routeHighlight).toBe("0f62fe");
  const beforeProgress = await page.evaluate(() => {
    const entry = window.factoryTwinApp.materialFlow.carriers.values().next().value;
    return entry.state.progress;
  });
  await request.post("/api/v2/harness/run-cycle", { data: { target_stage: "AUTO" } });
  await expect.poll(async () => page.evaluate(previousProgress => {
    const entry = window.factoryTwinApp.materialFlow.carriers.values().next().value;
    return Math.max(entry.state.progress, entry.targetProgress) - previousProgress;
  }, beforeProgress), { timeout: 2_000 }).toBeGreaterThan(0.1);

  const started = Date.now();
  await page.evaluate(() => window.factoryTwinApp.websocket.close());
  await expect(page.locator("#factory-twin-connection")).toHaveText("POLLING");
  await expect(page.locator("#factory-twin-connection")).toHaveText("LIVE", { timeout: 2_000 });
  expect(Date.now() - started).toBeLessThan(2_000);
});

test("mobile layout uses an overlay inspector and survives repeated page entry", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openTwin(page, request);
  const layout = await page.evaluate(() => ({
    innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    canvas: document.querySelector("#factory-twin-canvas").getBoundingClientRect().toJSON(),
  }));
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.innerWidth);
  expect(layout.canvas.width).toBeGreaterThan(360);
  expect(layout.canvas.height).toBeGreaterThan(480);

  await page.evaluate(() => {
    const app = window.factoryTwinApp;
    app.select(
      { entityType: "equipment", entityId: "A_0" },
      app.topology.entities.get("equipment:A_0"),
    );
  });
  const inspector = await page.locator("#factory-twin-inspector").boundingBox();
  expect(inspector.x).toBeGreaterThanOrEqual(0);
  expect(inspector.x + inspector.width).toBeLessThanOrEqual(390);
  expect(inspector.y + inspector.height).toBeLessThanOrEqual(844);

  await page.locator("#factory-twin-inspector-close").click();
  for (let cycle = 0; cycle < 20; cycle += 1) {
    await page.evaluate(() => { location.hash = "fab"; });
    await page.evaluate(() => { location.hash = "factory-twin"; });
  }
  await expect(page.locator("#factory-twin-connection")).toHaveText("LIVE");
  await expect(page.locator("#factory-twin-canvas canvas")).toHaveCount(1);
});
