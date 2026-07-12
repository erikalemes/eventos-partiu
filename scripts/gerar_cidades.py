# -*- coding: utf-8 -*-
"""Gera docs/cidades.js com todos os municipios do Brasil (nome + UF), via API do IBGE.
Usado pelo app para autocomplete, deteccao de cidade na consulta e busca por CEP.
Rodar so quando quiser atualizar a lista (muda raramente)."""
import gzip
import json
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"

req = urllib.request.Request(URL, headers={"User-Agent": "eventos-partiu/1.0"})
with urllib.request.urlopen(req, timeout=60) as resp:
    corpo = resp.read()
if corpo[:2] == b"\x1f\x8b":
    corpo = gzip.decompress(corpo)
municipios = json.loads(corpo.decode("utf-8"))

pares = sorted({(m["municipio-nome"], m["UF-sigla"]) for m in municipios})
conteudo = "window.CIDADES_BR = " + json.dumps([[n, u] for n, u in pares], ensure_ascii=False, separators=(",", ":")) + ";\n"
(RAIZ / "docs" / "cidades.js").write_text(conteudo, encoding="utf-8")
print(f"gravado docs/cidades.js com {len(pares)} municipios ({len(conteudo)//1024} KB)")
