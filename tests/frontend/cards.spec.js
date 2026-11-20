import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: new Date("2026-09-29T22:30:00Z") });
  await page.goto("/");
  await page.waitForFunction(() => window.ready);
});

test("four discoverable presets, stubs, suggestions and repeat registration", async ({ page }) => {
  const result = await page.evaluate(async () => {
    await import("/setlistfm-cards.js?again=1");
    const hass = window.fixtureHass();
    return window.customCards.map((metadata) => {
      const type = customElements.get(metadata.type);
      return {
        name: metadata.name, preview: metadata.preview,
        stub: type.getStubConfig(hass), empty: type.getStubConfig({states:{}}),
        preferred: type.getStubConfig(hass, ["sensor.sam_gigs"]).entity,
        editor: type.getConfigElement().localName,
        suggestion: metadata.getEntitySuggestion(hass, "sensor.sam_gigs")?.config.entity,
        unrelated: metadata.getEntitySuggestion(hass, "sensor.living_room_temperature"),
      };
    });
  });
  expect(result).toHaveLength(4);
  expect(result.map((item) => item.name)).toEqual(["setlist.fm Complete", "setlist.fm Compact", "setlist.fm Deluxe", "setlist.fm Mobile"]);
  for (const item of result) {
    expect(item.preview).toBe(true);
    expect(item.stub.entity).toBe("sensor.renamed_alex_shows");
    expect(item.stub.group_by_visit).toBe(false);
    expect(item.empty.entity).toBe("");
    expect(item.preferred).toBe("sensor.sam_gigs");
    expect(item.editor).toBe("setlistfm-card-editor");
    expect(item.suggestion).toBe("sensor.sam_gigs");
    expect(item.unrelated).toBeNull();
  }
});

test("waits for HA bootstrap before registering in the final element registry", async ({ page }) => {
  await page.goto("/?bootstrap=delayed", {waitUntil:"commit"});
  await page.waitForLoadState("networkidle");
  expect(await page.evaluate(() => window.customCards || [])).toEqual([]);
  await page.evaluate(() => window.finishBootstrap());
  await page.waitForFunction(() => window.ready);
  expect(await page.evaluate(() => window.oldRegistryResolved)).toBe(false);
  expect(await page.evaluate(() => window.customCards.map(({type}) => !!customElements.get(type)))).toEqual([true,true,true,true]);
  await page.evaluate(() => window.mountCard());
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
});

test("editor chooses exact renamed account IDs and emits complete config without credentials", async ({ page }, testInfo) => {
  await page.evaluate(() => window.mountEditor({grid_options:{columns:12}}));
  const account = page.getByLabel("Account / concerts entity");
  await expect(account.locator("option")).toHaveCount(3);
  await account.selectOption("sensor.sam_gigs");
  await page.getByLabel("Title", {exact:true}).fill("SAM live");
  await page.getByLabel("Show", {exact:true}).selectOption("past");
  await page.getByLabel("Maximum concerts per list section (1-50)").fill("7");
  await page.getByLabel("Maximum concerts per list section (1-50)").press("Tab");
  await page.getByLabel("Show listed song counts").uncheck();
  await page.getByLabel("Show city and country").uncheck();
  expect(await page.evaluate(() => window.lastChange)).toEqual({
    bubbles:true, composed:true,
    config:{type:"custom:setlistfm-complete-card",entity:"sensor.sam_gigs",title:"SAM live",filter:"past",
      limit:7,show_songs:false,show_location:false,group_by_visit:false,grid_options:{columns:12}},
  });
  await page.screenshot({path:testInfo.outputPath("visual-editor.png"),fullPage:true});
});

test("editor retains unavailable selections, validates limit and accepts keyboard input", async ({ page }) => {
  await page.evaluate(() => window.mountEditor({entity:"sensor.old_name"}));
  await expect(page.getByLabel("Account / concerts entity")).toHaveValue("sensor.old_name");
  const limit = page.getByLabel("Maximum concerts per list section (1-50)");
  await limit.fill("0");
  await limit.press("Tab");
  expect(await page.evaluate(() => window.lastChange)).toBeUndefined();
  await limit.fill("4");
  await limit.press("Tab");
  await page.getByLabel("Show listed song counts").focus();
  await page.keyboard.press("Space");
  expect(await page.evaluate(() => window.lastChange.config.show_songs)).toBe(false);
});

