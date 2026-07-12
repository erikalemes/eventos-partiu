# -*- coding: utf-8 -*-
"""Autoteste do Eventos - Partiu?!
Roda sem internet: usa fixtures de HTML salvos em tests/fixtures e valida o
coletor, a deduplicacao, a exclusao de eventos passados e o dados.js gerado.

Uso: python scripts/autoteste.py
Sai com codigo 1 se qualquer verificacao falhar (o workflow usa isso).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "tests" / "fixtures"
FALHAS = []


def verifica(nome, condicao, detalhe=""):
    status = "ok " if condicao else "FALHOU"
    print(f"[{status}] {nome}" + (f" -> {detalhe}" if detalhe and not condicao else ""))
    if not condicao:
        FALHAS.append(nome)


def evento_base(**kw):
    ev = {
        "nome": "Show Teste", "descricao": "", "categorias": ["shows"],
        "dataInicio": "2099-01-10", "horaInicio": "20:00", "dataFim": "", "horaFim": "",
        "local": "Teatro X", "endereco": "Rua 1", "bairro": "", "cidade": "Goiânia", "uf": "GO",
        "lat": None, "lon": None, "gratuito": False, "online": False,
        "urlIngresso": "https://exemplo.com/e/1", "urlInfo": "https://exemplo.com/e/1",
        "imagem": "", "fonte": "Sympla", "fonteUrl": "https://exemplo.com/e/1",
        "tipoFonte": "plataforma", "organizador": "",
    }
    ev.update(kw)
    return ev


# ---------------------------------------------------------- 1. extracao Sympla
html_sympla = (FIXTURES / "sympla_goiania.html").read_text(encoding="utf-8")
brutos = coletar.extrai_sympla(html_sympla)
verifica("sympla: extrai eventos do fixture", len(brutos) >= 30, f"so {len(brutos)}")
cidade_teste = {"nome": "Goiânia", "uf": "GO", "slugSympla": "goiania-go", "slugEventbrite": "x"}
normalizados = [n for n in (coletar.normaliza_sympla(b, cidade_teste) for b in brutos) if n]
verifica("sympla: normaliza todos com nome/data/url", all(e["nome"] and e["dataInicio"] and e["urlInfo"] for e in normalizados))
verifica("sympla: datas em formato ISO", all(len(e["dataInicio"]) == 10 and e["dataInicio"][4] == "-" for e in normalizados))
verifica("sympla: urls https", all(e["urlInfo"].startswith("https://") for e in normalizados))

# ------------------------------------------------------ 2. extracao Eventbrite
html_eb = (FIXTURES / "eventbrite_goiania.html").read_text(encoding="utf-8")
brutos_eb = coletar.extrai_eventbrite(html_eb)
verifica("eventbrite: extrai eventos do fixture", len(brutos_eb) >= 1, f"so {len(brutos_eb)}")
norm_eb = [n for n in (coletar.normaliza_eventbrite(b, cidade_teste) for b in brutos_eb) if n]
verifica("eventbrite: so aceita eventos com local na cidade pesquisada", all(e["cidade"] == "Goiânia" and e["uf"] == "GO" for e in norm_eb))
# regressao do bug de Sao Sebastiao: evento cujo local e em outra cidade nao pode
# ser carimbado como sendo da cidade pesquisada (nao inventar local).
_bruto_outra = {"name": "Curso em Santos", "start_date": "2099-01-01", "url": "https://exemplo.com/x",
                "primary_venue": {"name": "Local", "address": {"city": "Santos", "region": "SP"}}}
verifica("eventbrite: descarta evento de outra cidade", coletar.normaliza_eventbrite(_bruto_outra, cidade_teste) is None)
_bruto_mesma = {"name": "Show em Goiania", "start_date": "2099-01-01", "start_time": "20:00", "url": "https://exemplo.com/y",
                "primary_venue": {"name": "Local", "address": {"city": "Goiânia", "region": "GO"}}}
verifica("eventbrite: mantem evento da cidade pesquisada", (coletar.normaliza_eventbrite(_bruto_mesma, cidade_teste) or {}).get("cidade") == "Goiânia")

# ------------------------------------------------------------- 3. parse datas
verifica("data pt: 'Sex, 17 Jul - 2026 · 23:00'", coletar._parse_data_pt("Sex, 17 Jul - 2026 · 23:00") == ("2026-07-17", "23:00"))
verifica("data pt: sem hora", coletar._parse_data_pt("Dom, 1 Mar - 2027") == ("2027-03-01", ""))
verifica("data utc->local", coletar._data_utc_para_local("2026-07-18T02:00:00+00:00") == ("2026-07-17", "23:00"))

# ------------------------------------------------------------ 4. duplicidades
a = evento_base()
b = evento_base(fonte="Eventbrite", fonteUrl="https://outra.com/e/9", urlInfo="https://outra.com/e/9", descricao="descricao rica")
unicos = coletar.remove_duplicados([a, b])
verifica("dedup: mesmo nome+data+cidade vira 1", len(unicos) == 1)
verifica("dedup: guarda fonte adicional", unicos[0].get("fontesAdicionais", [{}])[0].get("nome") in ("Sympla", "Eventbrite"))
verifica("dedup: mantem o mais completo", unicos[0]["descricao"] == "descricao rica")
c = evento_base(nome="Outro Show", urlInfo="https://exemplo.com/e/2", fonteUrl="https://exemplo.com/e/2")
verifica("dedup: eventos diferentes nao se fundem", len(coletar.remove_duplicados([a, c])) == 2)

# ------------------------------------------------- 5. passados e muito futuros
hoje = "2026-07-12"
passado = evento_base(dataInicio="2026-07-01", dataFim="")
em_cartaz = evento_base(nome="Mostra Longa", dataInicio="2026-06-01", dataFim="2026-12-01")
futuro_ok = evento_base(nome="Prox", dataInicio="2026-08-01")
muito_longe = evento_base(nome="Longe", dataInicio="2027-06-01")
filtrados = coletar.remove_passados_e_distantes([passado, em_cartaz, futuro_ok, muito_longe], hoje)
nomes = {e["nome"] for e in filtrados}
verifica("datas: exclui evento encerrado", "Show Teste" not in nomes)
verifica("datas: mantem evento em cartaz", "Mostra Longa" in nomes)
verifica("datas: mantem evento futuro", "Prox" in nomes)
verifica("datas: exclui evento distante demais", "Longe" not in nomes)

# -------------------------------------------------------------- 6. categorias
verifica("categoria: show", "shows" in coletar.classifica("Show da Banda X ao vivo"))
verifica("categoria: infantil", "infantil" in coletar.classifica("Teatro infantil da Turma"))
verifica("categoria: dica de colecao", "shows" in coletar.classifica("Nome neutro", dicas=["show-musica-festa"]))
verifica("categoria: sem match vira outros", coletar.classifica("zzzz qqqq") == ["outros"])

# ------------------------------------------------------------ 7. confiabilidade
verifica("confianca: completo = plataforma", coletar.confianca_de(evento_base()) == "plataforma")
verifica("confianca: sem hora = incompleta", coletar.confianca_de(evento_base(horaInicio="")) == "incompleta")

# ------------------------------------------------------- 8. dados.js publicado
arq = RAIZ / "docs" / "dados.js"
verifica("dados.js existe", arq.exists())
if arq.exists():
    txt = arq.read_text(encoding="utf-8")
    dados = json.loads(txt[txt.find("{"):txt.rfind(";")])
    evs = dados["eventos"]
    hoje_real = datetime.now(coletar.FUSO_BRASILIA).strftime("%Y-%m-%d")
    verifica("dados.js: tem eventos suficientes", len(evs) >= 10, str(len(evs)))
    verifica("dados.js: nenhum evento encerrado", all((e["dataFim"] or e["dataInicio"]) >= hoje_real for e in evs))
    verifica("dados.js: todos com fonte e url", all(e["fonte"] and e["fonteUrl"].startswith("https://") for e in evs))
    verifica("dados.js: todos com cidade e uf", all(e["cidade"] and len(e["uf"]) == 2 for e in evs))
    verifica("dados.js: ids unicos", len({e["id"] for e in evs}) == len(evs))
    verifica("dados.js: geradoEm preenchido", bool(dados.get("geradoEm")))

print()
if FALHAS:
    print(f"AUTOTESTE FALHOU: {len(FALHAS)} verificacao(oes): {', '.join(FALHAS)}")
    sys.exit(1)
print("AUTOTESTE OK: todas as verificacoes passaram.")
