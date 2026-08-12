/** Derive RAM timing, voltage, and module details from catalog kit specs. */

const DDR5_JEDEC_TIMINGS = {
  4800: [40, 40, 40, 77],
  5200: [42, 42, 42, 84],
  5600: [46, 45, 45, 89],
  6000: [48, 48, 48, 96],
  6400: [52, 52, 52, 103],
};

const DDR4_JEDEC_TIMINGS = {
  1600: [11, 11, 11, 28],
  1867: [13, 13, 13, 32],
  2133: [15, 15, 15, 35],
  2400: [17, 17, 17, 39],
  2667: [19, 19, 19, 43],
  2933: [21, 21, 21, 47],
  3200: [22, 22, 22, 52],
};

const DDR4_TRFC_BY_GB = { 4: 350, 8: 560, 16: 880, 32: 1250 };
const DDR5_TRFC_BY_GB = { 8: 560, 16: 880, 24: 980, 32: 1250, 48: 1760, 64: 2100 };

function speedTier(generation, speedMts, profiles) {
  const set = new Set(profiles || []);
  if (generation === 5) {
    if (DDR5_JEDEC_TIMINGS[speedMts] && set.size <= 1 && set.has("jedec")) return "jedec";
    return "oc";
  }
  if (DDR4_JEDEC_TIMINGS[speedMts] && set.size <= 1 && set.has("jedec")) return "jedec";
  return "oc";
}

function estimateOcSubtimings(cl, speedMts, generation) {
  let trcd, tras;
  if (generation === 5) {
    trcd = cl + (speedMts >= 7200 ? 8 : speedMts >= 6400 ? 6 : speedMts >= 6000 ? 4 : 2);
    tras = cl + (speedMts >= 7200 ? 46 : speedMts >= 6400 ? 42 : speedMts >= 6000 ? 38 : 34);
  } else {
    trcd = cl + (speedMts >= 3600 ? 2 : speedMts >= 3200 ? 1 : 0);
    tras = cl + (speedMts >= 3600 ? 22 : speedMts >= 3200 ? 18 : 16);
  }
  return { cl, trcd, trp: trcd, tras, trc: trcd + tras, label: `CL${cl}-${trcd}-${trcd}-${tras}` };
}

function primaryTimings(generation, speedMts, casLatency, profiles) {
  const tier = speedTier(generation, speedMts, profiles);
  const table = generation === 5 ? DDR5_JEDEC_TIMINGS : DDR4_JEDEC_TIMINGS;
  if (tier === "jedec" && table[speedMts]) {
    const [cl, trcd, trp, tras] = table[speedMts];
    return { cl, trcd, trp, tras, trc: trcd + tras, label: `CL${cl}-${trcd}-${trp}-${tras}` };
  }
  return estimateOcSubtimings(casLatency, speedMts, generation);
}

function tckNs(speedMts) {
  return Math.round((2000 / speedMts) * 1000) / 1000;
}

function bandwidthGbps(speedMts) {
  return Math.round((speedMts * 8) / 100) / 10;
}

function trfcCycles(generation, perStickGb) {
  const table = generation === 5 ? DDR5_TRFC_BY_GB : DDR4_TRFC_BY_GB;
  if (table[perStickGb]) return table[perStickGb];
  const keys = Object.keys(table).map(Number);
  const nearest = keys.reduce((a, b) => Math.abs(b - perStickGb) < Math.abs(a - perStickGb) ? b : a);
  return table[nearest];
}

function voltages(generation, speedMts, profiles) {
  const set = new Set(profiles || []);
  const oc = speedTier(generation, speedMts, profiles) === "oc" || set.has("xmp") || set.has("expo") || set.has("both");
  if (generation === 5) {
    if (oc) {
      const vdd = speedMts >= 7200 ? 1.4 : speedMts >= 6400 ? 1.35 : 1.3;
      return { vdd, vddq: vdd, vpp: 1.8 };
    }
    return { vdd: 1.1, vddq: 1.1, vpp: 1.8 };
  }
  if (oc) return { vdd: 1.35, vddq: null, vpp: null };
  return { vdd: 1.2, vddq: null, vpp: null };
}

function commandRate(generation, speedMts, profiles) {
  if (speedTier(generation, speedMts, profiles) === "oc") return "1T";
  if (generation === 5 && speedMts >= 5600) return "2T";
  if (generation === 4 && speedMts >= 2933) return "2T";
  return "1T";
}

