// Procedural curtain-wall facade — the "curtain" backdrop variant.
//
// The city in elevation, not plan: a row of towers, each with its own
// structural module (bay width / floor height / dialect), drawn as hairline
// line-work in currentColor so it theme-flips for free. What keeps this
// reading as architecture instead of graph paper:
//   - line-weight hierarchy: party walls > columns > floors > mullions
//     (the component maps each path class to its opacity)
//   - bays wider than floors (~1.5–1.7:1) — never square cells
//   - per-tower modules, so floor lines misalign across party walls
//   - lit windows placed in clustered runs/stacks, not uniform noise
//
// Pure + deterministic (mulberry32 seeded PRNG): same seed → same facade,
// no Date.now/Math.random. Output is pre-batched SVG path data (one <path>
// per stroke/fill class) so the rendered SVG stays ~8 DOM nodes regardless
// of visual density.

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface FacadeModel {
  width: number;
  height: number;
  /** Stroked line-work, one path per weight class. */
  paths: {
    partyWalls: string;
    columns: string;
    floors: string;
    mullions: string;
    braces: string;
  };
  /** Filled window panes (lit cells), currentColor. */
  litPath: string;
  /** Filled spandrel bands (Chicago School floors). */
  spandrelPath: string;
  /** The one orange "found parcel" window. */
  orangePath: string;
  orange: { rect: Rect; cx: number; cy: number };
  stats: { cells: number; lit: number };
}

type Dialect = "miesian" | "chicagoSchool" | "braced";

