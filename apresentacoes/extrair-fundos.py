"""Extrai os fundos do template-criterio.pptx para a pasta fundos/.

Rodar só se o template mudar:  python3 extrair-fundos.py
Os gradientes viram JPEG (qualidade 92); os fundos lisos ficam em PNG.
"""
import io
import zipfile
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).parent
MAPA = {
    7: "gradiente-azul", 8: "gradiente-luz", 9: "blocos-escuros", 10: "blocos-azuis",
    12: "nevoa", 11: "navy", 13: "branco", 14: "preto",
}

with zipfile.ZipFile(AQUI / "template-criterio.pptx") as z:
    for n, nome in MAPA.items():
        im = Image.open(io.BytesIO(z.read(f"ppt/media/image{n}.png"))).convert("RGB")
        if n in (11, 13, 14):
            im.save(AQUI / "fundos" / f"{nome}.png", optimize=True)
        else:
            im.save(AQUI / "fundos" / f"{nome}.jpg", quality=92, subsampling=0)
        print(nome)
