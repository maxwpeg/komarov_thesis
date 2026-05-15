from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.config import settings
from pdf_documents.Project import Project

pdfmetrics.registerFont(TTFont("GOST Type A", str(settings.regular_font_path)))
pdfmetrics.registerFont(TTFont("GOST Type A Bold", str(settings.bold_font_path)))
p = Project()
p.launch()
p.save()
print(p.code)
