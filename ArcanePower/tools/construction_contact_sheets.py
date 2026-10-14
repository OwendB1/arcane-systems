"""Assemble the authored stage renders into review sheets, without altering art."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from prepare_lab import ROOT
from prepare_energy_core import BLOCKS

font = ImageFont.truetype('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf', 18)


def sheet(rows, output, finished=False):
    columns = 4 if finished else 3
    width, height = 360, 285
    canvas = Image.new('RGB', (width*columns, 65+height*len(rows)), (20,26,34))
    draw = ImageDraw.Draw(canvas)
    for i, label in enumerate(('Welded frame', 'Equipment installed', 'Partial armor', 'Finished')[:columns]):
        draw.text((i*width+15, 20), label, font=font, fill='white')
    for row, (label, paths) in enumerate(rows):
        draw.text((15, 62+row*height), label, font=font, fill=(125,210,245))
        for column, path in enumerate(paths):
            image = Image.open(path).convert('RGBA')
            image.thumbnail((width, height-35))
            canvas.paste(image, (column*width+(width-image.width)//2, 95+row*height), image)
    canvas.save(output)


def main():
    labels = {'ReactorPrototype':'Reactor', 'ContainmentController':'Containment controller',
              'AdvancedContainmentController':'Advanced containment controller',
              'VentDuct':'Vent duct', 'VentOutlet':'Vent outlet'}
    rows = [(label, [ROOT/'validation/construction'/('ArcanePower_'+name+'_BS'+str(i)+'.png')
                     for i in (1,2,3)]) for name,label in labels.items()]
    sheet(rows, ROOT/'validation/construction-stages.png')
    rows = [(label, [ROOT/'validation/energy'/(name+'_BS'+str(i)+'.png') for i in (1,2,3)]
             + [ROOT/'assets/icons/energy'/(name+'.png')]) for name,(label,*_) in BLOCKS.items()]
    sheet(rows, ROOT/'validation/energy-core-stages.png', finished=True)


if __name__ == '__main__': main()