test("editor applies pending accounts on blur and preserves typed input and selection", async ({ page }) => {
  await page.evaluate(() => {
    window.mountEditor();
    const outside = document.createElement("button");
    outside.textContent = "Outside editor";
    document.body.append(outside);
  });
  const account = page.getByLabel("Account / concerts entity");
  await account.selectOption("sensor.sam_gigs");
  await account.focus();
  await page.evaluate(() => {
    const hass = window.fixtureHass();
    hass.states["sensor.renamed_alex_shows"].attributes.friendly_name = "Alex renamed";
    hass.states["sensor.zoe_shows"] = {
      state:"0", attributes:{friendly_name:"Zoe Concerts",concerts:[],concert_list:""},
    };
    window.editor.hass = hass;
  });
  await expect(account).toBeFocused();
  await expect(account.locator("option")).toHaveCount(3);
  await page.getByRole("button", {name:"Outside editor"}).click();
  await expect(account.locator("option")).toHaveCount(4);
  await expect(account.locator('option[value="sensor.renamed_alex_shows"]')).toContainText("Alex renamed");
  await expect(account).toHaveValue("sensor.sam_gigs");

  const title = page.getByLabel("Title", {exact:true});
  await title.fill("My concert diary");
  await title.evaluate((input) => { input.setSelectionRange(3,10); window.typedInput = input; });
  await page.evaluate(() => {
    const hass = window.editor.hass;
    const states = {
      ...hass.states, "sensor.zoe_renamed":hass.states["sensor.zoe_shows"],
    };
    delete states["sensor.zoe_shows"];
    window.editor.hass = {...hass, states};
  });
  await expect(title).toBeFocused();
  await expect(title).toHaveValue("My concert diary");
  expect(await title.evaluate((input) => [input === window.typedInput,input.selectionStart,input.selectionEnd])).toEqual([true,3,10]);
  await page.getByRole("button", {name:"Outside editor"}).click();
  await expect(account.locator('option[value="sensor.zoe_renamed"]')).toHaveCount(1);
  await expect(account.locator('option[value="sensor.zoe_shows"]')).toHaveCount(0);
  await expect(account).toHaveValue("sensor.sam_gigs");
  await expect(title).toHaveValue("My concert diary");
});

test("canonical calendar range matches the backend, including early years", async ({ page }) => {
  const cases = [
    ["01-01-2026", "2026-01-01"], ["31-12-2026", "2026-12-31"],
    ["29-02-2024", "2024-02-29"], ["29-02-2000", "2000-02-29"],
    ["01-01-0001", "0001-01-01"], ["01-01-0099", "0099-01-01"],
    ["31-12-0999", "0999-12-31"], ["31-12-9999", "9999-12-31"],
  ];
  const result = await page.evaluate((dates) => dates.map((value) => {
    const parsed = window.helpers.parseConcertDate(value);
    return parsed ? [parsed.key, parsed.date.toISOString().slice(0, 10)] : null;
  }), cases.map(([value]) => value));
  expect(result).toEqual(cases.map(([, key]) => [key, key]));
});

