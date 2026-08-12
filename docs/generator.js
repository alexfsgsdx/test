/**
 * RAM Part Number Generator — browser port for GitHub Pages.
 * Mirrors ram_part_number.py, product_validation.py, spd_serial.py
 */

const DDR4_SPEEDS = [1600,1867,2133,2400,2667,2933,3000,3200,3600,3733,3866,4000,4133,4266,4400,4600,4800,5000,5100];
const DDR5_SPEEDS = [4800,5200,5600,6000,6200,6400,6600,6800,7000,7200,7600,7800,8000,8200,8400,8600,8800,9000,9200];
const DDR5_MIN_RETAIL = 4800;
const CONSUMER_PER_STICK_GB = new Set([4,8,16,24,32,48,64]);
const COMMON_TOTAL_GB = new Set([8,16,32,48,64,96,128]);
const VALID_STICK_COUNTS = [1, 2, 4, 8];
const DDR4_OC = new Set([3000,3200,3600,3733,3866,4000,4133,4266,4400,4600,4800,5000,5100]);
const DDR5_OC = new Set([6000,6200,6400,6600,6800,7000,7200,7600,7800,8000,8200,8400,8600,8800,9000,9200]);
const DDR4_JEDEC = new Set([1600,1867,2133,2400,2667,2933,3200]);
const DDR5_JEDEC = new Set([4800,5200,5600,6000,6400]);

const JEDEC_MODULE_IDS = {
  kingston:[0x01,0x98], corsair:[0x02,0x9E], gskill:[0x04,0xCD], crucial:[0x00,0x2C], micron:[0x00,0x2C],
  teamgroup:[0x04,0xFE], patriot:[0x02,0x94], xpg:[0x04,0xCB], adata:[0x04,0xCB], pny:[0x01,0xA8],
  oloy:[0x06,0xBA], geil:[0x04,0xFE], mushkin:[0x01,0x94], silicon_power:[0x06,0xE7], klevv:[0x06,0xCB],
  lexar:[0x04,0xCB], apacer:[0x04,0xCB], vcolor:[0x06,0xCB], timetec:[0x06,0xE7], samsung:[0x00,0xCE],
  hynix:[0x00,0xAD], ballistix:[0x00,0x2C],
};

const SERIAL_SCHEMES = {
  gskill:"empty", corsair:"binary_le", kingston:"binary_be", crucial:"binary_le", micron:"binary_le",
  samsung:"binary_le", hynix:"binary_le", teamgroup:"tester_seq_le", patriot:"binary_le", xpg:"binary_le",
  adata:"binary_le", pny:"binary_le", oloy:"binary_le", geil:"binary_le", mushkin:"binary_le",
  silicon_power:"tester_seq_le", klevv:"binary_le", lexar:"binary_le", apacer:"binary_le", vcolor:"binary_le",
  timetec:"binary_le", ballistix:"binary_le",
};

const SCHEME_NOTES = {
  empty:"Blank SPD serial (0x00000000)",
  binary_le:"Binary counter stored little-endian in SPD",
  binary_be:"Binary counter stored big-endian in SPD (Kingston-style)",
  tester_seq_le:"Byte 325 = tester ID, bytes 326-328 = LE counter",
};

export function validSpeeds(generation) {
  return generation === 5 ? [...DDR5_SPEEDS] : [...DDR4_SPEEDS];
}

export function validStickCounts() {
  return [...VALID_STICK_COUNTS];
}

export function validTotalGb(sticks = null) {
  const totals = [...COMMON_TOTAL_GB].sort((a, b) => a - b);
  if (sticks == null) return totals;
  return totals.filter(
    (total) => total % sticks === 0 && CONSUMER_PER_STICK_GB.has(total / sticks)
  );
}

function nearestValidSpeed(generation, speed) {
  const speeds = validSpeeds(generation);
  return speeds.reduce((a, b) => Math.abs(b - speed) < Math.abs(a - speed) ? b : a);
}

