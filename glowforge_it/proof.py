"""One-page local proof, bound to a revision; generating it never grants approval."""
import os
from xml.sax.saxutils import escape

from PIL import Image, ImageOps

from .imaging import to_8bit

# Each image is drawn in a ~3.25 in slot; 1200 px is ~370 DPI there. Embedding the full-resolution
# source and preview made 48 MB "one-page" PDFs.
MAX_EMBED_PX = 1200


def write_proof(path, source_path, preview, record, material, thickness, options):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab

    # ReportLab distributes the embeddable Bitstream Vera font with the library.
    font = 'GFVera'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, os.path.join(os.path.dirname(reportlab.__file__), 'fonts', 'Vera.ttf')))
    font_face = pdfmetrics.getFont(font).face
    text = options.client + options.order + str(material)
    if any(ord(char) not in font_face.charToGlyph for char in text if not char.isspace()):
        raise ValueError('Proof metadata contains characters unsupported by the embedded Vera font.')
    c = canvas.Canvas(path, pagesize=(612, 792), invariant=1, pageCompression=1, initialFontName=font, initialFontSize=9)
    c.setTitle('Client approval proof - ' + record['revision'][:16])
    c.setAuthor('glowforge-it')
    style = ParagraphStyle('body', fontName=font, fontSize=9, leading=12, textColor='#243342')

    def para(text, y, height=48):
        p = Paragraph(escape(text), style)
        _, used = p.wrap(524, height)
        if used > height:
            raise ValueError('Proof metadata exceeds the one-page layout; shorten the fields.')
        p.drawOn(c, 44, y - used)
        return y - used - 8

    c.setFillColorRGB(.08, .16, .20)
    c.rect(0, 694, 612, 98, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont(font, 22)
    c.drawString(44, 750, 'Client approval proof')
    c.setFont(font, 9)
    c.drawString(44, 728, 'Simulated appearance - actual finish varies.')
    c.drawString(44, 710, 'Review copy. Not a full-size placement template.')
    y = para('Client: ' + (options.client or '(not supplied)'), 676)
    y = para('Order: ' + (options.order or '(not supplied)'), y)
    c.setFillColorRGB(.08, .16, .20)
    c.setFont(font, 11)
    c.drawString(44, 553, 'Source artwork')
    c.drawString(318, 553, 'Simulated maple finish')
    with Image.open(source_path) as src:
        src = to_8bit(ImageOps.exif_transpose(src)).convert('RGBA')
        source = Image.new('RGBA', src.size, 'white')
        source.alpha_composite(src)
        source = source.convert('RGB')
    preview = preview.copy()
    for img, x in ((source, 44), (preview, 318)):
        img.thumbnail((MAX_EMBED_PX, MAX_EMBED_PX), Image.Resampling.LANCZOS)
        c.setStrokeColorRGB(.8, .82, .83)
        c.rect(x, 305, 250, 232)
        c.drawImage(ImageReader(img), x + 8, 313, width=234, height=216, preserveAspectRatio=True, anchor='c', mask='auto')
    w, h = record['mask']['size_px']
    y = para(f'Artwork: {w/300:.4f} x {h/300:.4f} in | Material: {material} | Thickness: {thickness:g} in', 287, 48)
    if options.jig:
        y = para(f'Jig: {options.jig_rows} rows x {options.jig_columns} columns; proof shows one blank.', y)
    y = para('Revision SHA-256: ' + record['revision'], y)
    y = para('Source SHA-256: ' + record['source_sha256'], y)
    y = para('This proof binds source, recipe, engraving and appearance. Any change requires a new revision.', y)
    if options.score_marks:
        y = para('Finish preview shows engraving only. Review vector score marks separately in the SVG.', y)
    if y < 123:
        raise ValueError('Proof metadata leaves insufficient room for sign-off.')
    c.setFont(font, 10)
    c.drawString(44, 104, 'Approval: ____________________   Name: ____________________')
    c.drawString(44, 78, 'Date: ____________________   Revision accepted: ______________')
    c.setFont(font, 8)
    c.drawString(44, 42, 'Blank fields do not establish customer approval. No machine settings are specified.     1 / 1')
    c.showPage()
    c.save()