export function buildRamDetails(product, requestedProfile, spdSerials = null) {
  const profiles = product.profiles || [product.profile];
  const primary = primaryTimings(product.generation, product.speed_mts, product.cas_latency, profiles);
  const tck = tckNs(product.speed_mts);
  const perStickBw = bandwidthGbps(product.speed_mts);
  const volts = voltages(product.generation, product.speed_mts, profiles);
  const trfc = trfcCycles(product.generation, product.per_stick_gb);
  const tier = speedTier(product.generation, product.speed_mts, profiles);
  const voltageLabel = `${volts.vdd.toFixed(2)}V`;

  const sections = [
    {
      title: "Primary timings",
      rows: [
        { label: "CAS Latency (CL)", value: String(primary.cl) },
        { label: "tRCD", value: String(primary.trcd) },
        { label: "tRP", value: String(primary.trp) },
        { label: "tRAS", value: String(primary.tras) },
        { label: "tRC", value: String(primary.trc) },
        { label: "Timing string", value: primary.label },
      ],
    },
    {
      title: "Extended timings",
      rows: [
        { label: "tCK", value: `${tck} ns` },
        { label: "tRFC", value: `${trfc} cycles (~${Math.round(trfc * tck)} ns)` },
        { label: "tWR", value: product.generation === 5 ? "24" : "16" },
        { label: "Command rate", value: commandRate(product.generation, product.speed_mts, profiles) },
      ],
    },
    {
      title: "Voltage",
      rows: [
        { label: "VDD", value: `${volts.vdd.toFixed(2)} V` },
        ...(volts.vddq != null ? [{ label: "VDDQ", value: `${volts.vddq.toFixed(2)} V` }] : []),
        ...(volts.vpp != null ? [{ label: "VPP", value: `${volts.vpp.toFixed(2)} V` }] : []),
      ],
    },
    {
      title: "Module",
      rows: [
        { label: "Brand", value: product.brand },
        { label: "Part number", value: product.part_number },
        { label: "Product", value: product.product_name },
        { label: "Kit", value: `${product.sticks}×${product.per_stick_gb} GB (${product.total_gb} GB total)` },
        { label: "Generation", value: `DDR${product.generation}` },
        { label: "Speed", value: `${product.speed_mts} MT/s` },
        { label: "Form factor", value: (product.form_factor || "dimm").toUpperCase() },
        { label: "ECC", value: product.ecc ? "Yes" : "No" },
        { label: "RGB", value: product.rgb ? "Yes" : "No" },
        { label: "Profiles", value: profiles.join(", ") },
        { label: "Speed tier", value: tier.toUpperCase() },
        ...(product.verified ? [{ label: "Verified", value: product.verified }] : []),
      ],
    },
    {
      title: "Performance",
      rows: [
        { label: "Per module", value: `${perStickBw} GB/s (64-bit)` },
        { label: "Kit aggregate", value: `${Math.round(perStickBw * product.sticks * 10) / 10} GB/s` },
        { label: "Channels", value: `${product.sticks} module${product.sticks === 1 ? "" : "s"}` },
      ],
    },
  ];

  if (spdSerials?.length) {
    const spdRows = [];
    for (const serial of spdSerials) {
      const prefix = `Stick ${serial.stick_index ?? "?"}`;
      spdRows.push(
        { label: `${prefix} serial`, value: serial.serial_number || "—" },
        { label: `${prefix} encoding`, value: serial.encoding || "—" },
        { label: `${prefix} module ID`, value: serial.module_unique_id || "—" },
      );
    }
    sections.push({ title: "SPD programming", rows: spdRows });
  }

  return {
    summary: `DDR${product.generation}-${product.speed_mts} ${primary.label} @ ${voltageLabel} (${product.sticks}×${product.per_stick_gb} GB)`,
    primary_timings: primary,
    tck_ns: tck,
    trfc_cycles: trfc,
    command_rate: commandRate(product.generation, product.speed_mts, profiles),
    voltages: volts,
    speed_tier: tier,
    requested_profile: requestedProfile,
    sections,
    notes: [
      "Primary and extended timings are estimated from catalog speed, CL, and profile tier.",
      "Verify against the manufacturer XMP/EXPO profile or SPD dump before tuning.",
    ],
  };
}