test("calendar parsing, leap years, timezone boundaries and chronological order", async ({ page }) => {
  const result = await page.evaluate(() => {
    const {parseConcertDate, todayKey, splitConcerts} = window.helpers;
    const records = window.fixtureHass().states["sensor.renamed_alex_shows"].attributes.concerts;
    return {
      invalid:["31-02-2026","29-02-2025","01-13-2026","2026-09-29",null,
        "1-1-2026"," 1-01-2026","01-01-2026 ","01-01-0000"].map(parseConcertDate),
      leap:parseConcertDate("29-02-2024").key,
      amsterdam:todayKey("Europe/Amsterdam"), la:todayKey("America/Los_Angeles"),
      east:todayKey("Pacific/Kiritimati",new Date("2026-01-01T10:30:00Z")),
      west:todayKey("Pacific/Honolulu",new Date("2026-01-01T00:30:00Z")),
      upcoming:splitConcerts(records,todayKey("Europe/Amsterdam")).upcoming.map((item) => item.id),
      past:splitConcerts(records,todayKey("Europe/Amsterdam")).past.map((item) => item.id),
    };
  });
  expect(result).toEqual({
    invalid:[null,null,null,null,null,null,null,null,null],leap:"2024-02-29",amsterdam:"2026-09-30",la:"2026-09-29",
    east:"2026-01-02",west:"2025-12-31",upcoming:["c","b","a"],past:["e","d"],
  });
  await page.evaluate(() => window.mountCard());
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
  await expect(page.locator(".columns section").last().locator("h4")).toHaveText(["Fontaines D.C.","Nala Sinephro"]);
});

test("changes the date boundary while idle and cleans up its timer", async ({ page }) => {
  await page.clock.setSystemTime(new Date("2026-09-29T21:59:30Z"));
  await page.evaluate(() => window.mountCard());
  await expect(page.locator(".hero h4")).toHaveText("Fontaines D.C.");
  await page.clock.fastForward(60000);
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
  expect(await page.evaluate(() => {
    const original = window.clearInterval;
    let cleared;
    window.clearInterval = (timer) => { cleared = timer; original(timer); };
    const timer = window.card._clock;
    window.card.remove();
    return timer === cleared;
  })).toBe(true);
});

test("updates timestamps when HA timezone changes without changing today's date", async ({ page }) => {
  await page.evaluate(() => window.mountCard());
  const before = await page.locator(".updated").textContent();
  await page.evaluate(() => {
    window.card.hass = {...window.card.hass, config:{time_zone:"Europe/Helsinki"}};
  });
  await expect(page.locator(".updated")).not.toHaveText(before);
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
});

test("hostile text stays text and unsafe links never become anchors", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.fixtureHass();
    const concerts = hass.states["sensor.renamed_alex_shows"].attributes.concerts;
    concerts[2].artist.name = '<img src=x onerror="window.pwned=true">';
    concerts[2].venue.name = "<script>window.pwned=true</script>";
    concerts[2].url = "javascript:alert(1)";
    concerts[4].url = "https://setlist.fm.evil.test/";
    concerts[3].url = "data:text/html,<script>alert(1)</script>";
    window.mountCard("deluxe",{title:"<img onerror=alert(1)>"},hass);
  });
  await expect(page.locator("h2")).toHaveText("<img onerror=alert(1)>");
  await expect(page.locator(".hero h4")).toHaveText('<img src=x onerror="window.pwned=true">');
  await expect(page.locator("setlistfm-deluxe-card").locator("img, script")).toHaveCount(0);
  await expect(page.locator(".hero a")).toHaveCount(0);
  expect(await page.evaluate(() => window.pwned)).toBeUndefined();
  expect(await page.evaluate(() => [
    "javascript:alert(1)", "//www.setlist.fm", "https://user:pass@www.setlist.fm/",
    "https://www.setlist.fm:1234/", "https://evil.test", "file:///tmp/test",
  ].map(window.helpers.safeSetlistUrl))).toEqual([null,null,null,null,null,null]);
  expect(await page.evaluate(() => window.helpers.safeSetlistUrl("http://www.setlist.fm/setlist/example.html"))).toBe("https://www.setlist.fm/setlist/example.html");
});

