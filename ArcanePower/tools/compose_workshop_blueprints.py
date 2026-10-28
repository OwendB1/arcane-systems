"""Typeset the current Blender wireframe studies into Workshop feature plates."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.cache/workshop-blueprints'
OUT = ROOT / 'workshop/images'
OUT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plates', nargs='+', choices=[f'{i:02}' for i in range(1, 13)],
                    help='Rebuild only these plates from their Blender studies.')
selected = set(parser.parse_args().plates or [f'{i:02}' for i in range(1, 13)])
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


if '01' in selected:
    im, d = plate('01', 'REACTOR / CONTAINMENT ASSEMBLY', 'ENERGY GENERATION  //  CONTROLLED REACTION  //  EMERGENCY EJECTION')
    model(im, 'reactor', (35, 170, 940, 640))
    text(d, (67, 805), 'CUTAWAY: SHIELDS / GLAZING / TILE SHELL OMITTED; RINGS POSED', 15, CYAN)
    d.line((992, 185, 992, 802), fill='#315a70', width=2)
    note(d, 1030, 206, '01', 'THREE FUEL TIERS', ['Aether / Helion / Empyrean', '5 / 50 / 250 GW fuel input', 'Up to 200 GW electrical'])
    note(d, 1030, 367, '02', 'ACTIVE CONTAINMENT', ['Two external controllers', 'Four independent heat circuits', '80 replaceable shell tiles'])
    note(d, 1030, 528, '03', 'A COMMITTED EXIT', ['Straight duct + outlet route', 'Physical core ejection', 'Critical fuse survives launch'])
    d.rectangle((1030, 718, 1525, 789), outline=GOLD, width=1)
    text(d, (1050, 732), 'CONTAINMENT IS A REQUIREMENT.', 22, GOLD, True)
    text(d, (1050, 761), 'Keep the exit pointed away from home.', 15, MUTED)
    im.save(OUT/'reactor-blueprint.png', optimize=True)

if '02' in selected:
    im, d = plate('02', 'CONTAINMENT / VENT HARDWARE', 'EXTERNAL MODULES  //  ALIGNED DUCTS  //  TERMINAL OUTLET')
    parts = [('controller', '01 / STANDARD', 'CONTAINMENT CONTROLLER'), ('advanced-controller', '02 / ADVANCED', 'CONTAINMENT CONTROLLER'), ('duct', '03 / STACKABLE', 'VENT DUCT'), ('outlet', '04 / TERMINAL', 'VENT OUTLET')]
    for i, (name, title, label) in enumerate(parts):
        x = 50 + i*380
        model(im, name, (x, 204, 350, 342))
        d.line((x, 570, x+340, 570), fill='#315a70', width=1)
        text(d, (x+4, 592), title, 22, GOLD, True)
        text(d, (x+4, 628), label, 17, CYAN)
    note(d, 58, 706, 'A', 'PAIR THE CONTROLLERS', ['Standard, mixed or advanced pairs set ring capacity.'])
    note(d, 848, 706, 'B', 'COMPLETE THE ROUTE', ['1-15 aligned ducts, then one terminal outlet.', 'Airtight outlet with a sealed ejection hatch.'])
    im.save(OUT/'hardware-blueprint.png', optimize=True)

if '03' in selected:
    im, d = plate('03', 'ENERGY CORE / MODULAR STORAGE', 'NATIVE BATTERY STORAGE  //  CAPACITY  //  TRANSFER  //  STABILIZATION')
    model(im, 'energy-bank', (38, 181, 700, 550))
    text(d, (70, 745), 'ASSEMBLED BANK / NATIVE SE UPGRADE SOCKETS', 17, GOLD)
    text(d, (70, 777), 'CORE: 3 x 3 x 3 LG / 1,000 MWh / 4 GW IN / 10 GW OUT', 17, CYAN)
    text(d, (70, 806), 'GLAZING OMITTED TO SHOW INTERNAL ASSEMBLY', 14, MUTED)
    d.line((770, 185, 770, 805), fill='#315a70', width=2)
    for i, (name, title, line1, line2) in enumerate([
        ('capacity', 'CAPACITY', 'Any compatible bay', '+10,000 / +100,000 MWh'),
        ('transfer', 'TRANSFER', '40 / 200 GW charge', '100 GW / 1 TW discharge'),
        ('stabilizer', 'STABILIZER', 'Any compatible bay', 'Matching / lower tiers')]):
        x=805+i*250
        model(im, name, (x, 225, 230, 295))
        text(d, (x+6, 539), title, 24, INK, True)
        text(d, (x+6, 577), line1, 16, CYAN)
        text(d, (x+6, 606), line2, 15, MUTED)
    text(d, (813, 191), '1 x 3 x 1 LG / ADVANCED PILLARS', 18, GOLD)
    note(d, 812, 690, '01', 'KEEP A RESERVE', ['Auto / Recharge / Discharge', 'Five-second jump-drive surge', 'Four bays accept any supported module'])
    im.save(OUT/'energy-blueprint.png', optimize=True)



def grid_plate(number, title, subtitle, filename, parts, columns=4, footnote=''):
    if number not in selected: return
    im, d = plate(number, title, subtitle)
    rows = (len(parts)+columns-1)//columns
    width, height = 1500/columns, 615/rows
    for index, (name, label, detail) in enumerate(parts):
        x, y = 50+(index%columns)*width, 177+(index//columns)*height
        model(im, name, (x+10, y, width-30, height-88))
        d.line((x+12, y+height-81, x+width-20, y+height-81), fill='#315a70')
        text(d, (x+16, y+height-71), label, 21 if columns<4 else 19, GOLD, True)
        text(d, (x+16, y+height-38), detail, 16 if columns<4 else 15, MUTED)
    if footnote: text(d, (62, 809), footnote, 15, CYAN)
    im.save(OUT/filename, optimize=True)


if '04' in selected:
    grid_plate('04', 'BRAYTON / TURBINE FAMILY', 'ONE TURBINE PER CIRCUIT  //  INTEGRATED COMPRESSOR  //  REGULAR + MIRRORED', 'turbines-blueprint.png', [
        ('turbine', 'T1 / STANDARD', '3.5 GW max / flat 80% Brayton conversion'),
        ('turbine-upgraded', 'T2 / UPGRADED', '50 GW max / Helion 40 GW across four'),
        ('turbine-mirrored', 'T1 / MIRRORED', 'Four T1 / Helion: 14 GW out + cooling'),
        ('turbine-mirrored-upgraded', 'T2 / MIRRORED UPGRADED', 'Empyrean: 200 GW output + 200 GW cooling')], 2,
        '2 WIDE x 2 HIGH x 5 LONG LG  /  ALIGN H + C  /  EACH CIRCUIT RECEIVES UP TO 25% OF SOURCE HEAT')

if '05' in selected:
    im, d = plate('05', 'ATMOSPHERIC / HEAT REJECTION', 'AIRTIGHT HULL CASING  //  DUPLEX MANIFOLD  //  CLEAR EXHAUST REQUIRED')
    model(im, 'air-cooler', (45, 177, 740, 460))
    model(im, 'air-cooler-rear', (815, 177, 740, 460))
    text(d, (66, 635), 'FRONT / TWIN FAN GUARDS', 23, GOLD, True)
    text(d, (824, 635), 'REAR / H + C CONNECTIONS', 23, GOLD, True)
    note(d, 65, 692, '01', 'TWO EQUIPMENT TIERS', ['5 GW standard / 50 GW upgraded', 'Fits a 3 x 3 hull opening / 2 cells deep'])
    note(d, 824, 692, '02', 'LEAVE THE FANS CLEAR', ['2.5 m beyond both guards', 'Vacuum provides no active cooling'])
    im.save(OUT/'cooling-blueprint.png', optimize=True)

if '06' in selected:
    im, d = plate('06', 'RADIATORS / MODULAR ARRAY', 'PASSIVE HEAT REJECTION  //  SUN TRACKING  //  BASE + UP TO THREE PANELS')
    model(im, 'radiator-stack', (48, 175, 700, 635))
    text(d, (70, 805), 'SEALED BASE + THREE SEPARATE PANELS / AUTHORING POSE', 15, CYAN)
    d.line((778, 185, 778, 805), fill='#315a70', width=2)
    model(im, 'space-radiator', (800, 177, 340, 330))
    model(im, 'radiator-panel', (1170, 177, 340, 330))
    text(d, (822, 522), '1 x 1 x 1 / SEALED BASE', 21, GOLD, True)
    text(d, (1190, 522), 'SEPARATE PANEL', 22, GOLD, True)
    note(d, 812, 592, '01', 'PANELS PROVIDE THE COOLING', ['2 / 20 GW per standard / upgraded panel', 'Three panels: 6 / 60 GW in shaded vacuum'])
    note(d, 812, 710, '02', 'SEAL THE BASE INTO THE HULL', ['Bottom H/C feed / base has no cooling itself', 'Match Up; any yaw / tracking stays on-grid'])
    im.save(OUT/'radiators-blueprint.png', optimize=True)

for bare, number, title in [(False, '07', 'ENCLOSED'), (True, '08', 'BARE')]:
    parts = []
    for shape, label, detail in [
        ('straight', 'STRAIGHT', 'Opposed H / C ports'), ('elbow', 'ELBOW', 'Horizontal turn'),
        ('riser', 'RISER', 'Vertical transition'), ('tee', 'TEE', 'Branch within one circuit'),
        ('cross', 'CROSS', 'Four-way junction'), ('roll-adapter', 'ROLL ADAPTER', 'Rotate the duplex roll'),
        ('end-cap', 'END CAP', 'Seal unused pipe mouths'), ('reactor-adapter', 'REACTOR ADAPTER', 'Offset end faces vessel')]:
        parts.append(('pipe-'+shape+('-bare' if bare else ''), label, detail))
    grid_plate(number, 'DUPLEX PIPEWORK / '+title, 'ONE LARGE-GRID CELL  //  SHARED SUPPLY + RETURN  //  KEEP REACTOR CIRCUITS SEPARATE',
               ('bare' if bare else 'framed')+'-pipes-blueprint.png', parts,
               footnote=('MATCH OPPOSING FACES AND H/C ROLL  /  CAP OPEN MOUTHS  /  CONVEYORS DO NOT CARRY HEAT'
                         if bare else 'MATCH H/C ROLL  /  CAP OPEN MOUTHS  /  FULL BLOCK CASINGS SEAL AGAINST ADJACENT ARMOR'))

if '09' in selected:
    im, d = plate('09', 'ENERGY CORE / COMPLETE BANK', 'FULL ASSEMBLY  //  FOUR UNIVERSAL BAYS  //  COMPLETE CASING + GLAZING OUTLINES')
    model(im, 'energy-full', (40, 175, 1030, 635))
    d.line((1090, 185, 1090, 805), fill='#315a70', width=2)
    note(d, 1120, 210, '01', 'PHYSICAL STORAGE', ['3 x 3 x 3 LG core', '1,000 MWh base capacity', 'Each cell keeps its charge'])
    note(d, 1120, 388, '02', 'FOUR FLEXIBLE BAYS', ['2 advanced capacity units', '1 advanced transfer unit', '1 advanced stabilizer'])
    note(d, 1120, 566, '03', 'BANK ABILITIES', ['Five-second drive surge', 'Ten-second burst output', 'Reserve + reactor support'])
    text(d, (70, 804), 'WIRE-FRAME GLAZING / NO STRUCTURAL CUTAWAY / ASSEMBLED ADVANCED MODULES', 15, CYAN)
    im.save(OUT/'full-energy-blueprint.png', optimize=True)

if '10' in selected:
    grid_plate('10', 'STORAGE / UPGRADE MODULES', '1 x 3 x 1 LARGE-GRID PILLARS  //  ANY CORE BAY  //  ALIGN UP AND FACE CONNECTORS INWARD', 'energy-modules-blueprint.png', [
        ('capacity-standard', 'STANDARD CAPACITY', '+10,000 MWh'),
        ('transfer-standard', 'STANDARD TRANSFER', '40 GW charge / 100 GW discharge'),
        ('stabilizer-standard', 'STANDARD STABILIZER', 'Supports standard modules'),
        ('capacity', 'ADVANCED CAPACITY', '+100,000 MWh'),
        ('transfer', 'ADVANCED TRANSFER', '200 GW charge / 1 TW discharge'),
        ('stabilizer', 'ADVANCED STABILIZER', 'Supports both equipment tiers')], 3,
        'STRONGEST TRANSFER / STABILIZER TIER APPLIES  /  MATCHING OR STRONGER STABILIZER REQUIRED')

if '11' in selected:
    im, d = plate('11', 'PIPE ROTOR / SEALED ROTARY UNION', 'NATIVE ADVANCED ROTOR  //  H + C ACROSS GRIDS  //  ADJUSTABLE CASING GAP')
    model(im, 'pipe-rotor-assembly', (48, 177, 700, 615))
    text(d, (70, 805), 'ASSEMBLED AT DEFAULT DISPLACEMENT / 200 mm CASING GAP', 15, CYAN)
    d.line((778, 185, 778, 805), fill='#315a70', width=2)
    model(im, 'pipe-rotor', (800, 180, 340, 330))
    model(im, 'pipe-rotor-head', (1170, 180, 340, 330))
    text(d, (822, 522), 'SEALED STATOR', 22, GOLD, True)
    text(d, (1190, 522), 'HEAD + ROTATING CUFF', 21, GOLD, True)
    note(d, 812, 592, '01', 'ONE CELL PER CASING', ['100-300 mm adjustable separation', 'Keep the rotating square head sweep clear'])
    note(d, 812, 710, '02', 'MATCH THE ARCANE HEAD', ['Native conveyor connection + duplex heat', 'Radiator tracking uses its separate base'])
    im.save(OUT/'pipe-rotor-blueprint.png', optimize=True)

if '12' in selected:
    im, d = plate('12', 'HULL RADIATORS / SURFACE ARRAY', 'FLUSH HULL FIT  //  FOUR SELF-SEALING EDGES  //  REAR DUPLEX FEED')
    model(im, 'hull-radiator-array', (45, 177, 755, 490))
    model(im, 'hull-radiator-rear', (835, 177, 705, 340))
    text(d, (66, 672), 'DAISY-CHAIN ON ALL FOUR EDGES', 23, GOLD, True)
    text(d, (850, 532), 'REAR / STANDARD H + C SOCKET', 22, GOLD, True)
    note(d, 65, 720, '01', 'FIXED / SINGLE RADIATING FACE', ['1 GW standard / 10 GW upgraded per block', '1 DEEP x 2 HIGH x 3 WIDE / full airtight backing'])
    note(d, 838, 592, '02', 'ONE FEED SERVES THE ARRAY', ['Only matching radiators join the edges.', 'Normal pipes connect at the lower rear.'])
    note(d, 838, 710, '03', 'NEIGHBORS SELF-SEAL', ['Removing a panel closes adjacent sockets.', 'Failed panels stay sealed but stop cooling.'])
    im.save(OUT/'hull-radiators-blueprint.png', optimize=True)

print('Wrote', len(selected), '1600x900 Workshop blueprint plates to', OUT)
