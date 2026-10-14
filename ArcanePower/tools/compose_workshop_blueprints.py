"""Typeset the Blender schematic renders into three Workshop feature plates."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/workshop-blueprints'
OUT = ROOT / 'workshop/images'
OUT.mkdir(parents=True, exist_ok=True)
SANS = '/usr/share/fonts/nerd-fonts/Overpass/OverpassNerdFont-ExtraBold.otf'
MONO = '/usr/share/fonts/liberation-mono-fonts/LiberationMono-Regular.ttf'
INK = '#d3f2ff'
CYAN = '#64c8ed'
MUTED = '#83a9be'
GOLD = '#e5bc72'


def text(draw, pos, value, size=22, color=INK, bold=False):
    draw.text(pos, value, font=ImageFont.truetype(SANS if bold else MONO, size), fill=color)


def plate(number, title, subtitle):
    im = Image.new('RGB', (1600, 900), '#081e30')
    d = ImageDraw.Draw(im)
    for x in range(0, 1600, 40): d.line((x, 0, x, 900), fill='#102d41', width=1)
    for y in range(0, 900, 40): d.line((0, y, 1600, y), fill='#102d41', width=1)
    d.rectangle((24, 24, 1576, 876), outline='#315a70', width=1)
    d.rectangle((24, 24, 1576, 146), fill='#0a2235')
    text(d, (50, 39), 'ODB / ARCANE SYSTEMS', 18, CYAN)
    text(d, (1210, 39), 'TECHNICAL SERIES / '+number, 17, MUTED)
    text(d, (48, 65), title, 44, bold=True)
    text(d, (50, 117), subtitle, 17, MUTED)
    d.line((50, 151, 1550, 151), fill=CYAN, width=2)
    d.rectangle((25, 839, 1575, 875), fill='#0a2235')
    text(d, (50, 848), 'ARCANE POWER  /  BLENDER MODEL STUDY', 16, CYAN)
    text(d, (1020, 848), 'ORTHOGRAPHIC  /  NOT TO SCALE', 16, MUTED)
    return im, d


def model(im, name, rect):
    img = Image.open(SOURCE / (name+'.png')).convert('RGBA')
    box = img.getbbox()
    if box: img = img.crop(box)
    x, y, w, h = rect
    img.thumbnail((w, h), Image.Resampling.LANCZOS)
    im.paste(img, (int(x+(w-img.width)/2), int(y+(h-img.height)/2)), img)


def note(d, x, y, number, title, lines):
    text(d, (x, y), number, 21, GOLD)
    text(d, (x+48, y-3), title, 25, bold=True)
    for index, line in enumerate(lines): text(d, (x+48, y+35+index*28), line, 18, MUTED)


im, d = plate('01', 'REACTOR / CONTAINMENT ASSEMBLY', 'ENERGY GENERATION  //  CONTROLLED REACTION  //  EMERGENCY EJECTION')
model(im, 'reactor', (35, 170, 940, 640))
text(d, (67, 805), 'CUTAWAY: SHIELDS / GLAZING / TILE SHELL OMITTED; RINGS POSED', 15, CYAN)
d.line((992, 185, 992, 802), fill='#315a70', width=2)
note(d, 1030, 206, '01', 'THREE FUEL TIERS', ['Aether / Helion / Empyrean', '10 GW / 100 GW / 1 TW', 'Provisional maximum output'])
note(d, 1030, 367, '02', 'ACTIVE CONTAINMENT', ['Two external controllers', 'Two to four deployed rings', '80 replaceable shell tiles'])
note(d, 1030, 528, '03', 'A COMMITTED EXIT', ['Straight duct + outlet route', 'Physical core ejection', 'Critical fuse survives launch'])
d.rectangle((1030, 718, 1525, 789), outline=GOLD, width=1)
text(d, (1050, 732), 'CONTAINMENT IS A REQUIREMENT.', 22, GOLD, True)
text(d, (1050, 761), 'Keep the exit pointed away from home.', 15, MUTED)
im.save(OUT/'reactor-blueprint.png', optimize=True)

im, d = plate('02', 'CONTAINMENT / VENT HARDWARE', 'EXTERNAL MODULES  //  ALIGNED DUCTS  //  TERMINAL OUTLET')
parts = [('controller', '01 / STANDARD', 'CONTAINMENT CONTROLLER'), ('advanced-controller', '02 / ADVANCED', 'CONTAINMENT CONTROLLER'), ('duct', '03 / STACKABLE', 'VENT DUCT'), ('outlet', '04 / TERMINAL', 'VENT OUTLET')]
for i, (name, title, label) in enumerate(parts):
    x = 50 + i*380
    model(im, name, (x, 204, 350, 342))
    d.line((x, 570, x+340, 570), fill='#315a70', width=1)
    text(d, (x+4, 592), title, 22, GOLD, True)
    text(d, (x+4, 628), label, 17, CYAN)
note(d, 58, 706, 'A', 'PAIR THE CONTROLLERS', ['Standard, mixed or advanced pairs set ring capacity.'])
note(d, 848, 706, 'B', 'COMPLETE THE ROUTE', ['1-15 aligned ducts, then one terminal outlet.'])
im.save(OUT/'hardware-blueprint.png', optimize=True)

im, d = plate('03', 'ENERGY CORE / MODULAR STORAGE', 'NATIVE BATTERY STORAGE  //  CAPACITY  //  TRANSFER  //  STABILIZATION')
model(im, 'energy-core', (38, 181, 700, 575))
text(d, (100, 775), '3 x 3 x 3 LARGE GRID  /  1,000 MWh  /  10 GW BASE', 17, CYAN)
d.line((770, 185, 770, 805), fill='#315a70', width=2)
for i, (name, title, line1, line2) in enumerate([
    ('capacity', 'CAPACITY', 'Side sockets', '+100,000 MWh each'),
    ('transfer', 'TRANSFER', 'Rear socket', '1 TW ceiling'),
    ('stabilizer', 'STABILIZER', 'Top socket', 'Enables expansions')]):
    x=805+i*250
    model(im, name, (x, 240, 230, 265))
    text(d, (x+6, 539), title, 24, INK, True)
    text(d, (x+6, 577), line1, 16, CYAN)
    text(d, (x+6, 606), line2, 16, MUTED)
text(d, (813, 191), 'ADVANCED MODULES SHOWN', 18, GOLD)
note(d, 812, 690, '01', 'KEEP A RESERVE', ['Auto / Recharge / Discharge', 'Emergency support for eligible reactors', 'Each physical battery retains its own charge'])
im.save(OUT/'energy-blueprint.png', optimize=True)
print('Wrote three 1600x900 Workshop blueprint plates to', OUT)