function speedTier(generation, speed) {
  if (generation === 5) {
    if (DDR5_JEDEC.has(speed)) return "jedec";
    if (DDR5_OC.has(speed)) return "oc";
  } else {
    if (DDR4_JEDEC.has(speed)) return "jedec";
    if (DDR4_OC.has(speed)) return "oc";
  }
  return "unknown";
}

export function validateKitSpec(spec) {
  const errors = [], warnings = [];
  const allowed = spec.generation === 5 ? DDR5_SPEEDS : DDR4_SPEEDS;
  const perStick = Math.floor(spec.total_gb / spec.sticks);

  if (!allowed.includes(spec.speed_mts)) {
    const nearest = nearestValidSpeed(spec.generation, spec.speed_mts);
    errors.push(`${spec.speed_mts} MT/s is not a standard DDR${spec.generation} retail speed. Valid speeds: ${allowed.join(", ")}. Nearest match: ${nearest} MT/s.`);
  }
  if (spec.generation === 5 && spec.speed_mts < DDR5_MIN_RETAIL) {
    errors.push(`DDR5 desktop kits rarely exist below ${DDR5_MIN_RETAIL} MT/s. You entered ${spec.speed_mts} MT/s.`);
  }
  if (!CONSUMER_PER_STICK_GB.has(perStick)) {
    warnings.push(`${perStick} GB per stick is uncommon. Most retail kits use 4/8/16/24/32/48/64 GB modules.`);
  }
  if (!COMMON_TOTAL_GB.has(spec.total_gb)) {
    warnings.push(`${spec.total_gb} GB total is an unusual kit size. Common kits: 8/16/32/48/64/96/128 GB.`);
  }
  const tier = speedTier(spec.generation, spec.speed_mts);
  if (["xmp","expo","both"].includes(spec.profile) && tier === "jedec") {
    warnings.push(`DDR${spec.generation}-${spec.speed_mts} is typically a JEDEC speed. XMP/EXPO kits at this speed exist but are less common.`);
  }
  if (spec.profile === "jedec" && tier === "oc") {
    warnings.push(`DDR${spec.generation}-${spec.speed_mts} is usually sold as an XMP/EXPO overclock kit, not plain JEDEC.`);
  }
  if (spec.generation === 5 && spec.speed_mts >= 7200 && spec.total_gb >= 64) {
    warnings.push("High-speed DDR5 (7200+) at 64 GB+ is rare — only a few brands sell this combo.");
  }
  warnings.push("Only manufacturer catalog-confirmed SKUs are shown. If no results appear, this exact configuration is not in the verified catalog.");

  return { errors, warnings, speed_tier: tier, retail_likely: !errors.length && (tier === "jedec" || tier === "oc"), ok: !errors.length };
}

function pad2(n) { return String(n).padStart(2, "0"); }
function pad3(n) { return String(n).padStart(3, "0"); }

function defaultCl(spec) {
  const { generation, speed_mts, profile } = spec;
  if (profile === "jedec") {
    if (generation === 5) {
      const m = {4800:40,5200:42,5600:46,6000:48,6400:52};
      return m[speed_mts] ?? Math.max(36, Math.floor(speed_mts / 125));
    }
    const m = {2133:15,2400:17,2666:19,2933:21,3200:22};
    return m[speed_mts] ?? Math.max(14, Math.floor(speed_mts / 200));
  }
  if (generation === 5) {
    if (speed_mts >= 7200) return 34;
    if (speed_mts >= 6400) return 32;
    if (speed_mts >= 6000) return 30;
    if (speed_mts >= 5600) return 36;
    return 40;
  }
  if (speed_mts >= 3600) return 18;
  if (speed_mts >= 3200) return 16;
  if (speed_mts >= 3000) return 15;
  return 16;
}

function perStickGb(spec) {
  if (spec.total_gb % spec.sticks !== 0) throw new Error(`Total ${spec.total_gb} GB not divisible by ${spec.sticks} sticks.`);
  return spec.total_gb / spec.sticks;
}

