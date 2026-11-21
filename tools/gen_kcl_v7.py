"""Generate the EchoPilot AI case KCL from connector bounding boxes in the STEP.

Coordinates: STEP frame (mm). Board centre at x=y=0, boards 83 x 59.
Carrier PCB z 21.62-23.31, EchoPilot AI PCB z 33.31-34.99.
"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
parts = json.load(open(ROOT / "ref/stack_bb.json"))

# ---- parameters ------------------------------------------------------------
WALL = 2.0
FIT_, LIPT_ = 0.3, 1.6
CLR = 0.6                     # v5: board edge to snap-lip INNER face (v3/v4 lip was inside the board outline)
IX, IY = 41.5 + CLR + FIT_ + LIPT_, 29.5 + CLR + FIT_ + LIPT_   # 44.0, 32.0
OX, OY = IX + WALL, IY + WALL
FLOOR_IN = 13.5               # v5: case underside flush with the post bottoms (z 11.5): case + posts stand on the table, carrier at its STEP height
Z_BOT = FLOOR_IN - WALL
SPLIT = 29.3                  # between carrier-top ports (<=28.4) and AI-board-bottom ports (>=30.26)
LID_IN = 43.0                 # v6: lid underside bears on the SO-DIMM connector top (43.13) -> 0.13 preload, no vertical play (v5: 44.5)
Z_TOP = LID_IN + WALL
HOLES = [(sx * 38.0, sy * 26.0) for sx in (-1, 1) for sy in (-1, 1)]
POST_R = 3.25                 # corner-post through-holes, dia 6.5 (5.1 AF hex standoff + clearance)
# Jetson Orin NX: 69.6 x 45 module, SO-DIMM connector edge at y~+22 so module spans y -23..+22
# v5: measured heatsink 57.8 x 40, centred in x, ~1 mm from the -y (non-button) edge, top z ~48.3; +1.5 mm
JW = (-28.9 - 1.5, -28.5 - 1.5, 28.9 + 1.5, 11.5 + 1.5)
LIP_T, LIP_H, FIT = 1.6, 5.0, 0.3   # v7: taller lip (v6: 3.0) so the catch sits 2 mm above the split
M_SIDE, M_BOT, M_TOP = 2.0, 2.0, 2.0   # v6: port cutout margins widened for finger/plug access (v5: 1.0, 1.0, 1.5)
# v7: long walls (+-y) get one fitted opening per port (v6: one wide slot per wall, + counterbores)
M_LONG = (0.6, 0.8, 1.0)     # side, bottom, top margins on +-y
PILLAR = 1.2                 # min wall left between two fitted openings (else they merge)
G_CLR = 0.1                  # v7: groove = catch profile + 0.1 (v6: bbox + 0.3)
SNAP_IN = 0.6                # v6: snap interference (v5: 0.3)
FAN_NOTCH = (JW[2] - 0.5, 6.0, JW[2] + 2.5, 10.0)   # v6: fan-cable notch on the +x edge of the heatsink window
BUTTONS = [(5.0, 27.1), (8.75, 27.1)]  # B3U-1000P under the lid outside window

PORT = re.compile(r'JST_GH|PicoBlade|XT30|1054500101|502570|Micro SD|530470410|629105150521|SM06B|nano SIM|1-84952')

# ---- port cutouts, grouped per wall and merged ------------------------------
sides = {"+x": [], "-x": [], "+y": [], "-y": []}
for p in parts:
    leaf = p["path"].split("/")
    if not any(PORT.search(x) for x in leaf[-2:]):
        continue
    x0, y0, z0, x1, y1, z1 = p["bb"]
    dist = {"+x": 41.5 - x1, "-x": x0 + 41.5, "+y": 29.5 - y1, "-y": y0 + 29.5}
    s = min(dist, key=dist.get)
    if dist[s] > 3:
        continue
    u0, u1 = (y0, y1) if "x" in s else (x0, x1)
    ms, mb, mt = M_LONG if "y" in s else (M_SIDE, M_BOT, M_TOP)
    sides[s].append([u0 - ms, z0 - mb, u1 + ms, z1 + mt])

def merge(rs, gap=3.0):  # merge openings whose wall pillar (horizontal or vertical) would be < gap
    rs = [r[:] for r in rs]
    changed = True
    while changed:
        changed = False
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                g2 = gap if max(a[3], b[3]) < SPLIT + 0.5 else 0.0   # vertical merging only within the bottom shell
                if a[0] - gap < b[2] and b[0] - gap < a[2] and a[1] - g2 < b[3] and b[1] - g2 < a[3]:
                    rs[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    rs.pop(j); changed = True; break
            if changed: break
    return rs

cuts = []
recesses = []   # v6: outer counterbores, bottom shell only
for s, rs in sides.items():
    for u0, z0, u1, z1 in merge(rs, PILLAR if "y" in s else 3.0):
        z0 = max(z0, FLOOR_IN + 0.8)   # keep a sill above the floor
        if SPLIT - 2.5 < z1 < SPLIT + 1: z1 = SPLIT + 1   # no slivers at the parting line
        if SPLIT - 1 < z0 < SPLIT + 2.5: z0 = SPLIT - 1
        u0, u1 = max(u0, -(IY if "x" in s else IX) + 0.8), min(u1, (IY if "x" in s else IX) - 0.8)
        if s == "+x": cuts.append((IX - 2, u0, z0, OX + 2, u1, z1))
        if s == "-x": cuts.append((-OX - 2, u0, z0, -IX + 2, u1, z1))
        if s == "+y": cuts.append((u0, IY - 2, z0, u1, OY + 2, z1))
        if s == "-y": cuts.append((u0, -OY - 2, z0, u1, -IY + 2, z1))

# v7: carrier-underside JST-GH rows on the short walls (CAN/USB): open the wall down through the
# case's bottom edge and trim the floor edge in front of them, so the plugs can be gripped from below
notches = []
for s in ("+x", "-x"):
    rows = [p["bb"] for p in parts if any(PORT.search(x) for x in p["path"].split("/")[-2:])
            and p["bb"][5] < 22.0 and (p["bb"][3] > 39 if s == "+x" else p["bb"][0] < -39)]
    if not rows: continue
    u0, u1 = max(min(b[1] for b in rows) - 1.0, -22.6), min(max(b[4] for b in rows) + 1.0, 22.6)   # stay clear of the post holes
    zt = max(b[5] for b in rows) + M_TOP
    sg = 1 if s == "+x" else -1
    xa, xb = sorted((sg * 40.6, sg * (OX + 2)))
    notches.append((xa, u0, Z_BOT - 1, xb, u1, zt))
f = lambda v: f"{v:.2f}"
def box(b): return f"box(x0 = {f(b[0])}, y0 = {f(b[1])}, z0 = {f(b[2])}, x1 = {f(b[3])}, y1 = {f(b[4])}, z1 = {f(b[5])})"

def poly(plane, pts):
    s = f"startProfile({plane}, at = [{f(pts[0][0])}, {f(pts[0][1])}])"
    s += "".join(f" |> line(endAbsolute = [{f(x)}, {f(y)}])" for x, y in pts[1:])
    return s + " |> close()"

L = []
L.append("""// EchoPilot AI + Carrier full-stack snap-fit case, Jetson Orin NX with open heatsink window.
// Generated by tools/gen_kcl.py from EchoMAV ECHOPILOT_FULL_STACK.step (frame: board centre = origin).
// Print: bottom shell as-is, top shell flipped (lid on bed). PLA, 0.4 nozzle.
// Assembly: stack rests on its own bottom posts (screw heads on the floor); cups around each post locate it.
@settings(defaultLengthUnit = mm, kclVersion = 1.0)

