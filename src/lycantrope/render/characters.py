"""Skinned characters (TEC-08): Rowan, enemies, held items and worn armor.

Each character type has one mesh on the GPU; every character draws it with its own joint
matrices (computed from baked clips on the CPU, skinned in the vertex shader). Items are
rigid meshes attached to a joint. Armor (ARS-05) is the outfit mesh with Rowan's skin
weights, split into head/arms/torso/legs; the body parts it covers aren't drawn.
"""
from __future__ import annotations

import hashlib
import math
import re
import random
from dataclasses import dataclass, field
from pathlib import Path

from pyglm import glm
import moderngl
import numpy as np

from lycantrope.core.paths import ASSETS, ROOT
from lycantrope.render.camera import frustum_planes
from lycantrope.render.gltf import (PARTS, SLOTS, Clip, MeshData, Skeleton, fit_outfit, load_mesh, load_skeleton,
                                    nearest_neighbours, part_of, triangle_parts, triangle_slots)
from lycantrope.render.shaders import ShaderLibrary, set_uniform
from lycantrope.world.stats import kill_xp
from lycantrope.world.actors import (Actor, AiParams, AttackTokens, ClipInfo, Enemy, Rowan,
                                     load_character_data, load_spawns, separate)
from lycantrope.world.collision import Colliders
from lycantrope.world.heightfield import Heightfield

MODELS = ASSETS / "models" / "meshy"
CACHE = ROOT / "assets" / "cache"
MAX_JOINTS = 64
DRAW_DISTANCE = 300.0
WADE_DEPTH = 0.9           # meters, for a 1.75 m character (scaled by height)
DEATH_RELOAD_S = 7.0           # Rowan down: the death screen shows this long, then the last save loads
SWIM_IN, SWIM_OUT = 1.2, 1.0   # Rowan starts swimming deeper than this, wades again shallower than that
STATIC_CLIPS = {"idle": ClipInfo(1.0, True), "walk": ClipInfo(1.0, True), "run": ClipInfo(1.0, True),
                "alert": ClipInfo(1.0, True), "attack1": ClipInfo(0.9, False), "attack2": ClipInfo(0.9, False),
                "hit": ClipInfo(0.5, False), "death": ClipInfo(1.0, False)}
RADIUS = {"bandit_lean": 0.38, "bandit_stocky": 0.45, "guard": 0.4, "shepherd": 0.38, "smith_hand": 0.42, "merchant": 0.38, "dairymaid": 0.33,
          "weaver": 0.35, "seller": 0.35, "rowan": 0.4, "goblin": 0.35, "wolf": 0.5, "bear": 0.9, "cultist": 0.38, "cultist_f": 0.35, "leng_raider": 0.4, "leng_captain": 0.45, "bruiser": 0.55, "battlemage": 0.4, "cow": 0.8, "villager_m": 0.35, "villager_f": 0.33, "farmer": 0.38}


# ---------------------------------------------------------------------------- #
@dataclass
class GpuMesh:
    vbo: moderngl.Buffer
    ibo: moderngl.Buffer
    ranges: list[tuple[int, int]]          # per slot (first index, count); one range if unsplit
    texture: moderngl.Texture | None
    vao: moderngl.VertexArray | None = None
    triangles: int = 0


def upload(ctx: moderngl.Context, m: MeshData, slots: np.ndarray | None = None, n_slots: int = len(SLOTS)) -> GpuMesh:
    V = len(m.pos)
    joints = m.joints.astype(np.float32) if m.joints is not None else np.zeros((V, 4), np.float32)
    weights = m.weights if m.weights is not None else np.tile([1.0, 0, 0, 0], (V, 1)).astype(np.float32)
    color = m.color if m.color is not None else np.ones((V, 3), np.float32)
    data = np.hstack([m.pos, m.nrm, m.uv, joints, weights, color]).astype("f4")
    tri = m.idx.reshape(-1, 3)
    ranges = []
    if slots is not None:
        order = np.argsort(slots, kind="stable")
        tri = tri[order]
        start = 0
        for s in range(n_slots):
            n = int((slots == s).sum()) * 3
            ranges.append((start, n))
            start += n
    else:
        ranges.append((0, tri.size))
    tex = None
    if m.texture is not None:
        img = m.texture
        tex = ctx.texture(img.size, 3, img.tobytes())
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        tex.anisotropy = 4.0
    return GpuMesh(ctx.buffer(data.tobytes()), ctx.buffer(np.ascontiguousarray(tri, np.uint32).tobytes()),
                   ranges, tex, triangles=len(tri))


def normalized_static(m: MeshData, height: float) -> MeshData:
    """Feet on y = 0, centered in x/z, scaled to a height in meters."""
    lo, hi = m.pos.min(axis=0), m.pos.max(axis=0)
    s = height / (hi[1] - lo[1])
    m.pos = ((m.pos - [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]) * s).astype(np.float32)
    return m


# ---------------------------------------------------------------------------- #
@dataclass
class Item:
    gpu: GpuMesh


def load_item(ctx, spec: dict) -> tuple[MeshData, Item]:
    m = load_mesh(MODELS / spec["model"], skinned=False)
    p = m.pos.astype(np.float64)
    if "length_m" in spec:
        # blade/knife: put the grip at the origin, tip along +Y, edge along +Z
        axis = "xyz".index(spec.get("tip", "-x")[-1])
        sign = -1.0 if spec.get("tip", "-x").startswith("-") else 1.0
        along = p[:, axis] * sign                       # grows toward the tip
        length = along.max() - along.min()
        s = spec["length_m"] / length
        grip = along.min() + spec.get("grip_from_end", 0.1) * length
        others = [i for i in range(3) if i != axis]
        # thinner of the other two axes is the blade's thickness
        thick, edge = sorted(others, key=lambda i: np.ptp(p[:, i]))
        ctr = (p.max(axis=0) + p.min(axis=0)) / 2
        q = np.zeros_like(p)
        q[:, 1] = (along - grip) * s
        q[:, 2] = (p[:, edge] - ctr[edge]) * s
        q[:, 0] = (p[:, thick] - ctr[thick]) * s
        # keep the basis right-handed (mirror the thickness if needed)
        basis = np.zeros((3, 3))
        basis[thick, 0], basis[axis, 1], basis[edge, 2] = 1, sign, 1
        if np.linalg.det(basis) < 0:
            q[:, 0] = -q[:, 0]
        n = np.zeros_like(m.nrm)
        n[:, 1] = m.nrm[:, axis] * sign
        n[:, 2] = m.nrm[:, edge]
        n[:, 0] = m.nrm[:, thick] * (-1 if np.linalg.det(basis) < 0 else 1)
        m.pos, m.nrm = q.astype(np.float32), n.astype(np.float32)
        frac = (along - along.min()) / length
        c0 = np.array(spec.get("color", [0.6, 0.6, 0.6]), np.float32)
        c1 = np.array(spec.get("end_color", spec.get("color", [0.6, 0.6, 0.6])), np.float32)
        m.color = np.where((frac < spec.get("end_fraction", 0.0))[:, None], c1, c0).astype(np.float32)
        if m.texture is not None:              # textured: the texture has the colours
            m.color = np.ones_like(m.color)
    else:
        lo, hi = p.min(axis=0), p.max(axis=0)
        s = spec.get("height_m", 0.3) / (hi[1] - lo[1])
        m.pos = ((p - (lo + hi) / 2) * s).astype(np.float32)
    return m, Item(upload(ctx, m))


def look_basis(origin, y_dir, z_hint) -> np.ndarray:
    """4x4 with +Y along y_dir, +Z as close to z_hint as possible, right-handed."""
    y = np.asarray(y_dir, float)
    y /= np.linalg.norm(y)
    z = np.asarray(z_hint, float) - y * np.dot(z_hint, y)
    z /= np.linalg.norm(z)
    x = np.cross(y, z)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, origin
    return m


@dataclass
class Attachment:
    item: Item
    joint: int
    offset: np.ndarray            # joint world (bind) -> item, 4x4
    # two-handed weapons: where the other hand grips, in the item's frame (grip at the origin,
    # +Y toward the head), and that hand's joints (upper arm, forearm, hand)
    second_grip: np.ndarray | None = None
    second_chain: tuple[int, int, int] | None = None
    in_hand: bool = False         # put away while swimming (or sheathed)
    sheathed: bool = False        # the same item worn on the back: drawn only while it's put away
    shield: bool = False          # stays on the arm when the sword is sheathed (but not while swimming)