for (const [state, message] of [
  ["unavailable","Concert data is unavailable."],
  ["unknown","Concert data is not ready yet."],
  ["missing","was not found."],
  ["invalid","This entity has no concerts list."],
  ["empty","An empty list does not establish your total attendance."],
  ["loading","Connecting to Home Assistant..."],
  ["unconfigured","Choose your setlist.fm concerts sensor"],
  ["timezone","Waiting for the Home Assistant time zone."],
]) {
  test(`honest ${state} state`, async ({ page }) => {
    await page.evaluate((state) => {
      const hass = window.fixtureHass();
      const sensor = hass.states["sensor.renamed_alex_shows"];
      if (state === "missing") delete hass.states["sensor.renamed_alex_shows"];
      else if (state === "invalid") delete sensor.attributes.concerts;
      else if (state === "empty") sensor.attributes.concerts = [];
      else if (state === "timezone") delete hass.config.time_zone;
      else sensor.state = state;
      window.mountCard("complete",state === "unconfigured" ? {entity:""} : {},state === "loading" ? null : hass);
    }, state);
    await expect(page.getByRole("status")).toContainText(message);
    await expect(page.locator(".hero")).toHaveCount(0);
  });
}

test("malformed records and stale results have explicit notices", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.fixtureHass();
    const attributes = hass.states["sensor.renamed_alex_shows"].attributes;
    attributes.last_update_success = false;
    attributes.concerts.push({date:"not-a-date"},null);
    window.mountCard("complete",{},hass);
  });
  await expect(page.getByRole("status").first()).toContainText("last refresh failed");
  await expect(page.getByRole("status").last()).toContainText("2 concert record(s)");
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
});

for (const preset of ["complete", "compact", "deluxe", "mobile"]) {
  test(`${preset} reports sanitized incomplete backend data`, async ({ page }) => {
    await page.evaluate((preset) => {
      const hass = window.fixtureHass();
      Object.assign(hass.states["sensor.renamed_alex_shows"].attributes, {
        complete:false, skipped_count:2, completeness_reason:"invalid_records",
        fetched_count:5, total_attended:7,
      });
      window.mountCard(preset, {}, hass);
    }, preset);
    await expect(page.getByRole("status")).toContainText("2 invalid records were skipped by the integration");
    await expect(page.getByRole("status")).not.toContainText("their date or details are invalid");
    await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
    await expect(page.locator(".stats dd").first()).toHaveText("5");
  });
}

test("ambiguous backend attendance is not presented as confirmed zero attendance", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.fixtureHass();
    const state = hass.states["sensor.renamed_alex_shows"];
    state.state = "0";
    Object.assign(state.attributes, {
      concerts:[], complete:false, skipped_count:0, completeness_reason:"attendance_not_found",
      fetched_count:0, total_attended:null,
    });
    window.mountCard("complete", {}, hass);
  });
  await expect(page.locator(".warning")).toContainText("cannot distinguish an empty account from an unknown username");
  await expect(page.locator(".warning")).toContainText("Total attendance is unknown");
  await expect(page.locator(".warning")).not.toContainText("invalid records");
  await expect(page.locator(".hero")).toHaveCount(0);
});

for (const complete of [true, undefined]) {
  test(`complete=${complete} remains compatible without an incompleteness warning`, async ({ page }) => {
    await page.evaluate((complete) => {
      const hass = window.fixtureHass();
      if (complete !== undefined) Object.assign(hass.states["sensor.renamed_alex_shows"].attributes, {
        complete, skipped_count:0, completeness_reason:null,
      });
      window.mountCard("complete", {}, hass);
    }, complete);
    await expect(page.locator(".warning")).toHaveCount(0);
    await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
  });
}

test("unknown upstream incompleteness reasons have a safe generic warning", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.fixtureHass();
    Object.assign(hass.states["sensor.renamed_alex_shows"].attributes, {
      complete:false, skipped_count:-1, completeness_reason:"<img src=x onerror=alert(1)>",
    });
    window.mountCard("complete", {}, hass);
  });
  await expect(page.locator(".warning")).toContainText("Attendance data is incomplete");
  await expect(page.locator(".warning")).not.toContainText("<img");
  await expect(page.locator(".warning")).not.toContainText("-1");
});