fn box(x0, y0, z0, x1, y1, z1) {
  return startSketchOn(offsetPlane(XY, offset = z0))
    |> rectangle(corner = [x0, y0], width = x1 - x0, height = y1 - y0)
    |> extrude(length = z1 - z0)
}

fn cyl(cx, cy, z0, z1, r) {
  return startSketchOn(offsetPlane(XY, offset = z0))
    |> circle(center = [cx, cy], radius = r)
    |> extrude(length = z1 - z0)
}

fn rect(z, hx, hy) {
  return startSketchOn(offsetPlane(XY, offset = z))
    |> rectangle(corner = [-hx, -hy], width = 2 * hx, height = 2 * hy)
}
""")
L.append(f"wall = {WALL}\nsplit = {SPLIT}\n")

# bottom shell: outer box to split, minus cavity, plus lip, posts
L.append("// ---------- bottom shell ----------")
L.append(f"bOuter = {box((-OX, -OY, Z_BOT, OX, OY, SPLIT))}")
L.append(f"bCav = {box((-IX, -IY, FLOOR_IN, IX, IY, SPLIT + 1))}")
L.append("bShell = subtract(bOuter, tools = [bCav])")
# lip: ring inside the wall, rising above the split
li = (IX - FIT - LIP_T, IY - FIT - LIP_T)
L.append(f"lipO = {box((-(IX - FIT), -(IY - FIT), SPLIT - 2, IX - FIT, IY - FIT, SPLIT + LIP_H))}")
L.append(f"lipI = {box((-li[0], -li[1], SPLIT - 3, li[0], li[1], SPLIT + LIP_H + 1))}")
# bond ring: fills the FIT gap below the split so the lip is fused to the wall
L.append(f"lipB = {box((-IX - 0.5, -IY - 0.5, SPLIT - 2, IX + 0.5, IY + 0.5, SPLIT - 0.5))}")
# 45 deg chamfer under the lip ledge: lofted ring from the wall line (bottom) out to the lip's inner face (top)
CH = IX + 0.2 - li[0]            # ledge depth incl. 0.2 overlap into the wall
CH_Z0, CH_Z1 = SPLIT - 2 - CH, SPLIT - 2 + 0.3
L.append(f"chO = {box((-IX - 0.5, -IY - 0.5, CH_Z0, IX + 0.5, IY + 0.5, CH_Z1))}")
L.append(f"chI = loft([rect(z = {f(CH_Z0 - 0.01)}, hx = {f(IX + 0.2)}, hy = {f(IY + 0.2)}), rect(z = {f(CH_Z1 + 0.01)}, hx = {f(li[0] - 0.3)}, hy = {f(li[1] - 0.3)})])")
L.append("chamfer = subtract(chO, tools = [chI])")
L.append("lip0 = subtract(union([lipO, lipB, chamfer]), tools = [lipI])")
# notch the lip + chamfer around the stack's corner posts (hex standoffs reach 0.5 mm into the lip)
prev = "lip0"
for i, (hx, hy) in enumerate(HOLES):
    L.append(f"lipN{i} = subtract({prev}, tools = [{box((hx - 2.8, hy - 2.9, CH_Z0 - 1, hx + 2.8, hy + 2.9, SPLIT + LIP_H + 1))}])"); prev = f"lipN{i}"  # hex standoff bbox 5.0 x 5.2 + 0.3
L.append(f"lipP = {prev}")
# remove the lip wherever it crosses a port opening (otherwise it is an unsupported strip)
prev = "lipP"
# Zoo engine can't union the lip when a lip run crosses x = 0 on the long walls: keep the lip clear of x = -5..0.3 (found by bisection)
LIP_SEAM = (-5.0, -OY - 2, CH_Z0, 0.3, OY + 2, SPLIT + LIP_H)
for i, c in enumerate([c for c in cuts if c[5] > CH_Z0 - 0.5] + [LIP_SEAM]):   # v7: low slots leave the lip intact
    L.append(f"lip{i + 1} = subtract({prev}, tools = [{box((c[0] - 0.5, c[1] - 0.5, CH_Z0 - 1, c[3] + 0.5, c[4] + 0.5, SPLIT + LIP_H + 1))}])")
    prev = f"lip{i + 1}"
L.append(f"lip = {prev}")
# snap bumps on lip outer face (long walls, +-y) and short walls (+-x)
bumps = []
# snap bumps only near the corners of the +-y walls: everywhere else the lip spans port openings
BZ0, BTIP = SPLIT + 2.0, 0.4    # v7: catch 2 mm above the split (v6: 0.8) -> ~1.6 mm of top-shell wall below each groove
for sy in (-1, 1):
    wall_cuts = sorted([(c[0], c[3]) for c in cuts if (c[1] < sy * IY < c[4]) and c[5] > CH_Z0 - 0.5] + [(-5.0, 0.3)])
    free, x = [], -(IX - FIT - 0.6)
    for a, b in wall_cuts:
        if a - 0.6 > x: free.append((x, a - 0.6))
        x = max(x, b + 0.6)
    if IX - FIT - 0.6 > x: free.append((x, IX - FIT - 0.6))
    spans = []
    for x0, x1 in free:
        if x1 - x0 < 5.0: continue
        if x1 - x0 > 28.0: spans += [(x0, x0 + 10.0), ((x0 + x1) / 2 - 5.0, (x0 + x1) / 2 + 5.0), (x1 - 10.0, x1)]
        elif x1 - x0 > 12.0: c_ = (x0 + x1) / 2; spans.append((c_ - 6.0, c_ + 6.0))
        else: spans.append((x0, x1))
    for x0, x1 in spans:
        y_out = sy * (IY + SNAP_IN); y_in = sy * (IY - FIT - 0.2)
        rise = abs(y_out - y_in) / 0.7     # tan(35 deg) ~ 0.7
        prof = [(y_in, BZ0), (y_out, BZ0), (y_out, BZ0 + BTIP), (y_in, BZ0 + BTIP + rise)]
        bumps.append(((x0, x1), prof))
for i, ((xa, xb), prof) in enumerate(bumps):
    pts = prof if prof[1][0] > prof[0][0] else list(reversed(prof))
    L.append(f"bumpP{i} = startSketchOn(offsetPlane(YZ, offset = {f(min(xa, xb))}))")
    L.append(f"bump{i} = {poly(f'bumpP{i}', pts)} |> extrude(length = {f(abs(xb - xa))})")
L.append(f"bU0 = union([bShell, lip])")
L.append(f"bBody = union([bU0, " + ", ".join(f"bump{i}" for i in range(len(bumps))) + "])")

# top shell: from split - fit to top
L.append("\n// ---------- top shell ----------")
L.append(f"tOuter = {box((-OX, -OY, SPLIT + FIT, OX, OY, Z_TOP))}")
L.append(f"tCav = {box((-IX, -IY, SPLIT - 1, IX, IY, LID_IN))}")
L.append("tShell = subtract(tOuter, tools = [tCav])")
L.append("tBody = tShell")

# ---------- cuts ----------
L.append("\n// ---------- cuts ----------")
tool_names = []
for i, c in enumerate(cuts):
    L.append(f"port{i} = {box(c)}")
    tool_names.append(f"port{i}")
# grooves in top shell inner wall for bumps (bump + FIT), enlarged
for i, ((xa, xb), prof) in enumerate(bumps):   # v7: groove follows the catch profile, +G_CLR all round
    (yi, z0), (yo, _), (_, zt), (_, zr) = prof
    sy = 1 if yo > yi else -1
    yi2, yo2 = yi - sy * 0.5, yo + sy * G_CLR
    gp = [(yi2, z0 - G_CLR), (yo2, z0 - G_CLR), (yo2, zt + G_CLR), (yi2, zr + G_CLR + 0.5 * 1.43)]
    gp = gp if gp[1][0] > gp[0][0] else list(reversed(gp))
    L.append(f"grooveP{i} = startSketchOn(offsetPlane(YZ, offset = {f(min(xa, xb) - G_CLR)}))")
    L.append(f"groove{i} = {poly(f'grooveP{i}', gp)} |> extrude(length = {f(abs(xb - xa) + 2 * G_CLR)})")
# lip clearance pocket in top shell is the cavity itself (lip sits inside cavity wall line) ->
# top shell wall overlaps lip region? lip is inside IX/IY, top wall is outside IX/IY: no overlap.
L.append(f"window = {box((JW[0], JW[1], LID_IN - 1, JW[2], JW[3], Z_TOP + 1))}")
L.append(f"fanNotch = {box((FAN_NOTCH[0], FAN_NOTCH[1], LID_IN - 1, FAN_NOTCH[2], FAN_NOTCH[3], Z_TOP + 1))}")
btn = []
for i, (bx, by) in enumerate(BUTTONS):
    L.append(f"btn{i} = cyl(cx = {bx}, cy = {by}, z0 = {LID_IN - 1}, z1 = {Z_TOP + 1}, r = 1.5)")
    btn.append(f"btn{i}")

# each body needs its own tool copies (subtract consumes tools)
L.append("""
fn portTools() {
  return [""" + ", ".join(box(c) for c in cuts) + """]
}
""")
L.append("bottomShellA0 = subtract(bBody, tools = portTools())")
prev = "bottomShellA0"
for i, r in enumerate(recesses):   # clip to the bottom shell height so no sliver faces sit on the split
    r = (r[0], r[1], r[2], r[3], r[4], min(r[5], SPLIT + 0.5))
    L.append(f"bR{i} = subtract({prev}, tools = [{box(r)}])"); prev = f"bR{i}"
for i, n in enumerate(notches):
    L.append(f"bN{i} = subtract({prev}, tools = [{box(n)}])"); prev = f"bN{i}"
L.append(f"bottomShellA = {prev}")
prev = "bottomShellA"
L.append(f"bottomShellS = {prev}")
# through-holes for the stack's metal corner posts (hex standoff 5.1 AF ~5.9 across corners)
prev = "bottomShellS"
for i, (hx, hy) in enumerate(HOLES):
    L.append(f"bH{i} = subtract({prev}, tools = [cyl(cx = {hx}, cy = {hy}, z0 = {f(Z_BOT - 1)}, z1 = {f(FLOOR_IN + 1)}, r = {POST_R})])"); prev = f"bH{i}"
L.append(f"bottomShellH = {prev}")

# ---------- v4: etched labels (3x5 pixel block font, 0.8 mm pixels, 0.5 mm deep) ----------
FONT = {
    "U": ["101", "101", "101", "101", "111"], "S": ["111", "100", "111", "001", "111"],
    "B": ["110", "101", "110", "101", "110"], "C": ["111", "100", "100", "100", "111"],
    "A": ["010", "101", "111", "101", "101"], "N": ["1001", "1101", "1011", "1001", "1001"],
    "E": ["111", "100", "110", "100", "111"], "T": ["111", "010", "010", "010", "010"],
    "H": ["101", "101", "111", "101", "101"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "^": ["010", "111", "010", "010", "010"],
}
PX, DEPTH = 0.8, 0.5

def text_boxes(s, face, uc, vc):
    """face: '+x','-x','-y','+y' walls (v = z) or 'lid' (u = x, v = y). (uc, vc) = text centre."""
    w = sum(len(FONT[ch][0]) + 1 for ch in s) - 1
    u_start, v_top = -w * PX / 2, 2.5 * PX
    out, col = [], 0
    for ch in s:
        g = FONT[ch]
        for r, row in enumerate(g):
            c = 0
            while c < len(row):          # one box per horizontal run of pixels; rows overlap 0.02
                if row[c] == "1":
                    c1 = c
                    while c1 < len(row) and row[c1] == "1": c1 += 1
                    a0, a1 = u_start + (col + c) * PX, u_start + (col + c1) * PX
                    b0, b1 = v_top - (r + 1) * PX, v_top - r * PX
                    out.append((a0, a1, b0, b1)); c = c1
                else:
                    c += 1
        col += len(g[0]) + 1
    res = []
    for a0, a1, b0, b1 in out:
        z0, z1 = vc + b0, vc + b1
        if face == "+x": res.append((OX - DEPTH, uc + a0, z0, OX + 1, uc + a1, z1))        # reads toward +y
        if face == "-x": res.append((-OX - 1, uc - a1, z0, -OX + DEPTH, uc - a0, z1))      # reads toward -y
        if face == "-y": res.append((uc + a0, -OY - 1, z0, uc + a1, -OY + DEPTH, z1))      # reads toward +x
        if face == "lid": res.append((uc + a0, vc + b0, Z_TOP - DEPTH, uc + a1, vc + b1, Z_TOP + 1))  # reads toward +x seen from above
    return res

# carrier ports (bottom shell, strip under the openings, z 9.5-16.3) - lower row labelled from below
LABELS_BOT_V4 = [("CAN", "+x", -13.45, 13.0), ("USB", "+x", 9.1, 13.0), ("^CAN", "-x", 3.6, 13.0)]
# AI-board ports + upper carrier row (top shell)
LABELS_TOP_V4 = [("ETH", "+x", 7.33, 33.0), ("USB", "+x", -3.0, 39.6), ("USB", "-x", 1.4, 42.8),
              ("USB", "-y", -24.0, 42.8), ("B1", "lid", -0.3, 27.1), ("B2", "lid", 13.8, 27.1)]
LABELS_BOT, LABELS_TOP = [], []   # v5: labels removed
def loops_from_rects(rects):
    """Outline loops (outer + holes) of a union of grid-aligned rects. rects: (a0, a1, b0, b1)."""
    us = sorted({round(v, 4) for r in rects for v in r[:2]}); vs = sorted({round(v, 4) for r in rects for v in r[2:]})
    filled = set()
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            cu, cv = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
            if any(r[0] < cu < r[1] and r[2] < cv < r[3] for r in rects): filled.add((i, j))
    edges = {}
    for i, j in filled:   # CCW cell edges; keep those not shared
        for a, b in [((i, j), (i + 1, j)), ((i + 1, j), (i + 1, j + 1)), ((i + 1, j + 1), (i, j + 1)), ((i, j + 1), (i, j))]:
            if (b, a) in edges: del edges[(b, a)]
            else: edges[(a, b)] = 1
    nxt = {}
    for a, b in edges: nxt.setdefault(a, []).append(b)
    loops = []
    def turn_rank(prev, cur, cand):   # prefer left turn (keeps corner-touching loops separate)
        d1 = (cur[0] - prev[0], cur[1] - prev[1]); d2 = (cand[0] - cur[0], cand[1] - cur[1])
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        return 0 if cross > 0 else (1 if cross == 0 else 2)
    while nxt:
        start = next(iter(nxt)); loop = [start]; cur = start; prev = None
        while True:
            cands = nxt[cur]
            b = cands.pop(0) if prev is None else cands.pop(min(range(len(cands)), key=lambda k: turn_rank(prev, cur, cands[k])))
            if not nxt[cur]: del nxt[cur]
            if b == start: break
            loop.append(b); prev, cur = cur, b
        pts = [(us[i], vs[j]) for i, j in loop]
        simp = [p for k, p in enumerate(pts)   # drop collinear points
                if not ((pts[k - 1][0] == p[0] == pts[(k + 1) % len(pts)][0]) or (pts[k - 1][1] == p[1] == pts[(k + 1) % len(pts)][1]))]
        area = sum(simp[k - 1][0] * simp[k][1] - simp[k][0] * simp[k - 1][1] for k in range(len(simp))) / 2
        loops.append((area, simp))
    return loops


def label_chain(base, labels, name):
    prev = base
    for i, (s, fc, u, v) in enumerate(labels):
        bx = text_boxes(s, fc, u, v)
        if fc in ("+x", "-x"): r2 = [(b[1], b[4], b[2], b[5]) for b in bx]; pl, off = "YZ", (OX if fc == "+x" else -OX)
        elif fc in ("+y", "-y"): r2 = [(b[0], b[3], b[2], b[5]) for b in bx]; pl, off = "XZ", (OY if fc == "+y" else -OY)
        else: r2 = [(b[0], b[3], b[1], b[4]) for b in bx]; pl, off = "XY", Z_TOP
        if pl == "XZ": off = -off       # XZ plane normal is -Y in KCL
        lp = loops_from_rects(r2)
        L.append(f"{name}P{i} = startSketchOn(offsetPlane({pl}, offset = {f(off)}))")
        outs = [p for a, p in lp if a > 0]; holes = [p for a, p in lp if a < 0]
        names = []
        for k, o in enumerate(outs):
            # holes inside this outer loop
            hs = [h for h in holes if min(x for x, _ in o) <= h[0][0] <= max(x for x, _ in o) and min(y for _, y in o) <= h[0][1] <= max(y for _, y in o)]
            expr = poly(f"{name}P{i}", o) + "".join(f" |> subtract2d(tool = {poly(f'{name}P{i}', list(reversed(h)))})" for h in hs)
            L.append(f"{name}G{i}_{k} = {expr} |> extrude(length = {f(2 * DEPTH)}, symmetric = true)")
            names.append(f"{name}G{i}_{k}")
        for k, g in enumerate(names):
            L.append(f"{name}L{i}_{k} = subtract({prev}, tools = [{g}])"); prev = f"{name}L{i}_{k}"
    return prev
L.append(f"bottomShell = {label_chain('bottomShellH', LABELS_BOT, 'bottomShellLab')}")
L.append("topShellA = subtract(tBody, tools = portTools())")
prev = "topShellA"
for i, t in enumerate([f"groove{i}" for i in range(len(bumps))] + ["window", "fanNotch"] + btn):
    L.append(f"tS{i} = subtract({prev}, tools = [{t}])"); prev = f"tS{i}"
L.append(f"topShellL = {prev}")
L.append(f"topShellB = {label_chain('topShellL', LABELS_TOP, 'tSLab')}")
# drop the unused per-port vars (they were for readability) -> remove them to avoid stray bodies
L = [l for l in L if not l.startswith("port")]

# Split into sections so each output file only builds the bodies it needs
# (every unconsumed solid in a KCL file is part of the exported model).
TOP_PREFIX = ("fanNotch", "grooveP", "tHole", "tOuter", "tCav", "tShell", "pad", "tBody", "groove", "window", "btn", "topShell", "tS")
BOT_PREFIX = ("bN", "bR", "boss", "bB", "ch", "bH", "bOuter", "bCav", "bShell", "lip", "bump", "post", "pin", "bBody", "bottomShell", "bU")
def keep(line, drop):
    return not line.startswith(drop)

outdir = ROOT / "cad" / "v7"
files = {
    # assembly view: both shells, top exploded 15 mm
    "main.kcl": (L, """
// Assembly view: top shell exploded 15 mm above (set explode = 0 for the assembled position).
explode = 15
topShell = topShellB |> translate(z = explode)
"""),
    # print orientation: bottom shell as modelled (floor on the bed)
    "print_bottom/main.kcl": ([l for l in L if keep(l, TOP_PREFIX)], f"""
// Print orientation: floor on the bed at z = 0.
bottomPrint = bottomShell |> translate(z = {-Z_BOT:.2f})
"""),
    # print orientation: top shell flipped, lid on the bed
    "print_top/main.kcl": ([l for l in L if keep(l, BOT_PREFIX)], f"""
// Print orientation: flipped so the lid is on the bed at z = 0.
topPrint = topShellB
  |> rotate(roll = 180)
  |> translate(z = {Z_TOP - 93.0 + 2 * (46.5 - Z_TOP):.2f})  // translate after rotate acts in the flipped frame; offset measured from the exported STL
"""),
}
for name, (lines, tail) in files.items():
    out = outdir / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n" + tail)
    print(out)
print(len(cuts), "cutouts")
for c in cuts: print([round(v, 2) for v in c])