async function stableSeed(...parts) {
  const payload = parts.join("|");
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(payload));
  const view = new DataView(buf);
  let v = view.getUint32(0, true);
  return (v & 0xFFFFFFFF) || 0x08424A92;
}

function toBcd(v) { return ((Math.floor(v / 10) << 4) | (v % 10)); }

function buildModuleUniqueId(brand, raw) {
  const [cont, code] = JEDEC_MODULE_IDS[brand] || [0x01, 0x98];
  const now = new Date();
  const year = toBcd(now.getFullYear() % 100);
  const week = toBcd(Math.min(getISOWeek(now), 53));
  const block = new Uint8Array([cont, code, 0x01, year, week, ...raw]);
  return "0x" + [...block].map(b => b.toString(16).padStart(2,"0").toUpperCase()).join("");
}

function getISOWeek(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
}

async function encodeSerial(scheme, brand, part, stick, generation, serialSalt = 0) {
  if (scheme === "empty") return [0,0,0,0];
  const seed = await stableSeed(brand, part, stick, generation, serialSalt);
  if (scheme === "tester_seq_le") {
    const tester = (seed & 0xFF) % 0x0F || 1;
    const counter = (seed >> 8) & 0xFFFFFF;
    return [tester, counter & 0xFF, (counter >> 8) & 0xFF, (counter >> 16) & 0xFF];
  }
  if (scheme === "binary_be") {
    return [(seed>>24)&0xFF, (seed>>16)&0xFF, (seed>>8)&0xFF, seed&0xFF];
  }
  return [seed&0xFF, (seed>>8)&0xFF, (seed>>16)&0xFF, (seed>>24)&0xFF];
}

async function generateSpdSerials(brand, part, generation, stickCount, serialSalt = 0) {
  const scheme = SERIAL_SCHEMES[brand] || "binary_le";
  const out = [];
  for (let stick = 1; stick <= stickCount; stick++) {
    const raw = await encodeSerial(scheme, brand, part, stick, generation, serialSalt);
    const plain = raw.map(b => b.toString(16).padStart(2,"0").toUpperCase()).join("");
    const le = raw[0] | (raw[1]<<8) | (raw[2]<<16) | (raw[3]<<24);
    const be = (raw[0]<<24) | (raw[1]<<16) | (raw[2]<<8) | raw[3];
    out.push({
      stick_index: stick,
      serial_number: "0x" + plain,
      serial_plain: plain,
      module_unique_id: buildModuleUniqueId(brand, raw),
      raw_bytes: raw.map(b => b.toString(16).padStart(2,"0").toUpperCase()).join(" "),
      spd_offset: "325-328 (0x145-0x148)",
      encoding: scheme,
      encoding_note: SCHEME_NOTES[scheme] || scheme,
      uint32_le: "0x" + (le>>>0).toString(16).padStart(8,"0").toUpperCase(),
      uint32_be: "0x" + (be>>>0).toString(16).padStart(8,"0").toUpperCase(),
    });
  }
  return out;
}