test("filters and options narrow records and never invent extra history", async ({ page }) => {
  await page.evaluate(() => window.mountCard("complete",{filter:"past",limit:1,show_location:false,show_songs:false}));
  await expect(page.locator(".hero")).toHaveCount(0);
  await expect(page.locator("h4")).toHaveText(["Fontaines D.C."]);
  await expect(page.locator(".location, .songs")).toHaveCount(0);
  await expect(page.getByText("1 more available.",{exact:false})).toBeVisible();
  await page.evaluate(() => window.mountCard("complete",{filter:"upcoming"}));
  await expect(page.getByText("Recent concerts",{exact:true})).toHaveCount(0);
  await expect(page.locator("h4")).toHaveText(["The War on Drugs","Little Simz","Khruangbin"]);
});

test("invalid configuration is rejected", async ({ page }) => {
  const errors = await page.evaluate(() => [null,{entity:4},{entity:"light.test"},{limit:0},{limit:51},
    {limit:1.5},{filter:"bad"},{title:{}},{show_songs:"yes"},{group_by_visit:"true"},{group_by_visit:1}].map((config) => {
    try { document.createElement("setlistfm-complete-card").setConfig(config); return false; }
    catch { return true; }
  }));
  expect(errors.every(Boolean)).toBe(true);
});

test("account details and safe setlist links are keyboard accessible", async ({ page, context }) => {
  await page.evaluate(() => {
    window.mountCard();
    window.card.addEventListener("hass-more-info",(event) => {
      window.moreInfo = {entity:event.detail.entityId,bubbles:event.bubbles,composed:event.composed};
    });
  });
  const link = page.locator(".hero a");
  await expect(link).toHaveAttribute("target","_blank");
  await expect(link).toHaveAttribute("rel","noopener noreferrer");
  await link.focus();
  await expect(link).toBeFocused();
  await page.getByRole("button",{name:"Account details"}).focus();
  await page.keyboard.press("Enter");
  expect(await page.evaluate(() => window.moreInfo)).toEqual({
    entity:"sensor.renamed_alex_shows",bubbles:true,composed:true,
  });
  // An unrelated HA state update should not destroy link focus.
  await link.focus();
  await page.evaluate(() => { window.card.hass = {...window.card.hass}; });
  await expect(link).toBeFocused();
  await context.route("https://www.setlist.fm/**", (route) => route.fulfill({body:"Local link interaction fixture"}));
  const popupPromise = page.waitForEvent("popup");
  await page.keyboard.press("Enter");
  const popup = await popupPromise;
  await popup.waitForLoadState();
  expect(popup.url()).toBe("https://www.setlist.fm/setlist/example/c.html");
  expect(await popup.evaluate(() => window.opener)).toBeNull();
  await popup.close();
});

for (const preset of ["complete","compact","deluxe","mobile"]) {
  for (const [width, theme] of [[320,"light"],[390,"dark"],[960,"light"],[960,"dark"]]) {
    test(`${preset} ${width}px ${theme} layout`, async ({ page }, testInfo) => {
      await page.setViewportSize({width,height:1100});
      await page.evaluate(({preset,theme}) => {
        document.documentElement.classList.toggle("dark",theme === "dark");
        window.mountCard(preset);
      },{preset,theme});
      await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
      const geometry = await page.evaluate(() => {
        const root = window.card.shadowRoot;
        const targets = [...root.querySelectorAll("a,button")];
        return {
          overflowing:[...root.querySelectorAll("*")].filter((node) => node.clientWidth && node.scrollWidth > node.clientWidth + 1).map((node) => node.className),
          touchTargets:targets.every((node) => node.getBoundingClientRect().height >= 44),
          columns:getComputedStyle(root.querySelector(".columns")).display,
          background:getComputedStyle(root.querySelector("ha-card")).backgroundColor,
          sizing:window.card.getGridOptions(),size:window.card.getCardSize(),
        };
      });
      expect(geometry.overflowing).toEqual([]);
      expect(geometry.touchTargets).toBe(true);
      expect(geometry.columns).toBe(width >= 960 && preset !== "mobile" ? "grid" : "block");
      expect(geometry.background).toBe(theme === "dark" ? "rgb(29, 37, 42)" : "rgb(255, 255, 255)");
      expect(geometry.sizing).toEqual({columns:12,min_columns:6,min_rows:3});
      expect(geometry.size).toBeGreaterThan(3);
      await page.screenshot({path:testInfo.outputPath(`${preset}-${width}-${theme}.png`),fullPage:true});
    });
  }
}

