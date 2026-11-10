"""Draw the CareerSense class diagrams and ERDs for section 3.5.3.3.

Wireframes occupy Figures 16-39, so these eight figures start at Figure 40.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_ITALIC = Path(r"C:\Windows\Fonts\ariali.ttf")

INK = "#222222"
HEADER = 34
ROW = 18
ATTR_SIZE = 13
TITLE_SIZE = 15


def font(size: int, kind: str = "regular") -> ImageFont.FreeTypeFont:
    path = {"regular": FONT, "bold": FONT_BOLD, "italic": FONT_ITALIC}[kind]
    return ImageFont.truetype(str(path), size)


def text_width(text: str, size: int, kind: str = "regular") -> float:
    return font(size, kind).getlength(text)


def box_height(rows: int) -> int:
    return HEADER + 8 + rows * ROW + 12


class Box:
    def __init__(self, title: str, lines: list, kind: str = "class", min_w: int = 0):
        self.title = title
        self.lines = lines
        self.kind = kind
        self.x = 0
        self.y = 0
        self.w = self._width(min_w)
        self.h = box_height(len(lines))

    def _width(self, min_w: int) -> int:
        title_w = text_width(self.title, TITLE_SIZE, "bold")
        body = title_w
        prefix_w = 54 if self.kind == "erd" else 0
        for line in self.lines:
            if self.kind == "erd":
                prefix, name = line
                body = max(body, prefix_w + text_width(name, ATTR_SIZE) + text_width(prefix, 11, "bold"))
            else:
                body = max(body, text_width(line, ATTR_SIZE))
        return int(max(min_w, body + 28))

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def anchor(self, side: str, t: float = 0.5) -> tuple[float, float]:
        if side == "n":
            return (self.x + self.w * t, self.y)
        if side == "s":
            return (self.x + self.w * t, self.bottom)
        if side == "w":
            return (self.x, self.y + self.h * t)
        if side == "e":
            return (self.right, self.y + self.h * t)
        raise ValueError(side)


class Diagram:
    def __init__(self, stem: str, title: str, erd: bool = False):
        self.stem = stem
        self.title = title
        self.erd = erd
        self.boxes: list[Box] = []
        self.links: list[dict] = []
        self.notes: list[tuple[float, float, str, int]] = []
        self.legend = erd
        self.w = 0
        self.h = 0

    def add(self, title: str, lines: list, kind: str | None = None, min_w: int = 0) -> Box:
        box = Box(title, lines, kind or ("erd" if self.erd else "class"), min_w)
        self.boxes.append(box)
        return box

    def poly(self, pts, label="", ms="", me="", label_side: int = 1, dashed: bool = False, label_segment=None):
        self.links.append(
            {
                "pts": [(float(x), float(y)) for x, y in pts],
                "label": label,
                "ms": ms,
                "me": me,
                "side": label_side,
                "dashed": dashed,
                "label_segment": label_segment,
            }
        )

    def hlink(self, left: Box, right: Box, label="", ms="", me="", label_side: int = -1):
        p1 = left.anchor("e")
        p2 = right.anchor("w")
        if abs(p1[1] - p2[1]) < 3:
            pts = [p1, p2]
        else:
            mid = (p1[0] + p2[0]) / 2
            pts = [p1, (mid, p1[1]), (mid, p2[1]), p2]
        self.poly(pts, label, ms, me, label_side)

    def vlink(self, upper: Box, lower: Box, label="", ms="", me="", label_side: int = 1):
        p1 = upper.anchor("s")
        p2 = lower.anchor("n")
        if abs(p1[0] - p2[0]) < 3:
            pts = [p1, p2]
        else:
            mid = (p1[1] + p2[1]) / 2
            pts = [p1, (p1[0], mid), (p2[0], mid), p2]
        self.poly(pts, label, ms, me, label_side)

    def note(self, x, y, text, width=640):
        self.notes.append((x, y, text, width))

    def finish(self, pad: int = 36) -> None:
        right = max(box.right for box in self.boxes)
        bottom = max(box.bottom for box in self.boxes)
        for link in self.links:
            for x, y in link["pts"]:
                right = max(right, x + 90)
                bottom = max(bottom, y)
        if self.notes:
            bottom = max(bottom, max(y + 22 for _, y, _, _ in self.notes))
        if self.legend:
            bottom += 56
        self.w = int(right + pad)
        self.h = int(bottom + pad)
        self._check()

    def _check(self) -> None:
        problems = []
        for i, a in enumerate(self.boxes):
            for b in self.boxes[i + 1 :]:
                if a.x < b.right + 10 and b.x < a.right + 10 and a.y < b.bottom + 10 and b.y < a.bottom + 10:
                    problems.append(f"boxes close: {a.title} and {b.title}")
        for link in self.links:
            pts = link["pts"]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                for box in self.boxes:
                    if _segment_hits_box(x1, y1, x2, y2, box):
                        problems.append(f"line through {box.title} ({link['label'] or 'link'})")
        self.problems = problems
        for item in problems:
            print(f"  ! {self.stem}: {item}")


def _segment_hits_box(x1, y1, x2, y2, box: Box) -> bool:
    inset = 4
    if abs(x1 - x2) < 0.5:
        x = x1
        ylo, yhi = sorted((y1, y2))
        return box.x + inset < x < box.right - inset and yhi > box.y + inset and ylo < box.bottom - inset
    if abs(y1 - y2) < 0.5:
        y = y1
        xlo, xhi = sorted((x1, x2))
        return box.y + inset < y < box.bottom - inset and xhi > box.x + inset and xlo < box.right - inset
    return False


def _trim(pts, start: float, end: float):
    pts = [tuple(p) for p in pts]
    if start > 0 and len(pts) >= 2:
        x1, y1 = pts[0]
        x2, y2 = pts[1]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        step = min(start, dist - 1)
        pts[0] = (x1 + dx / dist * step, y1 + dy / dist * step)
    if end > 0 and len(pts) >= 2:
        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        step = min(end, dist - 1)
        pts[-1] = (x2 - dx / dist * step, y2 - dy / dist * step)
    return pts


def _marker_depth(kind: str) -> float:
    return {"1": 16, "0..1": 24, "1..*": 18, "0..*": 26, "": 0}.get(kind, 0)


def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy) or 1
    return dx / dist, dy / dist


class SvgCanvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        ]

    def line(self, pts, width=1.4, dashed=False):
        if len(pts) < 2:
            return
        cmd = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        dash = ' stroke-dasharray="7 4"' if dashed else ""
        self.parts.append(
            f'<polyline points="{cmd}" fill="none" stroke="{INK}" stroke-width="{width}"{dash}/>'
        )

    def rect(self, x, y, w, h):
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#ffffff" stroke="{INK}" stroke-width="1.4"/>'
        )

    def fill_rect(self, x, y, w, h):
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#ffffff" stroke="none"/>'
        )

    def ellipse(self, cx, cy, r):
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#ffffff" stroke="{INK}" stroke-width="1.4"/>'
        )

    def text(self, x, y, value, size=13, kind="regular", anchor="start"):
        weight = "700" if kind == "bold" else "400"
        style = "italic" if kind == "italic" else "normal"
        escaped = (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{INK}" font-family="Arial" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{escaped}</text>'
        )

    def save(self, path: Path):
        path.write_text("\n".join(self.parts + ["</svg>"]), encoding="utf-8")


class PngCanvas:
    def __init__(self, w, h, scale=2):
        self.scale = scale
        self.image = Image.new("RGB", (w * scale, h * scale), "white")
        self.draw = ImageDraw.Draw(self.image)

    def _p(self, x, y):
        s = self.scale
        return (x * s, y * s)

    def line(self, pts, width=1.4, dashed=False):
        if len(pts) < 2:
            return
        width = max(1, int(round(width * self.scale)))
        if not dashed:
            self.draw.line([self._p(x, y) for x, y in pts], fill=INK, width=width)
            return
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            self._dashed(x1, y1, x2, y2, width)

    def _dashed(self, x1, y1, x2, y2, width):
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist
        pos = 0
        draw_on = True
        while pos < dist:
            nxt = min(dist, pos + (8 if draw_on else 5))
            if draw_on:
                self.draw.line([self._p(x1 + ux * pos, y1 + uy * pos), self._p(x1 + ux * nxt, y1 + uy * nxt)], fill=INK, width=width)
            pos = nxt
            draw_on = not draw_on

    def rect(self, x, y, w, h):
        s = self.scale
        self.draw.rectangle(
            [x * s, y * s, (x + w) * s, (y + h) * s],
            outline=INK,
            fill="white",
            width=max(1, int(round(1.4 * s))),
        )

    def fill_rect(self, x, y, w, h):
        s = self.scale
        self.draw.rectangle([x * s, y * s, (x + w) * s, (y + h) * s], fill="white")

    def ellipse(self, cx, cy, r):
        s = self.scale
        self.draw.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], outline=INK, fill="white", width=max(1, int(round(1.4 * s))))

    def text(self, x, y, value, size=13, kind="regular", anchor="start"):
        face = font(size * self.scale, kind)
        pil_anchor = {"start": "ls", "middle": "ms", "end": "rs"}[anchor]
        self.draw.text(self._p(x, y), value, font=face, fill=INK, anchor=pil_anchor)

    def save(self, path: Path):
        self.image.save(path, "PNG")


def _draw_marker(canvas, end, prev, kind: str):
    if not kind:
        return
    ux, uy = _unit(prev, end)
    px, py = -uy, ux

    def at(dist, off=0):
        return (end[0] - ux * dist + px * off, end[1] - uy * dist + py * off)

    def bar(dist):
        canvas.line([at(dist, 7), at(dist, -7)])

    def crow(dist):
        canvas.line([at(dist), at(0, 7)])
        canvas.line([at(dist), at(0, 0)])
        canvas.line([at(dist), at(0, -7)])

    if kind == "1":
        bar(5)
        bar(11)
    elif kind == "0..1":
        cx, cy = at(15)
        canvas.ellipse(cx, cy, 5)
        bar(6)
    elif kind == "1..*":
        bar(14)
        crow(14)
    elif kind == "0..*":
        cx, cy = at(20)
        canvas.ellipse(cx, cy, 5)
        crow(12)


def _label(canvas, x, y, value, size, kind, anchor, halo=True):
    if not value:
        return
    if halo:
        width = text_width(value, size, kind) + 8
        height = size + 4
        if anchor == "middle":
            left = x - width / 2
        elif anchor == "end":
            left = x - width
        else:
            left = x
        canvas.fill_rect(left, y - size, width, height)
    canvas.text(x, y, value, size, kind, anchor)


def render(diagram: Diagram):
    svg = SvgCanvas(diagram.w, diagram.h)
    png = PngCanvas(diagram.w, diagram.h)
    for canvas in (svg, png):
        _paint(canvas, diagram)
    svg_path = ROOT / f"{diagram.stem}.svg"
    png_path = ROOT / f"{diagram.stem}.png"
    svg.save(svg_path)
    png.save(png_path)
    print(f"{diagram.stem}: {diagram.w}x{diagram.h}  {svg_path.name}")


def _paint(canvas, diagram: Diagram):
    canvas.text(diagram.w / 2, 32, diagram.title, 18, "bold", "middle")
    prepared = []
    for link in diagram.links:
        depth_s = _marker_depth(link["ms"]) if diagram.erd else 0
        depth_e = _marker_depth(link["me"]) if diagram.erd else 0
        prepared.append((link, _trim(link["pts"], depth_s, depth_e)))
        canvas.line(prepared[-1][1], dashed=link["dashed"])
    for box in diagram.boxes:
        _paint_box(canvas, box)
    for link, _pts in prepared:
        if diagram.erd:
            _draw_marker(canvas, link["pts"][0], link["pts"][1], link["ms"])
            _draw_marker(canvas, link["pts"][-1], link["pts"][-2], link["me"])
        _place_labels(canvas, link, diagram.erd)
    for x, y, text, _width in diagram.notes:
        canvas.text(x, y, text, 12, "italic", "start")
    if diagram.legend:
        _paint_legend(canvas, 36, diagram.h - 42)


def _place_labels(canvas, link, erd: bool):
    pts = link["pts"]
    side = link["side"]
    spans = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        spans.append((math.hypot(x2 - x1, y2 - y1), x1, y1, x2, y2))
    if link["label"] and spans:
        chosen = link.get("label_segment")
        if chosen is None:
            _dist, x1, y1, x2, y2 = max(spans, key=lambda item: item[0])
        else:
            _dist, x1, y1, x2, y2 = spans[chosen]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if abs(y1 - y2) < 2:
            _label(canvas, mx, my - 14, link["label"], 12, "italic", "middle")
        else:
            anchor = "start" if side > 0 else "end"
            _label(canvas, mx + 8 * side, my + 4, link["label"], 12, "italic", anchor)
    _end_mult(canvas, pts[0], pts[1], link["ms"], erd, outward=False)
    _end_mult(canvas, pts[-1], pts[-2], link["me"], erd, outward=True)


def _end_mult(canvas, end, other, kind, erd, outward):
    if not kind or erd:
        return
    ux, uy = _unit(other, end)
    px, py = -uy, ux
    x = end[0] - ux * 16 + px * 12
    y = end[1] - uy * 16 + py * 12
    _label(canvas, x, y + 4, kind, 12, "bold", "middle")


def _paint_box(canvas, box: Box):
    canvas.rect(box.x, box.y, box.w, box.h)
    canvas.line([(box.x, box.y + HEADER), (box.right, box.y + HEADER)])
    canvas.text(box.x + box.w / 2, box.y + 23, box.title, TITLE_SIZE, "bold", "middle")
    y = box.y + HEADER + 20
    if box.kind == "erd":
        for prefix, name in box.lines:
            if prefix:
                canvas.text(box.x + 10, y, prefix, 11, "bold", "start")
            canvas.text(box.x + 58, y, name, ATTR_SIZE, "regular", "start")
            y += ROW
    else:
        for line in box.lines:
            canvas.text(box.x + 12, y, line, ATTR_SIZE, "regular", "start")
            y += ROW


def _paint_legend(canvas, x, y):
    samples = [("1", "Exactly one"), ("0..1", "Zero or one"), ("1..*", "One or many"), ("0..*", "Zero or many")]
    cursor = x
    for kind, caption in samples:
        start = (cursor, y)
        stop = (cursor + 42, y)
        canvas.line([start, (stop[0] - _marker_depth(kind), y)])
        _draw_marker(canvas, stop, start, kind)
        canvas.text(cursor + 50, y + 4, caption, 12, "regular", "start")
        cursor += 50 + text_width(caption, 12) + 28


def center_under(upper: Box, lower: Box):
    lower.x = upper.x + (upper.w - lower.w) / 2


def stack_center(boxes: list[Box], x: float):
    width = max(box.w for box in boxes)
    for box in boxes:
        box.x = x + (width - box.w) / 2
    return width


def bus(diagram: Diagram, origin, targets, bus_y, ms="1", me="0..*", label=""):
    xs = [point[0] for point in targets]
    lo, hi = min(xs + [origin[0]]), max(xs + [origin[0]])
    diagram.poly([origin, (origin[0], bus_y)], ms=ms, me="", label="")
    diagram.poly([(lo, bus_y), (hi, bus_y)], label=label, label_side=1)
    for point in targets:
        diagram.poly([(point[0], bus_y), point], ms="", me=me)


def place_row(boxes: list[Box], x: float, y: float, gap: float, height: float | None = None):
    cursor = x
    for box in boxes:
        box.x = cursor
        box.y = y + (0 if height is None else (height - box.h) / 2)
        cursor += box.w + gap
    return cursor


def build_alumni(erd: bool) -> Diagram:
    number = "43" if erd else "40"
    kind = "ERD" if erd else "Class Diagram"
    diagram = Diagram(f"figure-{number}-account-alumni", f"Figure {number}. Account and Alumni Management {kind}", erd)
    if erd:
        account = diagram.add("accounts", [
            ("PK", "id"), ("", "personal_email"), ("", "password_hash"), ("", "role"),
            ("", "status"), ("", "is_verified"), ("FK UK", "linked_student_id"),
            ("", "employee_number"), ("", "admin_privileges"),
        ])
        record = diagram.add("university_records", [("PK", "student_id"), ("", "degree"), ("", "year_graduated")])
        profile = diagram.add("alumni_profiles", [("PK", "id"), ("FK UK", "account_id"), ("", "degree"), ("", "year_graduated")])
        badge_def = diagram.add("badge_definitions", [("PK", "id"), ("UK", "key"), ("", "name")])
        badge = diagram.add("alumni_badges", [("PK", "id"), ("FK", "account_id"), ("FK", "badge_key")])
        request = diagram.add("profile_update_requests", [("PK", "id"), ("FK", "created_by"), ("", "subject"), ("", "status")])
        recipient = diagram.add("profile_update_request_recipients", [("PK", "id"), ("FK", "request_id"), ("FK", "alumni_id")])
        children = [
            diagram.add("alumni_jobs", [("PK", "id"), ("FK", "account_id"), ("", "job_title")]),
            diagram.add("further_studies", [("PK", "id"), ("FK", "account_id"), ("", "course_degree")]),
            diagram.add("alumni_seminars", [("PK", "id"), ("FK", "account_id"), ("", "title")]),
            diagram.add("alumni_certifications", [("PK", "id"), ("FK", "account_id"), ("", "certification_name")]),
            diagram.add("alumni_awards", [("PK", "id"), ("FK", "account_id"), ("", "title")]),
            diagram.add("alumni_skills", [("PK", "id"), ("FK", "account_id"), ("", "skill_name")]),
        ]
        labels = ("linked_student_id", "account_id", "badge_key", "account_id", "created_by", "request_id", "alumni_id", "account_id")
    else:
        account = diagram.add("Account", [
            "personalEmail", "passwordHash", "role", "status", "isVerified",
            "linkedStudentId", "employeeNumber", "adminPrivileges",
        ])
        record = diagram.add("UniversityRecord", ["studentId", "degree", "yearGraduated"])
        profile = diagram.add("AlumniProfile", [
            "phone", "address", "degree", "yearGraduated", "bio", "photo",
            "employmentStatus", "interestSpeaker", "interestMentor", "interestSponsor",
        ])
        badge_def = diagram.add("BadgeDefinition", ["key", "name", "description"])
        badge = diagram.add("AlumniBadge", ["badgeKey", "awardedAt"])
        request = diagram.add("ProfileUpdateRequest", ["subject", "requestedFields", "status"])
        recipient = diagram.add("ProfileUpdateRequestRecipient", ["emailStatus", "viewedAt", "completedAt"])
        children = [
            diagram.add("AlumniJob", ["jobTitle", "company", "isCurrent"]),
            diagram.add("FurtherStudy", ["courseDegree", "school", "yearEnrolled"]),
            diagram.add("AlumniSeminar", ["title", "location", "heldOn"]),
            diagram.add("AlumniCertification", ["certificationName", "issuingOrganization", "dateIssued"]),
            diagram.add("AlumniAward", ["title", "issuer", "awardedOn"]),
            diagram.add("AlumniSkill", ["skillName", "category"]),
        ]
        labels = ("match", "profile", "badge key", "awarded", "created by", "recipients", "alumnus", "")

    top = 78
    row_h = max(record.h, account.h, profile.h)
    record.y = top + (row_h - record.h) / 2
    account.y = top + (row_h - account.h) / 2
    profile.y = top + (row_h - profile.h) / 2
    left_w = stack_center([record], 36)
    record.x = 36 + (left_w - record.w) / 2
    account.x = 36 + left_w + 120
    profile.x = account.right + 120
    row_bottom = top + row_h

    stack_top = row_bottom + 112
    left_w = stack_center([badge_def, badge], 36)
    badge_def.y = stack_top
    badge.y = badge_def.bottom + 72
    request.x = profile.x
    request.y = stack_top
    recipient.x = profile.x
    if recipient.w > request.w:
        request.x = profile.x + (recipient.w - request.w) / 2
    else:
        recipient.x = request.x + (request.w - recipient.w) / 2
    recipient.y = request.bottom + 72
    stack_bottom = max(badge.bottom, recipient.bottom)

    kid_y = stack_bottom + 88
    place_row(children, 36, kid_y, 34)

    diagram.hlink(record, account, labels[0], "0..1", "0..1")
    diagram.hlink(account, profile, labels[1], "1", "0..1")
    diagram.vlink(badge_def, badge, labels[2], "1", "0..*")
    awarded_from = badge.anchor("e")
    awarded_to = account.anchor("s", 0.22)
    diagram.poly(
        [awarded_from, (awarded_to[0], awarded_from[1]), awarded_to],
        labels[3], "0..*", "1",
    )
    created_to = account.anchor("s", 0.58)
    created_from = request.anchor("n", 0.42)
    created_y = row_bottom + 78
    diagram.poly(
        [created_from, (created_from[0], created_y), (created_to[0], created_y), created_to],
        labels[4], "0..*", "1", label_segment=1,
    )
    diagram.vlink(request, recipient, labels[5], "1", "1..*")
    alumnus_to = account.anchor("s", 0.84)
    alumnus_from = recipient.anchor("e", 0.45)
    alumnus_x = max(profile.right, request.right, recipient.right) + 34
    alumnus_y = row_bottom + 40
    diagram.poly(
        [
            alumnus_from,
            (alumnus_x, alumnus_from[1]),
            (alumnus_x, alumnus_y),
            (alumnus_to[0], alumnus_y),
            alumnus_to,
        ],
        labels[6], "0..*", "1", label_side=1, label_segment=1,
    )
    bus(
        diagram,
        account.anchor("s", 0.36),
        [child.anchor("n") for child in children],
        kid_y - 36,
        "1",
        "0..*",
        labels[7],
    )
    diagram.finish(48 if erd else 36)
    return diagram


def build_tracer(erd: bool) -> Diagram:
    number = "44" if erd else "41"
    kind = "ERD" if erd else "Class Diagram"
    diagram = Diagram(f"figure-{number}-tracer-career", f"Figure {number}. Graduate Tracer and Career Analysis {kind}", erd)
    if erd:
        college = diagram.add("colleges", [("PK", "id"), ("", "name"), ("", "code")])
        program = diagram.add("academic_programs", [("PK", "id"), ("FK", "college_id"), ("", "name"), ("", "course_code")])
        registry = diagram.add("registry_imports", [("PK", "id"), ("", "filename"), ("", "imported_count"), ("FK", "admin_id")])
        resume = diagram.add("resumes", [("PK", "id"), ("FK", "account_id"), ("", "original_filename")])
        account = diagram.add("accounts", [("PK", "id"), ("", "personal_email"), ("", "role"), ("", "status")])
        submission = diagram.add("tracer_submissions", [
            ("PK", "id"), ("FK", "account_id"), ("FK", "resume_id"), ("FK", "student_id"),
            ("FK", "soc_code"), ("", "alignment_status"), ("", "alignment_score"),
        ])
        soc = diagram.add("soc_codes", [("PK", "soc_code"), ("", "description"), ("", "degree_patterns")])
        alignment = diagram.add("alignment_results", [
            ("PK", "id"), ("FK UK", "account_id"), ("", "overall_match_score"), ("", "alignment_justification"),
        ])
        record = diagram.add("university_records", [("PK", "student_id"), ("", "degree"), ("", "year_graduated")])
        mapping = diagram.add("job_title_mappings", [("PK", "id"), ("", "raw_title"), ("", "approved"), ("FK", "soc_code")])
        names = ("college_id", "account_id", "account_id", "soc_code", "account_id", "student_id", "soc_code", "admin_id")
    else:
        college = diagram.add("College", ["name", "code"])
        program = diagram.add("AcademicProgram", ["name", "courseCode"])
        registry = diagram.add("RegistryImport", ["filename", "importedCount"])
        resume = diagram.add("Resume", ["resumeFile", "extractedText", "parsedFields"])
        account = diagram.add("Account", ["personalEmail", "role", "status", "linkedStudentId"])
        submission = diagram.add("TracerSubmission", ["surveyAnswers", "alignmentStatus", "alignmentScore"])
        soc = diagram.add("SocCode", ["socCode", "description", "degreePathways"])
        alignment = diagram.add("AlignmentResult", ["score", "justification", "suggestedCareerPaths"])
        record = diagram.add("UniversityRecord", ["studentId", "degree", "yearGraduated"])
        mapping = diagram.add("JobTitleMapping", ["jobTitle", "approved"])
        names = ("programs", "resumes", "submissions", "soc code", "current alignment", "student record", "job title", "imported by")

    top = 78
    row2_y = top + max(college.h, program.h, registry.h) + 90
    row2_h = max(resume.h, account.h, submission.h, soc.h)
    place_row([resume, account, submission, soc], 36, row2_y, 156, row2_h)
    row3_y = row2_y + row2_h + 90
    for upper, lower in ((account, alignment), (submission, record), (soc, mapping)):
        lower.y = row3_y
        center_under(upper, lower)
    college.y = top + (max(college.h, program.h, registry.h) - college.h) / 2
    program.y = top + (max(college.h, program.h, registry.h) - program.h) / 2
    college.x = resume.x
    program.x = college.right + 130
    registry.y = top + (max(college.h, program.h, registry.h) - registry.h) / 2
    registry.x = soc.x + (soc.w - registry.w) / 2

    diagram.hlink(college, program, names[0], "1", "0..*")
    diagram.hlink(resume, account, names[1], "0..*", "1")
    diagram.hlink(account, submission, names[2], "1", "0..*")
    diagram.hlink(submission, soc, names[3], "0..*", "0..1")
    diagram.vlink(account, alignment, names[4], "1", "0..1")
    diagram.vlink(submission, record, names[5], "0..*", "0..1")
    diagram.vlink(soc, mapping, names[6], "0..1", "0..*")
    imported_from = registry.anchor("s")
    imported_to = account.anchor("n", 0.72)
    corridor = row2_y - 34
    diagram.poly(
        [imported_from, (imported_from[0], corridor), (imported_to[0], corridor), imported_to],
        names[7], "0..*", "0..1",
    )
    diagram.finish(48 if erd else 36)
    return diagram


def build_registration(erd: bool) -> Diagram:
    number = "45" if erd else "42"
    kind = "ERD" if erd else "Class Diagram"
    diagram = Diagram(f"figure-{number}-registration-auth", f"Figure {number}. Registration and Authentication {kind}", erd)
    if erd:
        draft = diagram.add("registration_drafts", [
            ("PK", "id"), ("", "personal_email"), ("", "password_hash"), ("", "privacy_consent"),
            ("", "original_filename"), ("FK", "linked_student_id"),
        ])
        record = diagram.add("university_records", [("PK", "student_id"), ("", "degree"), ("", "year_graduated")])
        account = diagram.add("accounts", [
            ("PK", "id"), ("", "personal_email"), ("", "password_hash"), ("", "role"),
            ("", "status"), ("FK UK", "linked_student_id"),
        ])
        reset = diagram.add("password_reset_verifications", [
            ("PK", "id"), ("", "email_hash"), ("", "pin_hash"), ("", "expires_at"),
            ("", "attempts"), ("FK", "account_id"),
        ])
        names = ("linked_student_id", "linked_student_id", "account_id")
    else:
        draft = diagram.add("RegistrationDraft", [
            "personalEmail", "passwordHash", "privacyConsent", "resumeFile", "extractedText", "parsedFields",
        ])
        record = diagram.add("UniversityRecord", ["studentId", "degree", "yearGraduated"])
        account = diagram.add("Account", ["personalEmail", "passwordHash", "role", "status", "isVerified", "linkedStudentId"])
        reset = diagram.add("PasswordResetVerification", ["emailHash", "pinHash", "expiresAt", "attempts"])
        names = ("possible match", "matched graduate", "recovery")

    top = 92
    row_h = max(draft.h, record.h, account.h)
    place_row([draft, record, account], 48, top, 150, row_h)
    reset.y = top + row_h + 100
    reset.x = account.x + (account.w - reset.w) / 2
    diagram.hlink(draft, record, names[0], "0..*", "0..1")
    diagram.hlink(record, account, names[1], "0..1", "0..1")
    diagram.vlink(account, reset, names[2], "0..1", "0..*")
    note = "The draft is removed after the survey is submitted and the account is created."
    diagram.note(draft.x, draft.bottom + 28, note)
    diagram.finish(48 if erd else 40)
    return diagram


def build_services(erd: bool) -> Diagram:
    number = "47" if erd else "46"
    kind = "ERD" if erd else "Class Diagram"
    diagram = Diagram(f"figure-{number}-alumni-services", f"Figure {number}. Alumni Services {kind}", erd)
    if erd:
        slot = diagram.add("aac_appointment_slots", [("PK", "id"), ("", "slot_date"), ("", "slot_time"), ("", "capacity")])
        card = diagram.add("alumni_cards", [("PK", "id"), ("FK UK", "account_id"), ("", "status"), ("", "card_number")])
        account = diagram.add("accounts", [("PK", "id"), ("", "personal_email"), ("", "role"), ("", "status")])
        redemption = diagram.add("alumni_perk_redemptions", [("PK", "id"), ("FK", "account_id"), ("FK", "perk_id"), ("", "redeemed_at")])
        perk = diagram.add("alumni_perks", [("PK", "id"), ("", "name"), ("", "requires_active_card")])
        activity = diagram.add("partner_activities", [
            ("PK", "id"), ("FK", "alumni_account_id"), ("FK", "recorded_by_id"), ("FK", "perk_id"), ("", "activity_type"),
        ])
        names = ("account_id", "account_id", "perk_id", "alumni_account_id", "recorded_by_id", "perk_id")
    else:
        slot = diagram.add("AacAppointmentSlot", ["slotDate", "slotTime", "capacity"])
        card = diagram.add("AlumniCard", ["status", "cardNumber", "appointmentDate", "appointmentTime"])
        account = diagram.add("Account", ["personalEmail", "role", "status"])
        redemption = diagram.add("AlumniPerkRedemption", ["redeemedAt", "code"])
        perk = diagram.add("AlumniPerk", ["name", "partner", "discount", "requiresActiveCard"])
        activity = diagram.add("PartnerActivity", ["activityType", "partnerName", "activityAt"])
        names = ("card", "claimed perk", "perk", "alumnus", "recorded by", "perk used")

    top = 78
    row_h = max(card.h, account.h, redemption.h, perk.h)
    row_y = top + slot.h + 70
    place_row([card, account, redemption, perk], 40, row_y, 120, row_h)
    slot.x = card.x + (card.w - slot.w) / 2
    slot.y = top
    activity.y = row_y + row_h + 100
    activity.x = account.x + (account.w - activity.w) / 2
    diagram.hlink(card, account, names[0], "0..1", "1")
    diagram.hlink(account, redemption, names[1], "1", "0..*")
    diagram.hlink(redemption, perk, names[2], "0..*", "1")
    shared_left = max(account.x, activity.x) + 36
    shared_right = min(account.right, activity.right) - 36
    diagram.poly(
        [(shared_left, activity.y), (shared_left, account.bottom)],
        names[3], "0..*", "0..1", label_side=-1,
    )
    diagram.poly(
        [(shared_right, activity.y), (shared_right, account.bottom)],
        names[4], "0..*", "0..1", label_side=1,
    )
    perk_target = perk.anchor("s")
    activity_source = activity.anchor("e")
    diagram.poly(
        [activity_source, (perk_target[0], activity_source[1]), perk_target],
        names[5], "0..*", "0..1",
    )
    diagram.note(slot.x, slot.bottom + 22, "Open schedule only. The card stores the chosen date and time.")
    diagram.finish(48 if erd else 36)
    return diagram


def write_index(diagrams: list[Diagram]):
    sections = []
    for diagram in diagrams:
        sections.append(
            f'<section class="sheet"><h2>{diagram.title}</h2>'
            f'<img src="{diagram.stem}.svg" alt="{diagram.title}"></section>'
        )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CareerSense class diagrams and ERDs</title>
  <style>
    body {{ margin: 0; background: #d9d9d9; color: #222; font-family: Arial, Helvetica, sans-serif; }}
    header {{ width: 1100px; max-width: calc(100% - 24px); margin: 20px auto; background: #fff; border: 1px solid #222; padding: 16px 20px; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    p {{ margin: 0; line-height: 1.45; }}
    .sheet {{ width: max-content; max-width: calc(100% - 24px); margin: 0 auto 28px; background: #fff; border: 1px solid #222; padding: 12px; }}
    h2 {{ font-size: 16px; margin: 0 0 8px; }}
    img {{ display: block; max-width: 100%; height: auto; }}
  </style>
</head>
<body>
  <header>
    <h1>3.5.3.3 Class Diagram and Entity Relationship Diagram</h1>
    <p>Figures 40 to 47. These follow the 24 wireframes in Figures 16 to 39.</p>
  </header>
  {''.join(sections)}
</body>
</html>
"""
    (ROOT / "index.html").write_text(html, encoding="utf-8")


def main():
    diagrams = [
        build_alumni(False),
        build_tracer(False),
        build_registration(False),
        build_alumni(True),
        build_tracer(True),
        build_registration(True),
        build_services(False),
        build_services(True),
    ]
    failed = False
    for diagram in diagrams:
        if diagram.problems:
            failed = True
        render(diagram)
    write_index(diagrams)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