function buildAll(spec, cl) {
  const s = { ...spec, per_stick_gb: perStickGb(spec) };
  const builders = {
    kingston: () => {
      const line = ["xmp","expo","both"].includes(s.profile) ? "KF" : "KVR";
      const feat = ["expo","both"].includes(s.profile) ? "E" : s.profile === "xmp" ? "A" : "B";
      const kit = s.sticks > 1 ? `K${s.sticks}` : "";
      return `${line}${s.generation}${Math.floor(s.speed_mts/100)}C${pad2(cl)}BB2${feat}${kit}-${s.total_gb}`;
    },
    corsair: () => {
      const series = s.generation === 5 ? (s.rgb ? "H" : "K") : (s.rgb ? "W" : "K");
      const pl = s.profile === "expo" ? "Z" : "C";
      const base = `CM${series}${s.total_gb}GX${s.generation}M${s.sticks}B${s.speed_mts}${pl}${pad2(cl)}`;
      if (s.profile === "both") {
        return [`${base}   (Intel XMP 3.0)`, base.replace(`${s.speed_mts}C`, `${s.speed_mts}Z`) + "   (AMD EXPO)"];
      }
      return [base];
    },
    gskill: () => {
      const sub = `${pad2(cl)}${pad2(cl)}${pad2(cl)}${pad2(cl+10)}`;
      const kit = s.sticks > 1 ? `X${s.sticks}` : "";
      let series = s.generation === 5 ? (["expo","both"].includes(s.profile) ? "TZ5K" : "TR5G") : "TZK";
      if (s.rgb && s.generation === 5) series = ["expo","both"].includes(s.profile) ? "TZ5RK" : "TR5RG";
      return `F${s.generation}-${s.speed_mts}J${sub}G${s.total_gb}G${kit}-${series}`;
    },
    crucial: () => s.sticks === 1 ? `CT${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}U${s.generation}` : `CT${s.sticks}K${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}U${s.generation}`,
    teamgroup: () => { const h = s.rgb || s.profile !== "jedec" ? "H" : ""; const k = s.sticks > 1 ? "DC" : ""; const l = s.profile !== "jedec" ? "FF3" : "TPD"; return `${l}D${s.generation}${s.per_stick_gb}G${s.speed_mts}${h}C${pad2(cl)}A${k}01`; },
    patriot: () => `${s.generation===5?"PVV5":"PVS4"}${s.total_gb}G${Math.floor(s.speed_mts/10)}C${pad2(cl)}${s.rgb?"R":""}${s.sticks>1?"K":""}`,
    xpg: () => { const k = s.sticks>1 ? (s.rgb?"-DCLARBK":"-DCLABBK") : (s.rgb?"-CLARBK":"-CLABBK"); return `AX${s.generation}U${s.speed_mts}C${pad2(cl)}${s.per_stick_gb}G${k}`; },
    pny: () => `MD${s.total_gb}G${s.sticks>1?`K${s.sticks}`:""}D${s.speed_mts}${pad3(cl)}M${s.rgb?"RGB":"R"}`,
    oloy: () => `MD${s.generation}U${Math.floor(s.speed_mts/100)}${pad2(cl)}0${s.rgb?"BR":"B"}${s.sticks>1?"K":""}DE`,
    geil: () => `GSLZ${s.generation}S${s.speed_mts}C${pad2(cl)}${s.sticks>1?`DC${s.total_gb}G`:s.per_stick_gb+"G"}${s.rgb?"R":""}`,
    mushkin: () => `MRB${s.generation}U${Math.floor(s.speed_mts/100)}MMPP${s.total_gb}G${s.sticks>1?`X${s.sticks}`:""}`,
    silicon_power: () => `SP${pad3(s.per_stick_gb)}GXLZU${s.speed_mts}B${pad2(cl)}A${s.generation}${s.sticks>1?`x${s.sticks}`:""}`,
    klevv: () => `KD${s.generation}AGUA${s.total_gb}-${Math.floor(s.speed_mts/100)}B300C${pad2(cl)}${s.rgb?"RGD":"BK"}${s.sticks>1?`-${s.sticks}x${s.per_stick_gb}`:""}`,
    lexar: () => `LD${s.generation}U${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}LA${s.sticks>1?`-${s.sticks}x`:""}${s.rgb?"-RGD":"-BK"}`,
    apacer: () => `AH${s.generation}U${s.per_stick_gb}G${s.speed_mts}C${pad2(cl)}AA-${s.sticks>1?s.sticks:"1"}`,
    vcolor: () => `TD${s.generation}${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}U${s.sticks*10+1}`,
    timetec: () => `TTDDR${s.generation}-${s.speed_mts}-${s.per_stick_gb}x${s.sticks}-${cl}`,
    adata: () => `AD${s.generation}U${Math.floor(s.speed_mts/100)}${s.sticks>1?s.sticks+"x":""}${s.per_stick_gb}G-C${pad2(cl)}`,
    samsung: () => {
      if (s.form_factor === "sodimm") return `M3${s.generation}R${s.per_stick_gb}GA${Math.floor(s.speed_mts/800)}BB0-CQ${pad2(cl)}D`;
      const pc = {8:"2",16:"4",32:"6",64:"8"}[s.per_stick_gb] || "4";
      return `M3${s.generation}R${pc}GA${Math.floor(s.speed_mts/400)}BB0-CQ${pad2(cl)}D`;
    },
    hynix: () => `HMCG${Math.floor(s.speed_mts/100)}MEBUA${cl}.N${s.generation}${s.sticks>1?`-${s.sticks}x${s.per_stick_gb}G`:`-${s.per_stick_gb}G`}`,
    micron: () => {
      const d = {8:"8",16:"4",32:"5",64:"6"}[s.per_stick_gb] || "4";
      const sb = {4800:"48",5200:"52",5600:"56",6000:"60",6400:"64"}[s.speed_mts] || String(Math.floor(s.speed_mts/100));
      return `MTC${s.generation}${d}A${sb}C${pad2(cl)}${s.sticks>1?`K${s.sticks}`:""}`;
    },
    ballistix: () => s.sticks===1 ? `BL${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}U${s.generation}` : `BL${s.sticks}K${s.per_stick_gb}G${Math.floor(s.speed_mts/100)}C${pad2(cl)}U${s.generation}`,
  };
  return builders;
}