for (const preset of ["complete", "compact", "deluxe", "mobile"]) {
  test(`${preset} grouping editor defaults off and survives HA config echo`, async ({ page }) => {
    await page.evaluate((preset) => window.mountEditor({type:`custom:setlistfm-${preset}-card`}), preset);
    const checkbox = page.getByLabel("Group by concert visit", {exact:true});
    await expect(checkbox).not.toBeChecked();
    await checkbox.focus();
    await page.keyboard.press("Space");
    await expect(checkbox).toBeChecked();
    await expect(checkbox).toBeFocused();
    expect(await page.evaluate(() => window.lastChange.config.group_by_visit)).toBe(true);
    await page.getByLabel("Title", {exact:true}).fill("Visit diary");
    expect(await page.evaluate(() => window.lastChange.config.group_by_visit)).toBe(true);
    await page.evaluate(() => {
      window.editor.shadowRoot.activeElement?.blur();
      window.editor.setConfig(window.lastChange.config);
    });
    await expect(checkbox).toBeChecked();
    await checkbox.uncheck();
    expect(await page.evaluate(() => window.lastChange.config.group_by_visit)).toBe(false);
  });

  for (const [width, theme] of [[320, "light"], [390, "dark"], [960, "dark"]]) {
    test(`${preset} grouped ${width}px ${theme} preserves artists and accessible links`, async ({ page }, testInfo) => {
      await page.setViewportSize({width, height:1100});
      await page.evaluate(({preset, theme}) => {
        document.documentElement.classList.toggle("dark", theme === "dark");
        window.mountCard(preset, {group_by_visit:true}, window.groupedHass());
      }, {preset, theme});
      await expect(page.locator(".hero h4")).toHaveText("Paradiso");
      await expect(page.locator(".hero .performance-name")).toHaveText(["Bloodywood", "Support Band"]);
      await expect(page.locator(".hero .setlist")).toHaveCount(2);
      await expect(page.locator(".stats dt").first()).toHaveText("Visits in list");
      await expect(page.locator(".stats dd").first()).toHaveText("3");
      await expect(page.locator(".stats dt").nth(1)).toHaveText("Performances in list");
      await expect(page.locator(".stats dd").nth(1)).toHaveText("4");
      await expect(page.locator(".columns h4").last()).toHaveText("Rotterdam Ahoy");
      for (const [index, id] of ["bloodywood", "support"].entries()) {
        const link = page.locator(".hero .setlist").nth(index);
        await expect(link).toHaveAttribute("href", `https://www.setlist.fm/setlist/${id}.html`);
        await expect(link).toHaveAttribute("target", "_blank");
        await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        await link.focus();
        await expect(link).toBeFocused();
      }
      await expect(page.locator(".hero .songs")).toHaveCount(preset === "compact" ? 0 : 2);
      expect(await page.evaluate(() => {
        const root = window.card.shadowRoot;
        return {
          overflowing:[...root.querySelectorAll("*")].filter((node) => node.clientWidth && node.scrollWidth > node.clientWidth + 1).map((node) => node.className),
          touchTargets:[...root.querySelectorAll("a,button")].every((node) => node.getBoundingClientRect().height >= 44),
          background:getComputedStyle(root.querySelector("ha-card")).backgroundColor,
        };
      })).toEqual({overflowing:[], touchTargets:true, background:theme === "dark" ? "rgb(29, 37, 42)" : "rgb(255, 255, 255)"});
      await page.screenshot({path:testInfo.outputPath(`grouped-${preset}-${width}-${theme}.png`), fullPage:true});
      await page.evaluate(() => window.card.setConfig({...window.card._config,group_by_visit:false}));
      await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
      await expect(page.locator(".stats dd").first()).toHaveText("5");
    });
  }
}

