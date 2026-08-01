from pathlib import Path

import pypdfium2 as pdfium


SOURCES = (
    (Path("References/Datasheets/LV-322501 Datasheet.pdf"), Path("tmp/pdfs/lv322501_render")),
    (Path("References/Datasheets/323C003 Datasheet.pdf"), Path("tmp/pdfs/323c003_render")),
)


for source, output_dir in SOURCES:
    output_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(source)
    print(f"{source}: {len(document)} pages")
    for index in range(len(document)):
        page = document[index]
        bitmap = page.render(scale=2.5)
        image = bitmap.to_pil()
        image.save(output_dir / f"page-{index + 1:02d}.png")
        bitmap.close()
        page.close()
    document.close()