const BRAND_REGISTRY = [
  ["kingston","Kingston"], ["corsair","Corsair"], ["gskill","G.Skill"], ["crucial","Crucial"],
  ["teamgroup","TeamGroup T-Force"], ["patriot","Patriot"], ["xpg","XPG (ADATA)"], ["pny","PNY"],
  ["oloy","OLOy"], ["geil","GeIL"], ["mushkin","Mushkin"], ["silicon_power","Silicon Power"],
  ["klevv","Klevv"], ["lexar","Lexar"], ["apacer","Apacer"], ["vcolor","V-Color"],
  ["timetec","Timetec"], ["adata","ADATA"], ["samsung","Samsung"], ["hynix","SK hynix"],
  ["micron","Micron"], ["ballistix","Ballistix (legacy)"],
];

let catalogCache = null;
let catalogLoadPromise = null;

async function fetchJsonWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load verified product catalog.");

  const total = parseInt(res.headers.get("Content-Length") || "0", 10);
  const reader = res.body?.getReader();

  if (!reader) {
    onProgress?.({ percent: 50, phase: "download" });
    const data = await res.json();
    onProgress?.({ percent: 100, phase: "ready" });
    return data;
  }

  const chunks = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    let percent;
    if (total > 0) {
      percent = Math.min(92, Math.round((received / total) * 92));
    } else {
      percent = Math.min(85, Math.round((received / 1600000) * 85));
    }
    onProgress?.({ percent, phase: "download", received, total: total || null });
  }

  onProgress?.({ percent: 96, phase: "parse" });
  const merged = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  const text = new TextDecoder().decode(merged);
  const data = JSON.parse(text);
  onProgress?.({ percent: 100, phase: "ready" });
  return data;
}

export async function loadCatalog(options = {}) {
  const { onProgress } = options;
  if (catalogCache) {
    onProgress?.({ percent: 100, phase: "ready" });
    return catalogCache;
  }
  if (!catalogLoadPromise) {
    const url = new URL("./catalog.json", import.meta.url);
    catalogLoadPromise = fetchJsonWithProgress(url, onProgress)
      .then((data) => {
        catalogCache = data;
        return data;
      })
      .catch((err) => {
        catalogLoadPromise = null;
        throw err;
      });
  } else if (onProgress) {
    onProgress({ percent: 72, phase: "download" });
  }
  const data = await catalogLoadPromise;
  onProgress?.({ percent: 100, phase: "ready" });
  return data;
}

