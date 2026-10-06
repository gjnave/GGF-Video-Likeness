import numpy as np
from PIL import Image,ImageDraw,ImageFilter

def composite_selection(source,generated,box,context):
    """Feather inside an exclusive pixel rectangle; preserve every outside pixel."""
    x0,y0,x1,y1=map(int,box)
    if x1<=x0 or y1<=y0:
        raise ValueError('The selected head area is empty. Select the head again.')
    inset=max(2,round(min(x1-x0,y1-y0)*.05))
    mask=Image.new('L',source.size,0)
    ImageDraw.Draw(mask).rounded_rectangle((x0+inset,y0+inset,max(x0+inset,x1-inset-1),max(y0+inset,y1-inset-1)),radius=inset,fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(inset))
    region=Image.new('L',source.size,0)
    ImageDraw.Draw(region).rectangle((x0,y0,x1-1,y1-1),fill=255)
    mask=Image.fromarray(np.minimum(np.asarray(mask),np.asarray(region)))
    layer=source.copy()
    layer.paste(generated,context[:2])
    return Image.composite(layer,source,mask)