def _rotation_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """3x3 rotation turning direction a onto direction b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:                                   # opposite: turn 180 degrees about any perpendicular
        p = np.cross(a, [1.0, 0.0, 0.0])
        if np.linalg.norm(p) < 1e-6:
            p = np.cross(a, [0.0, 1.0, 0.0])
        p /= np.linalg.norm(p)
        return 2.0 * np.outer(p, p) - np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1.0 + c)


def two_bone_ik(W: np.ndarray, chain: tuple[int, int, int], target: np.ndarray) -> None:
    """Bend an arm (upper arm, forearm, hand joint world matrices, in place) so the hand reaches
    target, keeping the elbow bending the way the animation had it."""
    i0, i1, i2 = chain
    S, E, H = W[i0][:3, 3].copy(), W[i1][:3, 3].copy(), W[i2][:3, 3].copy()
    a, b = np.linalg.norm(E - S), np.linalg.norm(H - E)
    to_t = target - S
    d = float(np.clip(np.linalg.norm(to_t), abs(a - b) + 1e-4, a + b - 1e-4))
    dir_t = to_t / max(np.linalg.norm(to_t), 1e-6)
    pole = (E - S) - dir_t * np.dot(E - S, dir_t)               # which way the elbow points now
    if np.linalg.norm(pole) < 1e-5:
        pole = np.cross(dir_t, [0.0, 1.0, 0.0])
    pole /= np.linalg.norm(pole)
    cos_s = (a * a + d * d - b * b) / (2 * a * d)                # law of cosines at the shoulder
    sin_s = np.sqrt(max(0.0, 1.0 - cos_s * cos_s))
    E2 = S + a * (dir_t * cos_s + pole * sin_s)
    H2 = S + dir_t * d
    R1 = _rotation_between(E - S, E2 - S)
    W[i0][:3, :3] = R1 @ W[i0][:3, :3]
    R2 = _rotation_between(R1 @ (H - E), H2 - E2)
    W[i1][:3, :3] = R2 @ R1 @ W[i1][:3, :3]
    W[i1][:3, 3] = E2
    W[i2][:3, :3] = R2 @ R1 @ W[i2][:3, :3]
    W[i2][:3, 3] = H2


# ---------------------------------------------------------------------------- #
@dataclass
class Outfit:
    """One NPC outfit (WLD-26) fitted over a villager body, split by PARTS. Its three pieces are
    worn separately: head (hat/hood), top (torso, arms, hands) and bottom (legs, feet)."""
    key: str
    gpu: GpuMesh
    pieces: dict[str, list[int]]          # piece -> PARTS indices it draws (only pieces it has)
    covers: dict[str, np.ndarray]         # piece -> mask of the body's triangles it sits over (hidden)


PIECE_PARTS = {"head": ("head",), "top": ("torso", "arms", "hands"), "bottom": ("legs", "feet")}


@dataclass
class CharType:
    key: str
    skel: Skeleton | None
    body: GpuMesh
    clips: dict[str, Clip]
    info: dict[str, ClipInfo]
    speeds: dict[str, float]
    ai: AiParams | None
    attachments: list[Attachment] = field(default_factory=list)
    armor_sets: dict[str, GpuMesh] = field(default_factory=dict)   # armor set id -> fitted mesh, split by SLOTS
    armor_wear: dict[str, str] = field(default_factory=dict)       # body slot -> the armor set worn there
    item_cache: dict[str, "Item"] = field(default_factory=dict)    # held/hung item id -> its GPU mesh
    dress: tuple | None = None    # Rowan: (body mesh, bind pose, sheath slot), to re-dress from his inventory
    height: float = 1.0           # in the world, after scale
    scale: float = 1.0            # rigs Meshy left at their own size (quadrupeds) -> height_m
    lift: float = 0.0             # raise the rig so its bind-pose feet sit on y = 0 (rig units)
    turn: float = 0.0             # radians about y so the model faces +z (Meshy doesn't always)
    spell: dict | None = None     # casters: projectile look (speed_m_s, radius_m, color)
    float_m: dict[str, float] = field(default_factory=dict)   # swim clips: water level, in rig units above the feet
    cast_hand: int = -1           # joint the cast animation raises (where the Rite's light gathers)
    cast_release: float = 0.55    # fraction of the cast clip where that hand is highest
    outfits: list[Outfit] = field(default_factory=list)       # NPC outfit kit
    body_tris: np.ndarray | None = None                        # body triangles, for per-outfit body variants
    body_variants: dict = field(default_factory=dict)          # worn pieces -> body GpuMesh without covered bits
    outfit_chance: dict[str, float] = field(default_factory=dict)
    voices: list[str] = field(default_factory=list)          # voice pool (data/voices.json names)
    name: str = ""                                            # shown in subtitles
    lines: str = ""                                           # which line set it speaks (npc_lines.json role)
    jaw: int = -1                 # extra joint (index after the rig's own) that opens the jaw
    jaw_of: int = -1              # the head joint it hangs from
    jaw_pivot: np.ndarray | None = None   # mesh-space rotation pivot and axis for the jaw
    jaw_axis: np.ndarray | None = None


def _fit_cached(body: MeshData, skel: Skeleton, outfit_path: Path, rig_path: Path) -> MeshData:
    outfit = load_mesh(outfit_path, skinned=False)
    h = hashlib.sha1(f"{outfit_path.stat().st_size}:{outfit_path.stat().st_mtime_ns}:"
                     f"{rig_path.stat().st_size}:{rig_path.stat().st_mtime_ns}:v1".encode()).hexdigest()[:16]
    cache = CACHE / f"armor_{outfit_path.parent.parent.parent.name}_{h}.npz"
    if cache.exists():
        d = np.load(cache)
        return MeshData(d["pos"], d["nrm"], outfit.uv, outfit.idx, d["joints"], d["weights"], outfit.texture)
    fit = fit_outfit(body, skel, outfit)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, pos=fit.pos, nrm=fit.nrm, joints=fit.joints, weights=fit.weights)
    return fit


COVER_M = 0.035              # body is hidden under cloth this close (outfits sit ~2-4 cm out)
HAT_CLEAR_M = 0.03           # hats and hoods are lifted at least this far off the head (clear of the hair)
POKE_M = 0.15                # ...and where it pokes out through the cloth, up to this far


JAW_DEG = 12.0               # how far the jaw drops at full loudness


def add_jaw(t: "CharType", body: MeshData, skel: Skeleton) -> None:
    """Give a talking NPC a jaw: an extra joint after the rig's own, hinged below the ears, carrying
    the chin and lower face (weights fade out toward the mouth line and the back of the head).
    Must run before the body is uploaded."""
    if "Head" not in skel.names or len(skel.names) + 1 > MAX_JOINTS:
        return
    head = skel.joint_index("Head")
    m2w = (skel.bind_world() @ skel.ibm)[0]
    pw = body.pos @ m2w[:3, :3].T + m2w[:3, 3]
    hw = (body.joints == head) * body.weights
    on_head = hw.sum(axis=1) > 0.5
    if on_head.sum() < 50:
        return
    hp = pw[on_head]
    bind = skel.bind_world()
    head_p = bind[head][:3, 3]
    # landmarks from the rig's own joints, not the head's outline (hats, hoods and beards stretch that)
    top = bind[skel.joint_index("head_end")][:3, 3] if "head_end" in skel.names else head_p + [0, 0.28, 0]
    face = bind[skel.joint_index("headfront")][:3, 3] if "headfront" in skel.names else head_p + [0, 0, 0.1]
    H = float(top[1] - head_p[1])
    if H < 0.15:                                                   # a misplaced head-top marker: use the mesh
        H = float(hp[:, 1].max() - head_p[1])
    zc, zf = float(head_p[2]), float(max(face[2], head_p[2] + 0.05))
    mouth = head_p[1] + 0.33 * H                                   # mouth line, a third of the way up
    below = np.clip((mouth - pw[:, 1]) / (0.1 * H), 0.0, 1.0)      # full below the mouth, fading above it
    front = np.clip((pw[:, 2] - zc) / (zf - zc) * 1.2, 0.0, 1.0)
    wj = below * front * hw.sum(axis=1) * (pw[:, 1] > head_p[1] - 0.25 * H)   # chin and beard, not the chest
    if (wj > 0.3).sum() < 10:
        return
    jaw = len(skel.names)
    j, w = body.joints.copy(), body.weights.copy()
    rows = np.nonzero(wj > 0.01)[0]
    hslot = np.argmax(np.where(j[rows] == head, w[rows], -1.0), axis=1)        # the vertex's head slot
    other = np.where(np.arange(4)[None, :] == hslot[:, None], np.inf, w[rows])
    free = np.argmin(other, axis=1)                                           # its lightest other slot
    w[rows, hslot] += w[rows, free]               # fold that slot's weight into the head...
    amount = w[rows, hslot] * wj[rows]            # ...then hand the jaw its share of the head
    w[rows, hslot] -= amount
    j[rows, free] = jaw
    w[rows, free] = amount
    body.joints, body.weights = j, w.astype(np.float32)
    w2m = np.linalg.inv(m2w)
    pivot_w = np.array([float(head_p[0]), mouth + 0.05 * H, zc - 0.01])   # hinge just below the ears
    t.jaw, t.jaw_of = jaw, head
    t.jaw_pivot = pivot_w @ w2m[:3, :3].T + w2m[:3, 3]
    ax = w2m[:3, :3] @ np.array([1.0, 0.0, 0.0])
    t.jaw_axis = ax / np.linalg.norm(ax)


def jaw_matrix(t: "CharType", open01: float) -> np.ndarray:
    """Mesh-space rotation of the jaw about its hinge, applied before the head's own skinning."""
    a = math.radians(JAW_DEG) * open01
    x, y, z = t.jaw_axis
    c, s, C = math.cos(a), math.sin(a), 1 - math.cos(a)
    R = np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                  [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                  [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t.jaw_pivot - R @ t.jaw_pivot
    return M


def _vertex_colors(m: MeshData) -> np.ndarray | None:
    """Texture colour under each vertex (0..1 RGB), or None without a texture."""
    if m.texture is None or m.uv is None:
        return None
    tex = np.asarray(m.texture.convert("RGB"), np.float32) / 255.0
    h, w = tex.shape[:2]
    u = np.clip((m.uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(int)
    v = np.clip((m.uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(int)
    return tex[v, u]


def _like(colors: np.ndarray, ref: np.ndarray, chroma: float = 0.03) -> np.ndarray:
    """Same hue as ref, allowing for baked light and shade (brightness 0.45x to 1.7x)."""
    b = colors.sum(axis=1) + 1e-4
    rb = float(ref.sum()) + 1e-4
    hue = np.abs(colors / b[:, None] - ref / rb).max(axis=1)
    return (hue < chroma) & (b > 0.45 * rb) & (b < 1.7 * rb)


def load_outfit(ctx, body: MeshData, skel: Skeleton, path: Path, rig_path: Path) -> Outfit:
    """Fit an outfit made on a grey mannequin over this body, drop the mannequin's own skin and face,
    and work out which of the body's parts each piece can hide.

    The mannequin's skin comes out blue-grey or flat mid-grey (once in a while a human face), and its
    A-pose arms don't line up with the villager's, so: the outfit's hands always go (the villager's own
    hands show), so does anything on the front of the face, and so does mannequin-coloured skin on the
    head, arms and chest."""
    fit = _fit_cached(body, skel, path, rig_path)
    m2w = (skel.bind_world() @ skel.ibm)[0]
    bw = body.pos @ m2w[:3, :3].T + m2w[:3, 3]
    ow = fit.pos @ m2w[:3, :3].T + m2w[:3, 3]
    _, dd = nearest_neighbours(ow, bw, k=2)
    near = dd[:, 0]
    vpart = np.array([PARTS.index(part_of(n)) for n in skel.names])
    main = fit.joints[np.arange(len(fit.joints)), np.argmax(fit.weights, axis=1)]
    part = vpart[main]
    P = PARTS.index
    hd = bw[vpart[body.joints[np.arange(len(body.joints)), np.argmax(body.weights, axis=1)]] == P("head")]
    face_front = (ow[:, 2] > hd[:, 2].mean() + 0.02) & (ow[:, 1] < hd[:, 1].max() - 0.07)
    drop = (part == P("hands")) | ((part == P("head")) & face_front & (near < 0.04))
    c = _vertex_colors(fit)
    if c is not None:
        spread, bright = c.max(axis=1) - c.min(axis=1), c.mean(axis=1)
        bluish = (c[:, 2] > c[:, 0] + 0.03) & (spread < 0.22) & (bright > 0.3) & (bright < 0.92)
        grey = (spread < 0.05) & (bright > 0.3) & (bright < 0.62)
        upper = np.isin(part, [P("head"), P("arms"), P("torso")])
        drop |= bluish | (grey & upper)
    # hats and hoods: everything above the neck moves with the head (a brim near the shoulders
    # would otherwise borrow the shoulders' weights and flap)
    if "neck" in skel.names and "Head" in skel.names:
        above = ow[:, 1] > skel.bind_world()[skel.joint_index("neck")][1, 3] + 0.03
        fit.joints = fit.joints.copy()
        fit.weights = fit.weights.copy()
        fit.joints[above] = [skel.joint_index("Head"), 0, 0, 0]
        fit.weights[above] = [1.0, 0.0, 0.0, 0.0]
        # lift hats, hoods and scarves clear of the hair: anything closer to the head than
        # HAT_CLEAR_M moves straight out from the middle of the head, so it sits over the hair
        # instead of the hair poking through it in patches
        hc = skel.bind_world()[skel.joint_index("Head")][:3, 3] + [0.0, 0.07, 0.0]
        lift = (part == P("head")) & (near < HAT_CLEAR_M)
        if lift.any():
            d = ow[lift] - hc
            d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
            ow = ow.copy()
            ow[lift] += d * (HAT_CLEAR_M - near[lift])[:, None]
            w2m = np.linalg.inv(m2w)
            fit.pos = (ow @ w2m[:3, :3].T + w2m[:3, 3]).astype(np.float32)
    tri = fit.idx.reshape(-1, 3)
    keep_tri = drop[tri].sum(axis=1) < 2
    tri_part = triangle_parts(fit, skel.names)
    before = np.bincount(tri_part, minlength=len(PARTS))
    kept = MeshData(fit.pos, fit.nrm, fit.uv, np.ascontiguousarray(tri[keep_tri].ravel()), fit.joints,
                    fit.weights, fit.texture)
    kparts = tri_part[keep_tri]
    after = np.bincount(kparts, minlength=len(PARTS))
    gpu = upload(ctx, kept, kparts, len(PARTS))
    P = PARTS.index
    pieces, covers = {}, {}
    if after[P("head")] > 150 and after[P("head")] >= 0.6 * before[P("head")]:
        # a hat that lost much of itself with the mannequin's skin is only scraps: not worn
        pieces["head"] = [P("head")]          # hats and hoods sit on the villager's own head: hide nothing
    if after[P("torso")] > 300:
        pieces["top"] = [P("torso"), P("arms"), P("hands")]
    if after[P("legs")] > 200:
        pieces["bottom"] = [P("legs"), P("feet")]
    # hide exactly the bits of the body each piece sits over: a body triangle goes when the piece's
    # cloth is within COVER_M of all three corners. Short sleeves, necklines and any hole left by the
    # mannequin's skin keep showing the villager underneath. Head and hands are never hidden.
    btri = body.idx.reshape(-1, 3)
    bpart = triangle_parts(body, skel.names)
    for piece in ("top", "bottom"):
        if piece not in pieces:
            continue
        sel = tri[keep_tri][np.isin(kparts, pieces[piece])]
        if len(sel) < 10:
            continue
        corners = ow[sel]                                          # (T, 3, 3)
        a0, a1, a2 = corners[:, 0], corners[:, 1], corners[:, 2]   # points across each triangle, not
        samples = np.concatenate([a0, a1, a2, (a0 + a1 + a2) / 3,  # just its corners: big flat panels
                                  (a0 + a1) / 2, (a1 + a2) / 2, (a2 + a0) / 2,   # have far-apart vertices
                                  (4 * a0 + a1 + a2) / 6, (a0 + 4 * a1 + a2) / 6, (a0 + a1 + 4 * a2) / 6])
        n = (fit.nrm[sel] @ m2w[:3, :3].T).sum(axis=1)             # the cloth's outward direction
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-8)
        normals = np.tile(n, (10, 1))
        idx, d = nearest_neighbours(bw, samples, k=2)
        i0, d0 = idx[:, 0], d[:, 0]
        # hidden: right under the cloth, or poking out through it (body in front of the cloth, nearby);
        # a wrist past a short cuff sits beside the cloth, not in front of it, so it stays
        out = np.einsum("ij,ij->i", bw - samples[i0], normals[i0])
        bvpart = vpart[body.joints[np.arange(len(body.joints)), np.argmax(body.weights, axis=1)]]
        trunk = np.isin(bvpart, [P("torso"), P("legs"), P("feet")])   # arms: short sleeves sit right over them
        close = (d0 < COVER_M) | (trunk & (d0 < POKE_M) & (out > 0.4 * d0))
        covers[piece] = close[btri].all(axis=1) & ~np.isin(bpart, [P("head"), P("hands")])
    return Outfit(path.parent.parent.parent.name, gpu, pieces, covers)


def load_type(ctx, key: str, spec: dict, items: dict, armor_specs: dict) -> CharType:
    rig = MODELS / spec["rig"] if spec.get("rig") else None
    ai = AiParams(**{k: tuple(v) if isinstance(v, list) else v for k, v in spec["ai"].items()}) if "ai" in spec else None
    idle = spec.get("clips", {}).get("idle")
    animated = rig is not None and rig.exists() and idle is not None and (MODELS / idle["file"]).exists()
    if rig is not None and rig.exists() and not animated and "static" in spec:
        print(f"characters: {key} is rigged but has no idle clip yet; drawing the static model")
    if animated or (rig is not None and rig.exists() and "static" not in spec):
        skel = load_skeleton(rig)
        body = load_mesh(rig)
        if "skirt" in spec:
            soften_skirt(body, skel, spec["skirt"])
        clips, info = {}, {}
        for name, c in spec["clips"].items():
            f = MODELS / c["file"]
            if not f.exists():
                continue
            clip = skel.bake(f, c["clip"], loop=c.get("loop", False), retarget=c.get("retarget", False),
                             speed=c.get("speed", 1.0), name=name)
            if c.get("mirror"):                   # e.g. a right-handed cast played with the left hand
                from lycantrope.render.procedural import mirror_clip
                clip = mirror_clip(skel, clip)
            if c.get("reverse"):                  # played backwards: a side-step that steps the other way
                clip = Clip(clip.name + "_reversed", np.ascontiguousarray(clip.world[::-1]), clip.duration,
                            clip.loop, clip.native_speed, clip.speed)
            clips[name] = clip
            info[name] = ClipInfo(clip.duration, clip.loop, clip.speed, c.get("move_speed", 0.0))
        float_m = {}
        if spec.get("jump") == "procedural" and "jump" not in clips:
            from lycantrope.render.procedural import make_jump_clip
            jc = make_jump_clip(skel)
            if jc is not None:
                clips["jump"] = jc
                info["jump"] = ClipInfo(jc.duration, False, 1.0, 0.0)
        if spec.get("swim") == "procedural" and "swim" not in clips:
            from lycantrope.render.procedural import make_swim_clips
            for name, (clip, level) in make_swim_clips(skel).items():
                clips[name] = clip
                info[name] = ClipInfo(clip.duration, True, 1.0, 1.5 if name == "swim" else 0.0)
                float_m[name] = level
        bind = skel.bind_world()
        m2w = bind[0] @ skel.ibm[0]
        bind_y = body.pos @ m2w[:3, 1] + m2w[1, 3]
        height = float(np.ptp(bind_y))
        scale = spec["height_m"] / height if "height_m" in spec else 1.0
        # Meshy's quadruped rigs put the origin mid-body, so lift them onto the ground
        t = CharType(key, skel, None, clips, info, spec["speeds"], ai, height=height * scale, scale=scale,
                     lift=-float(bind_y.min()), turn=math.radians(spec.get("turn_deg", 0.0)))
        t.float_m = {k: v + t.lift for k, v in float_m.items()}
        t.float_m.update(spec.get("swim_float_m", {}))
        if "cast" in clips:                       # the hand the cast raises highest is the casting hand
            ys = {h: clips["cast"].world[:, skel.joint_index(h), 1, 3] for h in ("LeftHand", "RightHand")
                  if h in skel.names}
            if ys:
                hand = max(ys, key=lambda h: float(ys[h].max()))
                t.cast_hand = skel.joint_index(hand)
                t.cast_release = float(np.argmax(ys[hand])) / max(1, len(ys[hand]) - 1)
        t.voices = list(spec.get("voices", []))
        t.lines = spec.get("lines", "")
        t.name = re.sub(r"\s*\(.*\)\s*$", "", spec.get("name", key))
        if spec.get("outfits"):                   # NPC outfit kit: fitted pieces, body split by part
            for path in spec["outfits"]:
                f = MODELS / path
                if f.exists():
                    t.outfits.append(load_outfit(ctx, body, skel, f, rig))
            t.outfit_chance = dict(spec.get("outfit_chance", {}))
            if t.outfits:
                t.body_tris = body.idx.reshape(-1, 3).astype(np.uint32)
        if t.voices:                              # a jaw for talking (Meshy rigs have no face bones);
            add_jaw(t, body, skel)                # after the outfits, which read the rig's own joints
        # armor first: it decides which body parts are drawn
        slots = None
        eq = spec.get("equipment", {})
        # Rowan (dress_from_inventory) gets every armor set fitted, and wears what his inventory says
        sets = list(armor_specs) if spec.get("dress_from_inventory") else [eq.get("armor")]
        for sid in sets:
            if sid not in armor_specs:
                continue
            outfit_path = MODELS / armor_specs[sid]["model"]
            if outfit_path.exists():
                fit = _fit_cached(body, skel, outfit_path, rig)
                t.armor_sets[sid] = upload(ctx, fit, triangle_slots(fit, skel.names))
        if eq.get("armor") in t.armor_sets:
            t.armor_wear = {s: eq["armor"] for s in armor_specs[eq["armor"]].get("slots", SLOTS)}
        if t.armor_sets:
            slots = triangle_slots(body, skel.names)
        t.body = upload(ctx, body, slots)
        # held and hung items
        for slot, item_id in eq.items():
            if slot != "armor":
                attach_item(ctx, t, bind, body, slot, item_id, items, spec.get("sheath"))
        if spec.get("dress_from_inventory"):
            t.dress = (body, bind, spec.get("sheath"))
        return t
    # not rigged yet: a static mesh moved by code
    m = normalized_static(load_mesh(MODELS / spec["static"], skinned=False), spec.get("height_m", 1.0))
    return CharType(key, None, upload(ctx, m), {}, dict(STATIC_CLIPS), spec["speeds"], ai,
                    height=spec.get("height_m", 1.0))


def attach_item(ctx, t: CharType, bind: np.ndarray, body: MeshData, slot: str, item_id: str, items: dict,
                sheath: str | None = None) -> None:
    """Hang one item (characters.json 'items') on a type: in a hand, on a hip, or strapped to the forearm
    (shields). A sword in the sheath slot also gets a copy across the back, drawn while it's put away."""
    if item_id not in items:
        return
    ispec = items[item_id]
    if not (MODELS / ispec["model"]).exists():
        return
    item = t.item_cache.get(item_id)
    if item is None:
        _m, item = load_item(ctx, ispec)
        t.item_cache[item_id] = item
    skel = t.skel
    att = place_item(skel, bind, slot, item, body, ispec)
    if ispec.get("two_handed") and slot in ("right_hand", "left_hand"):
        other = "Left" if slot == "right_hand" else "Right"
        L = ispec["length_m"]
        # the second hand sits this far from the main grip, toward the end of the handle
        gap = (ispec.get("grip_from_end", 0.1) - ispec.get("second_grip_from_end", 0.08)) * L
        att.second_grip = np.array([0.0, -gap, 0.0, 1.0])
        att.second_chain = tuple(skel.joint_index(f"{other}{j}") for j in ("Arm", "ForeArm", "Hand"))
    t.attachments.append(att)
    if sheath == slot:                                # a second place for it: across the back
        back = place_on_back(skel, bind, item, ispec)
        if back is not None:
            t.attachments.append(back)


def hand_center(skel: Skeleton, body: MeshData, joint: int, bind: np.ndarray) -> np.ndarray | None:
    """Middle of the hand mesh in the bind pose: vertices that mostly follow the hand bone."""
    if body.joints is None:
        return None
    main = body.joints[np.arange(len(body.joints)), np.argmax(body.weights, axis=1)]
    pts = body.pos[main == joint]
    if len(pts) < 10:
        return None
    m2w = bind[0] @ skel.ibm[0]
    pts = pts @ m2w[:3, :3].T + m2w[:3, 3]
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return (lo + hi) / 2                     # box center: fingers and thumb pull a mean around


def soften_skirt(body: MeshData, skel: Skeleton, cfg: dict) -> None:
    """Long skirts and robes: move most of the thigh/shin weight onto the hips, so the cloth
    hangs and sways instead of splitting with each stride. Feet keep their own weights."""
    legs = [skel.joint_index(n) for n in ("LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg", "LeftFoot",
                                          "RightFoot", "LeftToeBase", "RightToeBase") if n in skel.names]
    hips = skel.joint_index(cfg.get("to", "Hips"))
    amount = float(cfg.get("amount", 0.75))
    m2w = skel.bind_world()[0] @ skel.ibm[0]
    y = body.pos @ m2w[:3, 1] + m2w[1, 3]
    above = y > float(cfg.get("min_height_m", 0.2)) * (y.max() - y.min()) / 1.7 + y.min()
    # only cloth: vertices well away from the leg bones (the legs inside the skirt stay as they are)
    bw = skel.bind_world()
    pw = body.pos @ m2w[:3, :3].T + m2w[:3, 3]
    near_leg = np.full(len(pw), np.inf)
    for side in ("Left", "Right"):
        pts = [bw[skel.joint_index(f"{side}{n}")][:3, 3] for n in ("UpLeg", "Leg", "Foot")]
        for p0, p1 in zip(pts[:-1], pts[1:]):
            d = p1 - p0
            t = np.clip(((pw - p0) @ d) / max(float(d @ d), 1e-9), 0.0, 1.0)
            near_leg = np.minimum(near_leg, np.linalg.norm(pw - (p0 + t[:, None] * d), axis=1))
    cloth = near_leg > float(cfg.get("cloth_from_m", 0.11)) * (y.max() - y.min()) / 1.7
    j, w = body.joints.copy(), body.weights.copy()
    moved = np.zeros(len(w), np.float32)
    for k in range(4):
        on_leg = np.isin(j[:, k], legs) & above & cloth
        take = w[:, k] * amount * on_leg
        w[:, k] -= take
        moved += take
    # put the moved weight on the hips: reuse a hips slot if there is one, else the smallest slot
    has_hips = j == hips
    slot = np.where(has_hips.any(axis=1), has_hips.argmax(axis=1), w.argmin(axis=1))
    rows = np.arange(len(w))
    give = moved > 0
    j[rows[give], slot[give]] = hips
    w[rows[give], slot[give]] += moved[give]
    body.joints, body.weights = j, w / np.maximum(w.sum(axis=1, keepdims=True), 1e-8)

    # webbing: Meshy sometimes joins the legs with mesh bound to both of them at once (under a long
    # skirt, near the ankles); it tears apart whenever the legs part, so drop those triangles
    def side_weight(side):
        ids = [skel.joint_index(f"{side}{n}") for n in ("UpLeg", "Leg", "Foot", "ToeBase") if f"{side}{n}" in skel.names]
        return (body.weights * np.isin(body.joints, ids)).sum(axis=1)
    both = (side_weight("Left") >= 0.2) & (side_weight("Right") >= 0.2)
    low = y < y.min() + float(cfg.get("web_below", 0.5)) * (y.max() - y.min())
    tri = body.idx.reshape(-1, 3)
    web = (both & low)[tri].any(axis=1)
    body.idx = np.ascontiguousarray(tri[~web].ravel())


def place_on_back(skel: Skeleton, bind: np.ndarray, item: Item, spec: dict) -> Attachment | None:
    """A sheathed blade across the back: grip up behind the right shoulder, point down toward the
    left hip, edge facing out. Rides on the upper spine."""
    name = next((n for n in ("Spine", "Spine01", "Spine02") if n in skel.names), None)
    if name is None:
        return None
    joint = skel.joint_index(name)
    sp = bind[joint][:3, 3]
    lo = bind[skel.joint_index("Hips")][:3, 3] if "Hips" in skel.names else sp - [0, 0.3, 0]
    back_z = sp[2] - 0.17                                   # a hand's width behind the spine
    grip = np.array([sp[0] - 0.16, sp[1] + 0.14, back_z])   # behind the right shoulder (+x is his left)
    tip_dir = np.array([0.42, -(sp[1] - lo[1] + 0.35), 0.0])
    world = look_basis(grip, tip_dir, [0.0, 0.0, -1.0])
    return Attachment(item, joint, np.linalg.inv(bind[joint]) @ world, sheathed=True)


def place_item(skel: Skeleton, bind: np.ndarray, slot: str, item: Item, body: MeshData | None = None,
               spec: dict | None = None) -> Attachment:
    def pos(name):
        return bind[skel.joint_index(name)][:3, 3]
    spec = spec or {}
    if slot in ("right_hand", "left_hand") and spec.get("hold") == "shield":
        # strapped to the outside of the forearm: face out, top toward the elbow, point toward the hand
        side = "Right" if slot == "right_hand" else "Left"
        joint = skel.joint_index(f"{side}ForeArm")
        elbow, hand = pos(f"{side}ForeArm"), pos(f"{side}Hand")
        up = (elbow - hand) / np.linalg.norm(elbow - hand)
        out = np.array([1.0 if side == "Left" else -1.0, 0.0, 0.25])     # +x is the character's left
        out = out - up * np.dot(out, up)
        out /= np.linalg.norm(out)
        centre = (elbow + hand) / 2 + out * float(spec.get("off_arm_m", 0.07))
        world = look_basis(centre, up, out)
        return Attachment(item, joint, np.linalg.inv(bind[joint]) @ world, in_hand=True, shield=True)
    if slot in ("right_hand", "left_hand"):
        side = "Right" if slot == "right_hand" else "Left"
        joint = skel.joint_index(f"{side}Hand")
        hand, fore = pos(f"{side}Hand"), pos(f"{side}ForeArm")
        arm = (hand - fore) / np.linalg.norm(hand - fore)
        grip = hand_center(skel, body, joint, bind) if body is not None else None
        if grip is None:
            grip = hand + arm * 0.075                   # palm center, a bit past the wrist
        if spec.get("hold") == "along_arm":
            # heavy two-handers: the haft runs along the forearm (head past the fingers), tipped a
            # little forward so the handle clears the arm; overhead swings then bring the head down
            fwd = np.array([0.0, 0.0, 1.0]) - arm * arm[2]
            fwd /= np.linalg.norm(fwd)
            t = np.radians(spec.get("tilt_deg", 18.0))
            blade = arm * np.cos(t) + fwd * np.sin(t)
            world = look_basis(grip, blade, fwd)
        else:
            # blade forward (and a little up), square to the forearm like a fist grip
            blade = np.array([0.0, 0.35, 1.0])
            blade = blade - arm * np.dot(blade, arm)
            world = look_basis(grip, blade, [0.0, 1.0, 0.0])
    else:                                               # hip_left / hip_right: hang beside the thigh
        side = "Left" if slot == "hip_left" else "Right"
        leg = pos(f"{side}UpLeg")
        out = np.sign(leg[0] - pos("Hips")[0]) or 1.0
        world = np.eye(4)
        world[:3, 0], world[:3, 1], world[:3, 2] = [0, 0, -1], [0, 1, 0], [1, 0, 0]
        world[:3, 3] = leg + [out * 0.17, -0.12, 0.02]
        joint = skel.joint_index("Hips")
    return Attachment(item, joint, np.linalg.inv(bind[joint]) @ world, in_hand=slot in ("right_hand", "left_hand"))


# ---------------------------------------------------------------------------- #
def rot_y(h: float) -> np.ndarray:
    c, s = math.cos(h), math.sin(h)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], float)


@dataclass
class Character:
    t: CharType
    actor: Actor
    brain: Enemy | None = None
    phase: float = 0.0            # static meshes: gait phase for the bob
    grip2: float = 0.0            # two-handed weapons: how much the second hand is on the haft (0..1)
    size: float = 1.0             # per-character height/build variation
    tint: tuple[float, float, float] = (1.0, 1.0, 1.0)   # per-character colour variation
    wear: dict[str, int] = field(default_factory=dict)   # outfit piece -> index into t.outfits
    voice: str | None = None                             # which designed voice this NPC speaks with
    talk_env: np.ndarray | None = None                   # loudness of the line being said (jaw)
    talk_t: float = 0.0
    jaw_open: float = 0.0                                # 0 shut .. 1 open
    sheathed: bool | None = None                         # Rowan: sword on his back (None for others)
    fighter: object = None                               # stats.Fighter: enemies and Rowan (HP, poise...)
    night_only: bool = False                             # out only between dusk and dawn (WLD-11)


class CharacterSystem:
    def __init__(self, ctx: moderngl.Context, shaders: ShaderLibrary, world: Heightfield,
                 on_progress=None) -> None:
        self.ctx = ctx
        self.shaders = shaders
        self.world = world
        data = load_character_data()
        self.types: dict[str, CharType] = {}
        char_items = list(data["characters"].items())
        n_types = len(char_items)
        for i, (key, spec) in enumerate(char_items):
            try:
                self.types[key] = load_type(ctx, key, spec, data["items"], data.get("armor", {}))
                self.types[key].spell = spec.get("spell")
            except (FileNotFoundError, KeyError, ValueError) as exc:
                print(f"characters: can't load {key}: {exc}")
            if on_progress is not None:
                on_progress(i + 1, n_types, key)
        self.helmet = True
        # Rowan's gear on his model: inventory item id -> the characters.json item that shows it
        self.item_specs = data["items"]
        self.armor_specs = data.get("armor", {})
        self.shown_as = {s["inventory"]: k for k, s in self.item_specs.items() if "inventory" in s}
        from lycantrope.render.spells import Spells
        self.spells = Spells(ctx, shaders, world)
        from lycantrope.render.rites import RiteEffect
        self.rite = RiteEffect(ctx, shaders, world, self.spells.vbo, self.spells.count)
        self._cast_seen = (False, 0.0)            # Rowan: (casting last tick, cast clip time)
        self._rite_pending = False                # a cast is under way; its Rite lands at the flash
        self.rite_cooldown = 0.0                  # seconds until Rowan can cast again (CMB-34)
        self.chars: list[Character] = []
        self.rowan: Rowan | None = None
        self.colliders: Colliders | None = None     # solid props, set by set_colliders()
        self.spawn(load_spawns())
        self._version = -1
        self.drawn = 0
        self._joint_buf = np.zeros((MAX_JOINTS, 4, 4), np.float32)   # reused per character per frame
        self._cull_rad: np.ndarray | None = None   # cached culling radii; rebuilt only on roster change
        self._cull_rad_n = 0
        self.attack_tokens = AttackTokens(limit=2)  # CMB-27: max 2 enemies attacking at once
        # health, damage and experience (STA-24..28, CMB-37..45)
        from lycantrope.world.combat import Combat
        from lycantrope.world.stats import Progress, config, enemy_fighter
        self.combat_cfg = config()
        self.combat = Combat(self.combat_cfg)
        self.progress = Progress(self.combat_cfg)
        self.events: list[tuple] = []            # for the HUD: ("hurt", amount, from_xz), ("xp", n, why) ...
        self.down_t = 0.0                        # seconds since Rowan fell (death screen, then the reload)
        self.reloads = 0
        self._discover_t = 0.0
        for c in self.chars:
            if c.brain is not None:
                c.fighter = enemy_fighter(c.actor.kind, c.t.name or c.actor.kind, self.combat_cfg)
        self.night = False                       # set each tick by the game from the day clock
        self.dormant = [c for c in self.chars if c.night_only]   # night groups wait here by day
        self.chars = [c for c in self.chars if not c.night_only]
        if self.rowan is not None:
            ra = self.rowan.a
            self.spawn_point = (ra.x, ra.z, ra.heading)
            self.setup_rowan()
            self.discover(award=False)          # where he starts is already known
            self.progress.save()                # the "last save" a death rolls back to (until saves exist)

    def set_colliders(self, colliders: Colliders) -> None:
        """Make props solid: characters slide around them, wanderers don't aim inside them, and
        anyone who spawned overlapping one is nudged out."""
        self.colliders = colliders
        for c in self.chars:
            a = c.actor
            a.x, a.z, _ = colliders.push_out(a.x, a.z, a.radius, passes=4)
            a.y = self.world.height_at(a.x, a.z)
            a.save_prev()
            b = c.brain
            if b is not None and colliders.blocked(*b.home, a.radius):
                b.home = (a.x, a.z)                           # home was inside something: use where it stands
            if b is not None and b.goal_ok is None and not b.route:
                b.goal_ok = lambda _x0, _z0, x1, z1, r=a.radius: not colliders.blocked(x1, z1, r + 0.3)

    # ------------------------------------------------------------------ #
    def _actor(self, key: str, x: float, z: float, heading: float) -> Actor:
        t = self.types[key]
        a = Actor(key, x, z, heading, t.info, t.speeds, radius=RADIUS.get(key, 0.5))
        a.y = self.world.height_at(x, z)
        a.anim.rate = 0.0                     # start in the plain stance; the idle plays after a wait
        a.save_prev()
        return a

    def spawn(self, spawns: dict) -> None:
        anchors = {p.name: p for p in self.world.landmarks + self.world.waystones}
        r = spawns["rowan"]
        if "rowan" in self.types:
            an = anchors[r["anchor"]]
            f = math.radians(r.get("facing", 0))
            ra = self._actor("rowan", an.x + r["at"][0], an.z - r["at"][1], math.atan2(math.sin(f), -math.cos(f)))
            self.rowan = Rowan(ra)
            self.chars.append(Character(self.types["rowan"], ra))
        rng = random.Random(7)
        for gi, g in enumerate(spawns["groups"]):
            if g["kind"] not in self.types or g["anchor"] not in anchors:
                continue
            an = anchors[g["anchor"]]
            cx, cz = an.x + g["at"][0], an.z - g["at"][1]
            t = self.types[g["kind"]]
            route = [(an.x + e, an.z - n) for e, n in g.get("route", [])]
            for i in range(g["count"]):
                ang, rad = rng.uniform(0, math.tau), g.get("radius", 0) * math.sqrt(rng.random())
                x, z = cx + rad * math.cos(ang), cz + rad * math.sin(ang)
                start = rng.randrange(len(route)) if route else 0
                if route:                                    # travellers start somewhere along their road
                    x, z = route[start]
                elif t.ai is not None and t.ai.on_paths:     # path walkers start on a path
                    x, z = self.nearest_path(x, z)
                a = self._actor(g["kind"], x, z, rng.uniform(0, math.tau))
                brain = Enemy(a, (x, z), t.ai or AiParams(), seed=gi * 100 + i)
                ch = Character(t, a, brain)
                vary = g.get("vary", {})
                if vary:                                     # no two villagers quite alike
                    lo, hi = vary.get("height", (1.0, 1.0))
                    ch.size = rng.uniform(lo, hi)
                    k = float(vary.get("tint", 0.0))
                    base = rng.uniform(1 - k, 1 + k)
                    ch.tint = tuple(base * rng.uniform(1 - k / 2, 1 + k / 2) for _ in range(3))
                    plo, phi = vary.get("pace", (1.0, 1.0))
                    pace = rng.uniform(plo, phi)
                    a.speeds = {s: v * pace for s, v in a.speeds.items()}
                self.dress(ch, random.Random(gi * 1000 + i + 77), g.get("lines"))     # own seed: spawn spots stay put
                if not vary:
                    self.dress(ch, random.Random(gi * 1000 + i + 77), g.get("lines"))     # own seed: spawn spots stay put
                ch.night_only = bool(g.get("night", False))
                if route:
                    brain.set_route(route, start, rng.choice((-1, 1)))
                elif brain.ai.on_paths:
                    brain.goal_ok = self.path_walk_ok
                self.chars.append(ch)

    @staticmethod
    def dress(ch: "Character", rng: random.Random, lines: str | None = None) -> None:
        """Give an NPC its own mix of outfit pieces (none = its own clothes) and one of its voices,
        speaking its line set: ch.voice becomes "<lines>.<voice>", the folder its lines are in."""
        t = ch.t
        for piece in PIECE_PARTS:
            have = [i for i, o in enumerate(t.outfits) if piece in o.pieces]
            if have and rng.random() < t.outfit_chance.get(piece, 0.5):
                ch.wear[piece] = rng.choice(have)
        if t.voices:
            ch.voice = rng.choice(t.voices)
            role = lines or t.lines
            if role:
                ch.voice = f"{role}.{ch.voice}"

    def nearest_path(self, x: float, z: float, max_m: float = 40.0) -> tuple[float, float]:
        """The closest point on a path (middle of it), searching outward up to max_m."""
        w = self.world
        for r in np.arange(0.0, max_m, 1.5):
            for k in range(max(1, int(r * 2))):
                t = k / max(1, int(r * 2)) * math.tau
                px, pz = x + r * math.cos(t), z + r * math.sin(t)
                c, rr = w._px(px, pz)
                ci, ri = int(round(c)), int(round(rr))
                if 0 <= ci < w.size and 0 <= ri < w.size and w.road[ri, ci] >= 170:
                    return px, pz
        return x, z

    def path_walk_ok(self, x0: float, z0: float, x1: float, z1: float) -> bool:
        """Is (x1, z1) on a path, and is the straight walk there along paths (or from off-path)?"""
        w = self.world

        def road(x, z):
            c, r = w._px(x, z)
            ci, ri = int(round(c)), int(round(r))
            return int(w.road[ri, ci]) if 0 <= ci < w.size and 0 <= ri < w.size else 0
        if road(x1, z1) < 120:
            return False
        start_on = road(x0, z0) >= 60
        steps = max(8, int(math.hypot(x1 - x0, z1 - z0) / 1.5))    # a check every 1.5 m
        for k in range(1, steps):
            t = k / steps
            if road(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t) < (110 if start_on else 0):
                return False
        return True

    def name_of(self, speaker: int) -> str:
        """Display name of the character with this actor id (for subtitles)."""
        for c in self.chars:
            if id(c.actor) == speaker:
                return c.t.name or c.actor.kind
        return ""

    def talk(self, speaker: int, envelope: np.ndarray) -> None:
        """A voice line started: that NPC stops to face Rowan and moves its jaw with the line."""
        for c in self.chars:
            if id(c.actor) == speaker:
                c.talk_env, c.talk_t = envelope, 0.0
                if c.brain is not None:
                    c.brain.talk_s = len(envelope) / 30.0 + 0.5
                return

    def chased(self, range_m: float) -> bool:
        """Is any enemy within range_m actively after Rowan (for the combat music)?"""
        if self.rowan is None or self.rowan.a.state == "dead":
            return False
        r = self.rowan.a
        return any(c.brain is not None and c.actor.state in ("chase", "engage", "attack", "cast")
                   and (c.actor.x - r.x) ** 2 + (c.actor.z - r.z) ** 2 < range_m * range_m
                   for c in self.chars)

    # ------------------------------------------------------------------ stats
    @property
    def rowan_char(self) -> "Character | None":
        if self.rowan is None:
            return None
        return next((c for c in self.chars if c.actor is self.rowan.a), None)

    def setup_rowan(self) -> None:
        """Rowan's Fighter from his progress: HP, stamina, attack; stamina costs and attack speed."""
        rc = self.rowan_char
        if rc is None:
            return
        cfg = self.combat_cfg
        rc.fighter = self.progress.fighter("Rowan")
        self.rowan.fighter = rc.fighter
        self.rowan.roll_window = float(cfg["fall"]["roll_window_s"])
        self.apply_stats()
        self.dress_rowan()

    def apply_stats(self) -> None:
        cfg = self.combat_cfg
        d = self.progress.stats()
        self.rowan.attack_rate = d["recovery"] / 100.0
        self.combat.crit_chance = d["crit_chance"]
        self.combat.rowan_weapon = self.progress.weapon()
        k = self.progress.stamina_multiplier()           # WPR-03: attacks cost more below the requirements
        self.rowan.costs = {m: float(v["stamina"]) * k for m, v in cfg["moves"].items() if "stamina" in v}
        self.rowan.costs["jump"] = float(cfg["stamina"]["jump"])
        self.rowan.costs["sprint_per_s"] = float(cfg["stamina"]["sprint_per_s"])

    def equipment_changed(self) -> None:
        """Rowan put something on or took it off: new attack, defence, poise and costs, same share of HP."""
        rc = self.rowan_char
        if rc is None or rc.fighter is None:
            return
        self.progress.refresh(rc.fighter)
        self.apply_stats()
        self.dress_rowan()

    def dress_rowan(self) -> None:
        """Put Rowan's equipped gear on his model: the armor pieces that have a model, the main-hand
        weapon (with its copy on his back), and the off-hand shield or catalyst. Slots whose item
        has no model show his own clothes / nothing."""
        rc = self.rowan_char
        t = rc.t if rc is not None else None
        if t is None or t.dress is None:
            return
        body, bind, sheath = t.dress
        eq = self.progress.inv.equipped
        t.armor_wear = {}
        for slot in SLOTS:
            iid = eq.get(slot)
            for sid in t.armor_sets:
                if iid and self.armor_specs[sid].get("pieces", {}).get(slot) == iid:
                    t.armor_wear[slot] = sid
        t.attachments = []
        main = self.shown_as.get(eq.get("mainhand"))
        if main:
            attach_item(self.ctx, t, bind, body, "right_hand", main, self.item_specs, sheath)
        off = self.shown_as.get(eq.get("offhand"))
        if off:
            spec = self.item_specs[off]
            slot = spec.get("worn", "left_hand" if spec.get("hold") == "shield" else "hip_left")
            attach_item(self.ctx, t, bind, body, slot, off, self.item_specs)
        self._version = -1                        # new meshes need vertex arrays

    def update_spawn(self) -> None:
        """Lock in Rowan's current position as the death-respawn point."""
        if self.rowan is not None:
            ra = self.rowan.a
            self.spawn_point = (ra.x, ra.z, ra.heading)

    def apply_save(self, data: dict) -> None:
        """Restore progress and position from a loaded save dict (TEC-16)."""
        prog = data.get("progress")
        if prog:
            self.progress.restore(prog)
        sp = data.get("spawn")
        if sp:
            self.spawn_point = (float(sp["x"]), float(sp["z"]), float(sp.get("heading", 0.0)))
        self.setup_rowan()
        if self.rowan is not None:
            ra = self.rowan.a
            ra.x, ra.z, ra.heading = self.spawn_point
            ra.y = self.world.height_at(ra.x, ra.z)
            ra.save_prev()
        self.progress.save()   # keep in-memory _saved in sync with what we just loaded

    def level_up(self, plan: dict[str, int]) -> bool:
        """Spend XP on attribute points (the level-up screen, STA-02/24)."""
        rc = self.rowan_char
        if rc is None or not self.progress.apply(plan):
            return False
        self.progress.refresh(rc.fighter)
        self.apply_stats()
        self.events.append(("level", self.progress.level))
        return True

    def drink(self) -> bool:
        """The Lifewater flask (CMB-22): heals over a moment."""
        rc = self.rowan_char
        if rc is None or rc.fighter is None or not rc.fighter.alive or self.progress.flask <= 0:
            return False
        if rc.actor.state not in ("move", "block", "swim"):
            return False
        self.progress.flask -= 1
        lw = self.combat_cfg["lifewater"]
        rc.fighter.heal(self.progress.flask_heal(rc.fighter.max_hp), lw["seconds"])
        self.events.append(("flask", self.progress.flask))
        return True

    def eat(self, food: str = "apple") -> bool:
        """Food heals slowly (CMB-44)."""
        rc = self.rowan_char
        spec = self.combat_cfg["food"].get(food)
        if rc is None or rc.fighter is None or not rc.fighter.alive or spec is None:
            return False
        if not self.progress.inv.remove(food):
            return False
        rc.fighter.heal(spec["heal"], spec["seconds"])
        self.events.append(("eat", food))
        return True

    def discover(self, award: bool = True) -> None:
        """Finding a landmark or waking a Waystone gives XP once (STA-25)."""
        if self.rowan is None:
            return
        ra = self.rowan.a
        extra = self.combat_cfg["xp"]["discover_extra_m"]
        for kind, places in (("landmark", self.world.landmarks), ("waystone", self.world.waystones)):
            for p in places:
                if p.name in self.progress.discovered:
                    continue
                if math.hypot(ra.x - p.x, ra.z - p.z) <= p.radius + extra:
                    self.progress.discovered.add(p.name)
                    if award:
                        n = self.progress.discover_xp(kind)
                        self.progress.gain(n)
                        self.events.append(("xp", n, f"Discovered {p.name}"))

    def reload(self) -> None:
        """Death loads the last save (STA-28): Rowan's level and XP go back to it, he wakes where it was
        made, and the enemies are back where they were."""
        self.progress.restore()
        self.setup_rowan()
        self.teleport(*self.spawn_point)
        self.respawn_enemies()
        self.down_t = 0.0
        self.reloads += 1
        self.events.append(("reload",))

    def teleport(self, x: float, z: float, heading: float) -> None:
        """Put Rowan somewhere new, standing still (death reloads, fast travel)."""
        ra = self.rowan.a
        ra.x, ra.z, ra.heading = x, z, heading
        ra.y = self.world.height_at(ra.x, ra.z)
        ra.state, ra.speed, ra.vy, ra.airborne, ra.fall_top, ra.travel = "move", 0.0, 0.0, False, None, None
        ra.play("idle", restart=True)
        ra.save_prev()
        self.rowan.sheathed, self.rowan.plunging = True, False

    def rest(self) -> None:
        """WLD-09: resting at a Waystone heals Rowan fully, refills the flask and brings the enemies back."""
        f = self.rowan_char.fighter
        f.hp = f.trail = f.max_hp
        f.stamina, f.poise, f.heals, f.exhausted = f.max_stamina, f.poise_max, [], False
        self.progress.flask = int(self.combat_cfg["lifewater"]["charges"])
        self.rite_cooldown = 0.0
        self.respawn_enemies()

    NIGHT_POP_M = 50.0              # night groups come and go only this far from Rowan

    def night_shift(self) -> None:
        """WLD-11: night groups come out after dusk and leave at dawn, back at their spawn points. Never in
        Rowan's face (NIGHT_POP_M), and never mid-fight; the dead stay down until enemies respawn."""
        if self.rowan is None:
            return
        ra = self.rowan.a

        def far(x, z):
            return math.hypot(x - ra.x, z - ra.z) > self.NIGHT_POP_M
        changed = False
        if self.night:
            for c in list(self.dormant):
                hx, hz = c.brain.home
                if c.fighter is not None and c.fighter.alive and far(hx, hz):
                    self.dormant.remove(c)
                    a = c.actor
                    a.x, a.z = hx, hz
                    a.y = self.world.height_at(hx, hz)
                    a.state, a.speed, a.vy, a.airborne, a.fall_top = "wander", 0.0, 0.0, False, None
                    a.play("idle", restart=True)
                    a.save_prev()
                    self.chars.append(c)
                    changed = True
        else:
            for c in [c for c in self.chars if c.night_only]:
                a = c.actor
                if a.state not in ("chase", "engage", "attack", "cast", "hit") and far(a.x, a.z):
                    self.chars.remove(c)
                    self.dormant.append(c)
                    changed = True
        if changed:
            self._cull_rad_n = -1                # roster changed: rebuild the culling radii

    def respawn_enemies(self) -> None:
        """Every enemy back at full health where it started (the night groups too, out or not)."""
        for c in self.chars + self.dormant:
            b = c.brain
            if b is None or c.fighter is None:
                continue
            a = c.actor
            c.fighter.reset()
            a.x, a.z = b.home
            a.y = self.world.height_at(a.x, a.z)
            a.state, a.speed, a.vy, a.airborne, a.fall_top = "wander", 0.0, 0.0, False, None
            a.timer = b.rng.uniform(0.5, 3.0)
            b.goal = None
            a.play("idle", restart=True)
            a.save_prev()
        self.spells.items.clear()
        self.combat.swings.clear()

    def _hits(self, rc) -> None:
        """XP for kills and HUD events for this tick's hits."""
        for h in self.combat.hits:
            t = h.target
            if t is rc:
                self.events.append(("hurt", h.amount, t.fighter.hit_from, h.kind))
            elif h.killed and t.fighter is not None:
                n = kill_xp(t.fighter.xp, t.fighter.level, self.progress.level, self.combat_cfg)
                self.progress.gain(n)
                self.events.append(("xp", n, t.fighter.name))
                a = t.actor
                self.events.append(("killed", a.kind, (a.x, a.y, a.z), t.fighter.name))   # loot (WLD-17)
            if not h.staggered and not h.killed and h.kind != "fall":
                a = t.actor                          # no hit animation: still make the impact heard
                self.cue_sound(a.kind, "hit", (a.x, a.y + 1.0, a.z))

    def cue_sound(self, kind: str, event: str, pos) -> None:
        """Set by the game to the sound system's cue (stays silent without sound)."""

    def _landed(self, c: "Character", drop: float) -> None:
        """Fall damage, stumbles, landing rolls, water and plunges (CMB-38..43)."""
        from lycantrope.world.stats import landing
        f = c.fighter
        if f is None or not f.alive:
            return
        a = c.actor
        fc = self.combat_cfg["fall"]
        depth = self.world.water_depth(a.x, a.z)
        rc = self.rowan_char
        if c is rc:
            plunged = False
            if self.rowan.plunging and drop >= fc["plunge_min_m"]:
                plunged = self.combat.plunge(rc, self.chars)
                if plunged and a.state != "dead":
                    a.state = "attack"
                    a.play("heavy", restart=True)
                    info = a.clips.get("heavy")
                    a.anim.time = info.duration * 0.65 if info else 0.0   # the end of the slam
            self.rowan.plunging = False
            rolled = self.rowan.roll_t > 0.0
            dmg, stumble = landing(drop, f.max_hp, rolled, depth, plunged, self.combat_cfg)
            if rolled and drop >= fc["stumble_m"]:
                self.events.append(("roll",))
                if a.has("roll"):
                    a.state = "roll"
                    a.play("roll", restart=True)
        else:
            dmg, stumble = landing(drop, f.max_hp, False, depth, False, self.combat_cfg)
            dmg *= f.weight                          # heavy beasts take more (CMB-43)
        if dmg > 0 or stumble:
            self.combat.fall(c, dmg, stumble, rc)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.chars:
            out[c.actor.kind] = out.get(c.actor.kind, 0) + 1
        return out

    # ------------------------------------------------------------------ #
    def update(self, inp, cam_yaw: float, dt: float) -> None:
        if self.rowan is None:
            return
        self.night_shift()
        ra = self.rowan.a
        self.combat.hits = []
        rcf = self.rowan_char.fighter if self.rowan_char is not None else None
        if inp.die:                                    # debug K: fall where he stands (a real death)
            inp = type(inp)(**{**inp.__dict__, "die": False})
            if rcf is not None and rcf.alive:
                rcf.hurt(rcf.hp + 1.0)
                from lycantrope.world.combat import Hit
                self.combat.react(self.rowan_char, Hit(None, self.rowan_char, 0.0, killed=True, kind="fall"),
                                  self.rowan_char)
        for c in self.chars:
            c.actor.save_prev()
            want = 1.0 if c.actor.state == "attack" else 0.0      # both hands for the swing only
            c.grip2 += (want - c.grip2) * min(1.0, dt * 7.0)
        rc = next((c for c in self.chars if c.actor is ra), None)
        if rc is not None and "swim" in ra.clips and ra.state != "dead":
            k = rc.t.height * rc.size / 1.75
            depth = self.world.water_depth(ra.x, ra.z)
            self.rowan.swimming = depth > (SWIM_OUT if self.rowan.swimming else SWIM_IN) * k
        else:
            self.rowan.swimming = False
        self.rowan.update(inp, cam_yaw, dt)
        if rc is not None:
            rc.sheathed = self.rowan.sheathed
        self._watch_cast(ra, rc)
        alive = ra.state != "dead"
        near = [c.actor for c in self.chars                    # only these can bump into each other
                if abs(c.actor.x - ra.x) < 150 and abs(c.actor.z - ra.z) < 150]
        for c in self.chars:
            if c.brain is not None:
                if (math.hypot(c.actor.x - ra.x, c.actor.z - ra.z) > 60.0
                        and c.actor.state == "wander" and c.brain.goal is None):
                    c.actor.timer -= dt                     # sleeping: just count down
                    continue
                c.brain.update(ra, alive, dt, tokens=self.attack_tokens)
                if c.brain.should_release():                   # a caster lets its spell go
                    a, sp = c.actor, c.t.spell or {}
                    fwd = (math.sin(a.heading), math.cos(a.heading))
                    start = (a.x + fwd[0] * 0.6, a.y + c.t.height * 0.72, a.z + fwd[1] * 0.6)
                    target = (ra.x, ra.y + 1.2, ra.z)
                    self.spells.cast(start, target, float(sp.get("speed_m_s", 16)), float(sp.get("radius_m", 0.28)),
                                     sp.get("color", (1.0, 0.45, 0.12)),
                                     damage=dict(c.fighter.spell) if c.fighter is not None and c.fighter.spell else None)
        separate([a for a in near if a.state != "dead"])
        # swings that land, spells that reach Rowan, and what they cost
        rc = self.rowan_char
        self.combat.update(self.chars, rc)
        self.combat.spell_hits(self.spells.items, rc)
        if rc is not None and rc.fighter is not None:
            rc.fighter.update(dt, regen=ra.state not in ("attack", "block") and not self.rowan.sprinting,
                              cfg=self.combat_cfg)
        self.spells.update(dt)
        self.rite.update(dt)
        self._land_rite(rc, dt)
        self._discover_t -= dt
        if self._discover_t <= 0.0 and ra.state != "dead":
            self._discover_t = 0.5
            self.discover()
        lim = self.world.half - 5
        for c in self.chars:
            a = c.actor
            # enemy fighter regen (Rowan's already handled above, skip him here)
            f = c.fighter
            if f is not None and c is not rc and (f.since_hurt < 10.0 or f.heals):
                f.update(dt, cfg=self.combat_cfg)
            # jaw follows NPC voice line loudness
            if c.talk_env is not None:
                ji = int(c.talk_t * 30.0)
                if ji >= len(c.talk_env):
                    c.talk_env, jaw_target = None, 0.0
                else:
                    jaw_target = float(c.talk_env[ji])
                c.talk_t += dt
            else:
                jaw_target = 0.0
            c.jaw_open += (jaw_target - c.jaw_open) * min(1.0, dt * 25.0)
            # physics: swim, fly, ground snap, collision
            if a is ra and self.rowan.swimming:                # float with the water at his back
                if self.colliders is not None:
                    a.x, a.z, _ = self.colliders.push_out(a.x, a.z, a.radius)
                a.x = min(max(a.x, -lim), lim)
                a.z = min(max(a.z, -lim), lim)
                level = c.t.float_m.get(a.anim.clip, c.t.float_m.get("swim", 1.1)) * c.t.scale * c.size
                wl_target = self.world.water_at(a.x, a.z) - level
                a.y += (wl_target - a.y) * min(1.0, dt * 5.0)
                a.y = max(a.y, self.world.height_at(a.x, a.z))
                a.advance(dt)
                continue
            if a.airborne or ((a is ra or c.fighter is not None) and a.y - self.world.height_at(a.x, a.z) > 0.35):
                self._fly(c, dt, lim)                          # jumping, or ran off a ledge
                continue
            if a.x == a.px and a.z == a.pz:                   # didn't move: ground is the same
                a.advance(dt)
                continue
            a.x = min(max(a.x, -lim), lim)
            a.z = min(max(a.z, -lim), lim)
            if self.colliders is not None:                     # houses, trunks, fences, rocks
                a.x, a.z, hit = self.colliders.push_out(a.x, a.z, a.radius)
                if hit and c.brain is not None:
                    c.brain.bumped += dt
            # only Rowan swims: everyone else wades, and deeper water stops them at the edge
            wd = self.world.water_depth(a.x, a.z)
            if a is not ra and wd > WADE_DEPTH * (c.t.height / 1.75) and \
                    wd > self.world.water_depth(a.px, a.pz):
                a.x, a.z = a.px, a.pz
                a.speed = 0.0
                if c.brain is not None:
                    c.brain.goal = None
            a.y = self.world.height_at(a.x, a.z)
            a.advance(dt)
            if c.t.skel is None:
                c.phase += a.speed * dt * 2.2
        self._hits(rc)
        if rc is not None and rc.fighter is not None and not rc.fighter.alive:
            self.down_t += dt                              # the death screen, then back to the last save
            if self.down_t >= DEATH_RELOAD_S:
                self.reload()

    def _fly(self, c: "Character", dt: float, lim: float) -> None:
        """In the air (Rowan jumping, anyone off a ledge): gravity, solid props and the map edge still
        apply; landing hurts if the drop was high (CMB-38)."""
        from lycantrope.world.actors import GRAVITY
        a = c.actor
        if not a.airborne or a.fall_top is None:
            a.fall_top = a.y
        a.airborne = True
        a.x = min(max(a.x, -lim), lim)
        a.z = min(max(a.z, -lim), lim)
        if self.colliders is not None:
            a.x, a.z, _ = self.colliders.push_out(a.x, a.z, a.radius)
        a.y += a.vy * dt
        a.vy -= GRAVITY * dt
        a.fall_top = max(a.fall_top, a.y)
        ground = self.world.height_at(a.x, a.z)
        surface = max(ground, self.world.water_at(a.x, a.z) - 1.0)   # deep water catches him (then he swims)
        if a.y <= surface and a.vy <= 0.0:
            a.y, a.vy, a.airborne = max(ground, min(a.y, surface)), 0.0, False
            drop, a.fall_top = a.fall_top - a.y, None
            if a.state == "move":
                a.locomotion()
            self._landed(c, drop)
        a.advance(dt)

    def _watch_cast(self, ra: Actor, rc: "Character | None") -> None:
        """Start Rowan's Rite effect when his cast animation starts; cancel it if he's interrupted."""
        casting = ra.state == "cast" and ra.anim.clip == "cast"
        was, t_prev = self._cast_seen
        if casting and (not was or ra.anim.time < t_prev) and rc is not None:
            info = ra.clips.get("cast")
            length = info.duration if info else 1.5
            self.rite.begin(rc.t.cast_release * length / max(ra.anim.rate, 1e-3))
            self._rite_pending = True
        elif not casting and was:
            self.rite.cancel()
        self._cast_seen = (casting, ra.anim.time)

    def _land_rite(self, rc, dt: float) -> None:
        """The Ward forms at the cast's flash (an interrupted cast gives nothing and costs no cooldown)."""
        self.rite_cooldown = max(0.0, self.rite_cooldown - dt)
        f = rc.fighter if rc is not None else None
        if self._rite_pending and (not self.rite.active or self.rite.cancelled_at >= 0):
            self._rite_pending = False
        elif self._rite_pending and self.rite.t >= self.rite.release_s and f is not None:
            self._rite_pending = False
            absorb, seconds = self.progress.ward()
            f.ward_hp = f.ward_max = absorb
            f.ward_t = seconds
            self.rite_cooldown = self.progress.rite_cooldown()
            self.events.append(("ward", absorb, seconds))
        self.rite.ward_level = f.ward_hp / f.ward_max if f is not None and f.ward_t > 0 and f.ward_max > 0 else 0.0

    def _body_variant(self, t: CharType, c: "Character", prog) -> GpuMesh:
        """The body without the triangles this NPC's top and bottom cover (built once per mix)."""
        key = tuple(sorted((p, k) for p, k in c.wear.items() if p in t.outfits[k].covers))
        g = t.body_variants.get(key)
        if g is None:
            hide = np.zeros(len(t.body_tris), bool)
            for p, k in key:
                hide |= t.outfits[k].covers[p]
            tri = np.ascontiguousarray(t.body_tris[~hide])
            g = GpuMesh(t.body.vbo, self.ctx.buffer(tri.tobytes()), [(0, tri.size)], t.body.texture)
            t.body_variants[key] = g
        if g.vao is None or getattr(g, "_ver", None) != self.shaders.version:
            g.vao = self.ctx.vertex_array(prog, [(g.vbo, "3f 3f 2f 4f 4f 3f", "in_pos", "in_nrm", "in_uv",
                                                  "in_joints", "in_weights", "in_color")],
                                          index_buffer=g.ibo, index_element_size=4)
            g._ver = self.shaders.version
        return g

    # ------------------------------------------------------------------ #
    def _program(self) -> moderngl.Program:
        prog = self.shaders.get("skinned")
        if self._version != self.shaders.version:
            def vao(g: GpuMesh):
                g.vao = self.ctx.vertex_array(prog, [(g.vbo, "3f 3f 2f 4f 4f 3f", "in_pos", "in_nrm", "in_uv",
                                                      "in_joints", "in_weights", "in_color")],
                                              index_buffer=g.ibo, index_element_size=4)
            for t in self.types.values():
                vao(t.body)
                for g in t.armor_sets.values():
                    vao(g)
                for o in t.outfits:
                    vao(o.gpu)
                for at in t.attachments:
                    vao(at.item.gpu)
            self._version = self.shaders.version
        return prog

    def joint_worlds(self, c: Character) -> np.ndarray:
        t, an = c.t, c.actor.anim
        cur = t.clips.get(an.clip) or t.clips.get("idle")
        w = cur.sample(an.time)
        if an.fade < 1.0 and an.prev in t.clips:
            f = an.fade * an.fade * (3 - 2 * an.fade)
            w = t.clips[an.prev].sample(an.prev_time) * (1 - f) + w * f
        for at in t.attachments:                     # two-handed weapons: pull the other hand onto the haft
            if at.second_chain is not None and c.grip2 > 0.01:
                base = w.astype(float, copy=True)
                ik = base.copy()
                target = (base[at.joint] @ at.offset @ at.second_grip)[:3]
                two_bone_ik(ik, at.second_chain, target)
                k = c.grip2 * c.grip2 * (3 - 2 * c.grip2)
                w = base + (ik - base) * k
        return w

    def _draw(self, prog, g: GpuMesh, slots_on: list[int] | None = None) -> None:
        if g.texture is not None:
            g.texture.use(5)
            set_uniform(prog, "u_tex", 5)
        set_uniform(prog, "u_has_tex", 1 if g.texture is not None else 0)
        ranges = g.ranges if slots_on is None else [g.ranges[i] for i in slots_on]
        for first, count in ranges:
            if count:
                g.vao.render(moderngl.TRIANGLES, vertices=count, first=first)

    def render(self, eye: glm.vec3, viewproj: glm.mat4, env: dict, alpha: float) -> None:
        if not self.chars:
            return
        prog = self._program()
        set_uniform(prog, "u_viewproj", viewproj)
        set_uniform(prog, "u_cam", eye)
        for k, v in env.items():
            set_uniform(prog, k, v)
        planes = frustum_planes(viewproj)
        e = np.array([eye.x, eye.y, eye.z])
        # cull everyone at once (one numpy pass), then only loop over who's on screen
        pos = np.array([(c.actor.x, c.actor.y + c.t.height * 0.5, c.actor.z) for c in self.chars])
        n = len(self.chars)
        if self._cull_rad_n != n:
            self._cull_rad = np.array([max(c.t.height, 1.0) * 1.2 for c in self.chars])
            self._cull_rad_n = n
        rad = self._cull_rad
        vis = np.linalg.norm(pos - e, axis=1) <= DRAW_DISTANCE
        vis &= ((pos @ planes[:, :3].T + planes[:, 3]) >= -rad[:, None] - 1.0).all(axis=1)
        drawn = 0
        for idx in np.nonzero(vis)[0]:
            c = self.chars[idx]
            a, t = c.actor, c.t
            x = a.px + (a.x - a.px) * alpha
            y = a.py + (a.y - a.py) * alpha
            z = a.pz + (a.z - a.pz) * alpha
            dh = (a.heading - a.ph + math.pi) % math.tau - math.pi
            h = a.ph + dh * alpha
            model = np.eye(4)
            model[:3, 3] = (x, y, z)
            model = model @ rot_y(h + t.turn)
            sc = t.scale * c.size
            if sc != 1.0:
                model = model @ np.diag([sc, sc, sc, 1.0])
            if abs(t.lift) > 1e-4:
                up = np.eye(4)
                up[1, 3] = t.lift
                model = model @ up
            drawn += 1
            if t.skel is None:
                self._draw_static(prog, c, model)
                continue
            W = self.joint_worlds(c)
            if self.rowan is not None and a is self.rowan.a:   # where the Rite's light gathers
                self.rite.feet = (x, y, z)
                if t.cast_hand >= 0:
                    self.rite.hand = tuple((model @ W[t.cast_hand].astype(float))[:3, 3])
            palette = np.einsum("jab,jbc->jac", W, t.skel.ibm)
            buf = self._joint_buf
            buf[:] = 0.0
            buf[:len(palette)] = palette
            if t.jaw >= 0:                                     # the jaw hangs off the head
                buf[t.jaw] = palette[t.jaw_of] @ jaw_matrix(t, c.jaw_open)
            prog["u_joints"].write(np.ascontiguousarray(buf.transpose(0, 2, 1)).tobytes())
            set_uniform(prog, "u_model", glm.mat4(*model.T.ravel()))
            set_uniform(prog, "u_skinned", 1)
            set_uniform(prog, "u_tint", glm.vec3(*c.tint))
            if t.outfits:
                self._draw(prog, self._body_variant(t, c, prog))
                for piece, k in c.wear.items():
                    o = t.outfits[k]
                    self._draw(prog, o.gpu, o.pieces.get(piece, []))
            elif t.armor_sets:
                worn = {s: sid for s, sid in t.armor_wear.items() if s != "head" or self.helmet}
                self._draw(prog, t.body, [i for i, s in enumerate(SLOTS) if s not in worn])
                for sid in set(worn.values()):
                    self._draw(prog, t.armor_sets[sid], [SLOTS.index(s) for s, v in worn.items() if v == sid])
            else:
                self._draw(prog, t.body)
            set_uniform(prog, "u_skinned", 0)
            swim = a.anim.clip in ("swim", "tread")
            sheath = self.rowan is not None and a is self.rowan.a and self.rowan.sheathed
            for at in t.attachments:
                if at.sheathed:                          # the sword on his back: only while it's put away
                    show = swim or sheath
                else:                                    # shields stay on the arm when he sheathes
                    show = not at.in_hand or not (swim or (sheath and not at.shield))
                if not show:
                    continue
                m = model @ W[at.joint].astype(float) @ at.offset
                set_uniform(prog, "u_model", glm.mat4(*m.T.ravel()))
                self._draw(prog, at.item.gpu)
        self.drawn = drawn
        self.spells.render(eye, viewproj, env, alpha)
        self.rite.render(eye, viewproj, env)

    def _draw_static(self, prog, c: Character, model: np.ndarray) -> None:
        """Rigless animals: a bob while moving, a lunge when attacking, lying down when dead."""
        set_uniform(prog, "u_tint", glm.vec3(*c.tint))
        a, t = c.actor, c.t
        h = t.height
        bob = abs(math.sin(c.phase)) * 0.035 * h * min(1.0, a.speed / 2.0)
        pitch, fwd = 0.0, 0.0
        if a.anim.clip.startswith("attack"):
            u = min(a.anim.time / 0.9, 1.0)
            fwd = 0.45 * h * math.sin(math.pi * u)
            pitch = -0.35 * math.sin(math.pi * u)
        local = np.eye(4)
        local[1, 3] = bob
        local[2, 3] = fwd
        if pitch:
            cp, sp = math.cos(pitch), math.sin(pitch)
            local = local @ np.array([[1, 0, 0, 0], [0, cp, -sp, 0], [0, sp, cp, 0], [0, 0, 0, 1]])
        m = model @ local
        set_uniform(prog, "u_skinned", 0)
        set_uniform(prog, "u_model", glm.mat4(*m.T.ravel()))
        self._draw(prog, t.body)
