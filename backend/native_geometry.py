"""Trusted helper run only with KiCad's bundled Python, never uploaded code."""
import json
import sys
import pcbnew

board=pcbnew.LoadBoard(sys.argv[1])
if board is None:raise RuntimeError('Native geometry loader could not open board')
objects=[]
def add(item,kind,reference=None):
    try:
        identifier=item.m_Uuid.AsString()
        box=item.GetBoundingBox()
        x0=pcbnew.ToMM(box.GetX());y0=pcbnew.ToMM(box.GetY())
        x1=x0+pcbnew.ToMM(box.GetWidth());y1=y0+pcbnew.ToMM(box.GetHeight())
        obj={'id':identifier,'kind':kind,'shape':'polygon','points':[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],'envelope':True,'geometry_source':'KiCad native object envelope','width':0,'layer':board.GetLayerName(item.GetLayer()),'reference':reference}
        if hasattr(item,'GetNetname'):obj['net']=item.GetNetname()
        if kind=='pad':obj['pad']=item.GetNumber()
        if kind=='component':obj['value']=item.GetValue()
        objects.append(obj)
    except (AttributeError,RuntimeError):pass
for footprint in board.GetFootprints():
    add(footprint,'component',footprint.GetReference())
    for pad in footprint.Pads():add(pad,'pad',footprint.GetReference())
    for graphic in footprint.GraphicalItems():add(graphic,'graphic',footprint.GetReference())
    for field in footprint.GetFields():add(field,'text',footprint.GetReference())
for drawing in board.GetDrawings():add(drawing,'graphic')
with open(sys.argv[2],'w',encoding='utf-8') as output:json.dump({'engine':pcbnew.GetBuildVersion(),'objects':objects},output)