export function catalogStats(catalog) {
  const brands = new Set(catalog.products.map((p) => p.brand));
  return {
    product_count: catalog.products.length,
    brand_count: brands.size,
    brands: [...brands].sort(),
    version: catalog.version,
    updated: catalog.updated,
  };
}

function profileMatches(entryProfiles, requested) {
  if (requested === "both") return entryProfiles.some((p) => ["xmp", "expo", "both"].includes(p));
  if (requested === "jedec") return entryProfiles.includes("jedec");
  return entryProfiles.includes(requested) || entryProfiles.includes("both");
}

function profileLabel(product, requested) {
  const profiles = product.profiles || [product.profile];
  if (requested === "both") {
    if (profiles.includes("xmp") && profiles.includes("expo")) return "Intel XMP 3.0 & AMD EXPO";
    if (profiles.includes("xmp")) return "Intel XMP 3.0";
    if (profiles.includes("expo")) return "AMD EXPO";
    if (profiles.includes("both")) return "Intel XMP 3.0 & AMD EXPO";
    return null;
  }
  if (profiles.includes(requested) || profiles.includes("both")) {
    return { xmp: "Intel XMP 3.0", expo: "AMD EXPO", jedec: "JEDEC" }[requested] || null;
  }
  return null;
}

function lookupCatalog(spec, catalog) {
  const perStick = spec.total_gb / spec.sticks;
  const matches = {};
  for (const product of catalog.products) {
    const profiles = product.profiles || [product.profile];
    if (product.sticks !== spec.sticks) continue;
    if (product.per_stick_gb !== perStick) continue;
    if (product.total_gb !== spec.total_gb) continue;
    if (product.generation !== spec.generation) continue;
    if (product.speed_mts !== spec.speed_mts) continue;
    if (product.rgb !== !!spec.rgb) continue;
    if (product.ecc !== !!spec.ecc) continue;
    if ((product.form_factor || "dimm") !== (spec.form_factor || "dimm")) continue;
    if (spec.cas_latency != null && product.cas_latency !== spec.cas_latency) continue;
    if (!profileMatches(profiles, spec.profile)) continue;
    (matches[product.brand] ||= []).push(product);
  }
  for (const brand of Object.keys(matches)) {
    matches[brand].sort((a, b) => a.part_number.localeCompare(b.part_number));
  }
  return matches;
}

export async function generateReport(spec, options = {}) {
  const serialSalt = options.serialSalt ?? ((Date.now() ^ (Math.random() * 0xFFFFFFFF)) >>> 0);
  const per = perStickGb(spec);
  const validation = validateKitSpec(spec);
  if (!validation.ok) throw new Error(validation.errors.join(" "));

  const catalog = await loadCatalog();
  const matches = lookupCatalog(spec, catalog);
  const brandIds = Object.keys(matches);
  if (!brandIds.length) {
    throw new Error(
      "No verified manufacturer catalog products match this configuration. " +
      "Adjust speed, capacity, profile, RGB, or CAS latency — only catalog-confirmed SKUs are returned."
    );
  }

  let cl = spec.cas_latency ?? defaultCl(spec);
  const matchedCls = new Set();
  const brands = {};
  const brand_meta = [];

  for (const [id, name] of BRAND_REGISTRY) {
    const products = matches[id];
    if (!products?.length) continue;
    const enriched = [];
    for (const product of products) {
      matchedCls.add(product.cas_latency);
      enriched.push({
        part_number: product.part_number,
        label: profileLabel(product, spec.profile),
        product_name: product.product_name,
        catalog_confirmed: true,
        source_url: product.source_url,
        source: product.source,
        verified: product.verified,
        profiles: product.profiles || [product.profile],
        spd_serials: await generateSpdSerials(id, product.part_number, spec.generation, spec.sticks, serialSalt),
      });
    }
    brands[id] = enriched;
    brand_meta.push({ id, name });
  }

  if (matchedCls.size === 1) cl = [...matchedCls][0];
  const stats = catalogStats(catalog);

  return {
    ok: true,
    validation,
    valid_speeds: validSpeeds(spec.generation),
    catalog: {
      ...stats,
      mode: "catalog_only",
      matched_brands: brand_meta.length,
      matched_products: Object.values(brands).reduce((n, arr) => n + arr.length, 0),
    },
    spec: { ...spec, per_stick_gb: per, cas_latency: cl, cas_latency_custom: spec.cas_latency != null },
    brand_meta,
    brands,
    brand_count: brand_meta.length,
    serial_salt: serialSalt,
  };
}