interface Tower {
  x: number;
  w: number;
  dialect: Dialect;
  bays: number;
  bayW: number;
  floorH: number;
  /** y of floor line 0 — negative so floors bleed past the top edge. */
  phase: number;
  floors: number;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1);
    t = (t + Math.imul(t ^ (t >>> 7), t | 61)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const fmt = (n: number) => String(Math.round(n * 10) / 10);
const line = (x1: number, y1: number, x2: number, y2: number) =>
  `M${fmt(x1)} ${fmt(y1)}L${fmt(x2)} ${fmt(y2)}`;
const rectPath = ({ x, y, w, h }: Rect) => `M${fmt(x)} ${fmt(y)}h${fmt(w)}v${fmt(h)}h${fmt(-w)}Z`;

// Where the orange window lands: left periphery, below the headline column —
// far enough from the content mask's fade zone to keep most of its alpha.
const ORANGE_TARGET = { x: 150, y: 640 };

export function generateFacade(opts: { seed: number; width?: number; height?: number }): FacadeModel {
  const { seed, width = 1440, height = 900 } = opts;
  const rng = mulberry32(seed);
  const BLEED = 40;
  const yTop = -BLEED;
  const yBot = height + BLEED;

  // --- tower massing: slabs abut edge-to-edge, bleeding past both sides ---
  const towers: Tower[] = [];
  let tx = -BLEED - rng() * 40;
  while (tx < width + BLEED) {
    const w = 140 + rng() * 180;
    towers.push({ x: tx, w, dialect: "miesian", bays: 0, bayW: 0, floorH: 0, phase: 0, floors: 0 });
    tx += w;
  }

  // Dialects: exactly one braced tower (never at an edge), and both named
  // vocabularies guaranteed to appear so no seed yields a monotone field.
  const bracedIdx = 1 + Math.floor(rng() * Math.max(1, towers.length - 2));
  towers.forEach((t, i) => {
    t.dialect = i === bracedIdx ? "braced" : rng() < 0.5 ? "miesian" : "chicagoSchool";
  });
  const others = towers.filter((_, i) => i !== bracedIdx);
  if (!others.some((t) => t.dialect === "chicagoSchool")) others[0].dialect = "chicagoSchool";
  if (!others.some((t) => t.dialect === "miesian")) others[others.length - 1].dialect = "miesian";

  // --- structural module per tower (bays wider than floors) ---
  for (const t of towers) {
    const targetBay =
      t.dialect === "miesian" ? 24 + rng() * 7 : t.dialect === "chicagoSchool" ? 34 + rng() * 10 : 42 + rng() * 8;
    t.bays = Math.max(3, Math.round(t.w / targetBay));
    t.bayW = t.w / t.bays;
    t.floorH = t.bayW / (t.dialect === "chicagoSchool" ? 1.7 : 1.5);
    t.phase = -rng() * t.floorH;
    t.floors = Math.ceil((yBot - t.phase) / t.floorH);
  }

  // Locate the cell that will hold the orange window (its tower skips lit
  // and mullion fills there).
  const oTower = towers.find((t) => ORANGE_TARGET.x >= t.x && ORANGE_TARGET.x < t.x + t.w)!;
  const oBay = Math.min(oTower.bays - 1, Math.floor((ORANGE_TARGET.x - oTower.x) / oTower.bayW));
  const oFloor = Math.floor((ORANGE_TARGET.y - oTower.phase) / oTower.floorH);

  const party: string[] = [];
  const columns: string[] = [];
  const floors: string[] = [];
  const mullions: string[] = [];
  const braces: string[] = [];
  const litRects: Rect[] = [];
  const spandrels: Rect[] = [];
  let cellCount = 0;

  party.push(line(towers[0].x, yTop, towers[0].x, yBot));
  for (const t of towers) party.push(line(t.x + t.w, yTop, t.x + t.w, yBot));

  for (const t of towers) {
    const isOrangeTower = t === oTower;
    const cellRect = (b: number, f: number): Rect => ({
      x: t.x + b * t.bayW + 2.5,
      y: t.phase + f * t.floorH + 2.5,
      w: t.bayW - 5,
      h: t.floorH - 5,
    });

    for (let b = 1; b < t.bays; b++) {
      const cx = t.x + b * t.bayW;
      columns.push(line(cx, yTop, cx, yBot));
    }
    for (let f = 0; f <= t.floors; f++) {
      const fy = t.phase + f * t.floorH;
      floors.push(line(t.x, fy, t.x + t.w, fy));
    }
    cellCount += t.bays * t.floors;

    // Lit windows: clustered — horizontal runs (half-lit office floors),
    // an occasional vertical stack (stairwell core), sparse singles.
    const lit = new Set<string>();
    const runs = 2 + Math.floor(rng() * 3);
    for (let i = 0; i < runs; i++) {
      const f = Math.floor(rng() * t.floors);
      const start = Math.floor(rng() * t.bays);
      const len = 2 + Math.floor(rng() * 4);
      for (let b = start; b < Math.min(t.bays, start + len); b++) lit.add(`${b}:${f}`);
    }
    if (rng() < 0.5) {
      const b = Math.floor(rng() * t.bays);
      const start = Math.floor(rng() * t.floors);
      const len = 3 + Math.floor(rng() * 3);
      for (let f = start; f < Math.min(t.floors, start + len); f++) lit.add(`${b}:${f}`);
    }
    const singles = 3 + Math.floor(rng() * 3);
    for (let i = 0; i < singles; i++) {
      lit.add(`${Math.floor(rng() * t.bays)}:${Math.floor(rng() * t.floors)}`);
    }
    if (isOrangeTower) lit.delete(`${oBay}:${oFloor}`);
    for (const key of lit) {
      const [b, f] = key.split(":").map(Number);
      litRects.push(cellRect(b, f));
    }

    if (t.dialect === "chicagoSchool") {
      // Some floors read as continuous spandrel bands; the rest may carry
      // Chicago windows (1:2:1 — two inner mullions + a sill).
      for (let f = 0; f < t.floors; f++) {
        const rowY = t.phase + f * t.floorH;
        if (rng() < 0.28) {
          spandrels.push({ x: t.x + 1, y: rowY + t.floorH * 0.72, w: t.w - 2, h: t.floorH * 0.28 - 1.5 });
          continue;
        }
        for (let b = 0; b < t.bays; b++) {
          if (rng() >= 0.3) continue;
          if (lit.has(`${b}:${f}`)) continue;
          if (isOrangeTower && b === oBay && f === oFloor) continue;
          const x0 = t.x + b * t.bayW;
          const m1 = x0 + t.bayW * 0.27;
          const m2 = x0 + t.bayW * 0.73;
          mullions.push(line(m1, rowY + 3, m1, rowY + t.floorH - 4));
          mullions.push(line(m2, rowY + 3, m2, rowY + t.floorH - 4));
          mullions.push(line(x0 + 3, rowY + t.floorH - 4, x0 + t.bayW - 4, rowY + t.floorH - 4));
        }
      }
    } else if (t.dialect === "braced") {
      // Hancock-style X-bracing: full-tower-width panels spanning several
      // floors — a tower-level feature, never a per-cell tile.
      const panelH = (6 + Math.floor(rng() * 3)) * t.floorH;
      for (let py = t.phase; py < yBot; py += panelH) {
        braces.push(line(t.x, py, t.x + t.w, py + panelH));
        braces.push(line(t.x + t.w, py, t.x, py + panelH));
      }
    } else if (rng() < 0.35) {
      // Miesian towers occasionally carry a belt-truss band (mechanical floor).
      const every = 12 + Math.floor(rng() * 5);
      for (let f = every; f < t.floors; f += every) {
        const fy = t.phase + f * t.floorH;
        braces.push(line(t.x, fy, t.x + t.w, fy));
        braces.push(line(t.x, fy + 3.5, t.x + t.w, fy + 3.5));
      }
    }
  }

  const orangeRect: Rect = {
    x: oTower.x + oBay * oTower.bayW + 2.5,
    y: oTower.phase + oFloor * oTower.floorH + 2.5,
    w: oTower.bayW - 5,
    h: oTower.floorH - 5,
  };

  return {
    width,
    height,
    paths: {
      partyWalls: party.join(""),
      columns: columns.join(""),
      floors: floors.join(""),
      mullions: mullions.join(""),
      braces: braces.join(""),
    },
    litPath: litRects.map(rectPath).join(""),
    spandrelPath: spandrels.map(rectPath).join(""),
    orangePath: rectPath(orangeRect),
    orange: {
      rect: orangeRect,
      cx: orangeRect.x + orangeRect.w / 2,
      cy: orangeRect.y + orangeRect.h / 2,
    },
    stats: { cells: cellCount, lit: litRects.length },
  };
}