test("grouping requires backend payload instead of guessing from old names", async ({ page }) => {
  await page.evaluate(() => window.mountCard("complete", {group_by_visit:true}));
  await expect(page.getByRole("status")).toContainText("requires an updated setlist.fm integration");
  await expect(page.locator(".stats, .hero")).toHaveCount(0);
  await page.evaluate(() => window.card.setConfig({...window.card._config,group_by_visit:false}));
  await expect(page.locator(".hero h4")).toHaveText("The War on Drugs");
});

test("grouped partial data, separate unidentified performances and overflow stay explicit", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.groupedHass();
    const attributes = hass.states["sensor.renamed_alex_shows"].attributes;
    Object.assign(attributes, {complete:false, grouping_complete:false, skipped_count:1, completeness_reason:"invalid_records"});
    const visit = attributes.concert_visits[0];
    Object.assign(visit, {grouping_complete:false, performance_count:132, omitted_performance_count:130});
    window.mountCard("deluxe", {group_by_visit:true}, hass);
  });
  await expect(page.getByRole("status").filter({hasText:"1 invalid record was skipped"})).toBeVisible();
  await expect(page.getByRole("status").filter({hasText:"Visit grouping is uncertain"})).toBeVisible();
  await expect(page.getByRole("status").filter({hasText:"Venue identity is missing"})).toBeVisible();
  await expect(page.getByRole("status").filter({hasText:"130 additional performances are omitted"})).toBeVisible();
  await expect(page.locator(".stats dt").first()).toHaveText("Visit groups / separate performances");
  await expect(page.locator(".hero .performance-name")).toHaveText(["Bloodywood", "Support Band"]);
});

test("grouped hostile lineup text is escaped and per-performance URL policy is enforced", async ({ page }) => {
  await page.evaluate(() => {
    const hass = window.groupedHass();
    const visit = hass.states["sensor.renamed_alex_shows"].attributes.concert_visits[0];
    visit.venue.name = "<img src=x onerror=alert(1)>";
    visit.performances[0].artist.name = "<script>alert(1)</script>";
    visit.performances[0].url = "javascript:alert(1)";
    visit.performances[1].url = "https://www.setlist.fm.evil.test/";
    window.mountCard("complete", {group_by_visit:true}, hass);
  });
  await expect(page.locator(".hero h4")).toHaveText("<img src=x onerror=alert(1)>");
  await expect(page.locator(".hero .performance-name").first()).toHaveText("<script>alert(1)</script>");
  await expect(page.locator(".hero a, .hero img, .hero script")).toHaveCount(0);
});

test("grouped date filters, section cap and HA midnight keep visits intact", async ({ page }) => {
  await page.evaluate(() => window.mountCard("complete", {group_by_visit:true, filter:"past", limit:1}, window.groupedHass()));
  await expect(page.locator("h4")).toHaveText(["Rotterdam Ahoy"]);
  await page.evaluate(() => window.card.setConfig({...window.card._config,filter:"upcoming"}));
  await expect(page.locator("h4")).toHaveText(["Paradiso", "AFAS Live"]);
  await expect(page.locator(".hero .performance-name")).toHaveCount(2);
  await page.clock.setSystemTime(new Date("2026-09-30T22:01:00Z"));
  await page.clock.fastForward(60000);
  await expect(page.locator(".hero h4")).toHaveText("AFAS Live");
});

for (const state of ["empty", "unavailable", "unknown", "invalid"]) {
  test(`grouped ${state} remains explicit`, async ({ page }) => {
    await page.evaluate((state) => {
      const hass = window.groupedHass();
      const sensor = hass.states["sensor.renamed_alex_shows"];
      if (state === "empty") sensor.attributes.concert_visits = [];
      else if (state === "invalid") sensor.attributes.concert_visits = [{date:"01-01-2026",performances:[null]}];
      else sensor.state = state;
      window.mountCard("complete", {group_by_visit:true}, hass);
    }, state);
    await expect(page.getByRole("status").first()).toContainText({
      empty:"No concert records", unavailable:"unavailable", unknown:"not ready", invalid:"could not be displayed",
    }[state]);
    await expect(page.locator(".hero")).toHaveCount(0);
  });
}