/** Re-roll SPD assembly serials for an existing report without re-querying the catalog. */
export async function refreshReportSerials(report, serialSalt) {
  const salt = serialSalt ?? ((Date.now() ^ (Math.random() * 0xFFFFFFFF)) >>> 0);
  const spec = report.spec;
  const brands = {};
  for (const meta of report.brand_meta) {
    const enriched = [];
    for (const entry of report.brands[meta.id]) {
      enriched.push({
        ...entry,
        spd_serials: await generateSpdSerials(
          meta.id,
          entry.part_number,
          spec.generation,
          spec.sticks,
          salt,
        ),
      });
    }
    brands[meta.id] = enriched;
  }
  return { ...report, brands, serial_salt: salt };
}

export function parseNaturalLanguage(text) {
  const lowered = text.toLowerCase();
  let sticks, total_gb;
  const perMatch = lowered.match(/(\d+)\s*x\s*(\d+)\s*(?:gb|g)\b/);
  if (perMatch) {
    sticks = parseInt(perMatch[1], 10);
    total_gb = sticks * parseInt(perMatch[2], 10);
  } else {
    const sm = lowered.match(/(\d+)\s*(?:x|sticks?|modules?|dimms?)/) || lowered.match(/(\d+)\s*stick/);
    sticks = sm ? parseInt(sm[1], 10) : 2;
    const tm = lowered.match(/(\d+)\s*(?:gb|g)\s*(?:total|combined|kit)?|(?:total|combined|kit)\s*(\d+)\s*(?:gb|g)/) || lowered.match(/(\d+)\s*(?:gb|g)/);
    if (!tm) throw new Error("Could not find total capacity.");
    total_gb = parseInt(tm[1] || tm[2], 10);
  }
  const generation = /ddr4|ddr 4/.test(lowered) ? 4 : 5;
  const sp = lowered.match(/(?:speed|ddr\d[\s-]?|)(\d{4,5})\s*(?:mt\/s|mts|mhz)?/) || lowered.match(/\b(4\d{3}|5\d{3}|6\d{3}|7\d{3}|8\d{3})\b/);
  if (!sp) throw new Error("Could not find speed.");
  let profile = "jedec";
  if (/both|xmp and expo|xmp\/expo/.test(lowered)) profile = "both";
  else if (/expo/.test(lowered)) profile = "expo";
  else if (/xmp/.test(lowered)) profile = "xmp";
  const clm = lowered.match(/\bcl\s*(\d{1,2})\b|\bc(\d{1,2})\b/);
  return {
    sticks, total_gb, generation, speed_mts: parseInt(sp[1], 10), profile,
    cas_latency: clm ? parseInt(clm[1] || clm[2], 10) : null,
    rgb: /rgb/.test(lowered), ecc: /ecc/.test(lowered),
    form_factor: /sodimm|so-dimm/.test(lowered) ? "sodimm" : "dimm",
  };
}

export function specFromForm(data) {
  return {
    sticks: parseInt(data.sticks, 10),
    total_gb: parseInt(data.total_gb, 10),
    generation: parseInt(data.generation, 10),
    speed_mts: parseInt(data.speed_mts, 10),
    profile: data.profile || "jedec",
    cas_latency: data.cas_latency === "" || data.cas_latency == null ? null : parseInt(data.cas_latency, 10),
    rgb: !!data.rgb,
    ecc: !!data.ecc,
    form_factor: data.form_factor || "dimm",
  };
}
