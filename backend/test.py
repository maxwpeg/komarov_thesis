from Project import Project
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


pdfmetrics.registerFont(TTFont("GOST Type A", "./GOST_A.TTF"))
pdfmetrics.registerFont(TTFont("GOST Type A Bold", "./GOST_A_BOLD.TTF"))
p = Project()
p.launch()
p.save()
print(p.code)