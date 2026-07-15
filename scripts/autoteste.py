# -*- coding: utf-8 -*-
"""Autoteste do Eventos - Partiu?!
Roda sem internet: usa fixtures de HTML salvos em tests/fixtures e valida o
coletor, a deduplicacao, a exclusao de eventos passados e o dados.js gerado.

Uso: python scripts/autoteste.py
Sai com codigo 1 se qualquer verificacao falhar (o workflow usa isso).
"""
import json
import re
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

# ------------------------------------------ 2b. extracao Goiânia Pulsa (institucional)
html_gp = (FIXTURES / "goianiapulsa.html").read_text(encoding="utf-8", errors="ignore")
brutos_gp = coletar.extrai_goianiapulsa(html_gp)
verifica("goiania pulsa: extrai cartoes do fixture", len(brutos_gp) >= 30, f"so {len(brutos_gp)}")
norm_gp = [n for n in (coletar.normaliza_goianiapulsa(b) for b in brutos_gp) if n]
verifica("goiania pulsa: normaliza com nome/data/url", all(e["nome"] and len(e["dataInicio"]) == 10 and e["fonteUrl"].startswith("https://") for e in norm_gp))
verifica("goiania pulsa: fonte marcada", all(e["fonte"] == "Goiânia Pulsa" and e["tipoFonte"] == "institucional" for e in norm_gp))
verifica("goiania pulsa: cobre Centro de Convenções/Niemeyer",
         any(re.search(r"conven|niemeyer", coletar.normaliza_nome(e["local"])) for e in norm_gp))
_gp1 = coletar.normaliza_goianiapulsa({"url": "https://goianiapulsa.tur.br/evento/x/", "data": "24/07/2026", "titulo": "Gala Concert", "local": "Goiânia e Trindade"})
verifica("goiania pulsa: 'Goiânia e Trindade' fica Goiânia", _gp1["cidade"] == "Goiânia")

# ------------------------------------ 2c. CCGO e Ulysses (fontes oficiais)
html_ccgo = (FIXTURES / "ccgo.html").read_text(encoding="utf-8", errors="ignore")
norm_ccgo = [n for n in (coletar.normaliza_ccgo(b) for b in coletar.extrai_ccgo(html_ccgo)) if n]
verifica("ccgo: extrai eventos do fixture", len(norm_ccgo) >= 20, f"so {len(norm_ccgo)}")
verifica("ccgo: todos em Goiânia com fonte oficial", all(e["cidade"] == "Goiânia" and e["tipoFonte"] == "oficial" for e in norm_ccgo))
verifica("ccgo: intervalo '22 a 24/10/2026'", coletar._parse_intervalo_ddmm("22 a 24/10/2026") == ("2026-10-22", "2026-10-24"))
verifica("ccgo: data simples", coletar._parse_intervalo_ddmm("23/10/2026 - Teatro") == ("2026-10-23", ""))

html_uly = (FIXTURES / "ulysses.html").read_text(encoding="utf-8", errors="ignore")
norm_uly = [n for n in (coletar.normaliza_ulysses(b) for b in coletar.extrai_ulysses(html_uly)) if n]
verifica("ulysses: extrai eventos do fixture", len(norm_uly) >= 5, f"so {len(norm_uly)}")
verifica("ulysses: Brasília, oficial, com hora", all(e["cidade"] == "Brasília" and e["tipoFonte"] == "oficial" and e["horaInicio"] for e in norm_uly))

# ------------------------------------ 2d. links avulsos (BaladAPP etc.)
html_bap = (FIXTURES / "baladapp_happyland.html").read_text(encoding="utf-8", errors="ignore")
_av = coletar.extrai_avulso(html_bap, "https://baladapp.com.br/pt-BR/eventos/happy-land-2026/8948", "2026-07-15")
verifica("avulso: extrai titulo/datas/cidade do BaladAPP",
         _av is not None and _av["nome"] == "Happy Land 2026" and _av["dataInicio"] == "2026-07-03"
         and _av["dataFim"] == "2026-08-02" and _av["cidade"] == "Goiânia" and _av["uf"] == "GO")
verifica("avulso: local extraido", (_av or {}).get("local") == "Pecuária de Goiânia")
verifica("avulso: fonte pelo dominio", (_av or {}).get("fonte") == "BaladAPP")
verifica("avulso: pagina sem dados minimos e descartada",
         coletar.extrai_avulso("<html><title>Oi</title></html>", "https://x.com/e/1", "2026-07-15") is None)
verifica("avulso: intervalo cruzando meses", coletar.extrai_datas_texto_pt("Data: 03 de Julho à 02 de Agosto de 2026", "2026-07-15") == ("2026-07-03", "2026-08-02"))

# datas por extenso (Shopping Cerrado)
verifica("extenso: '16 a 19 de Julho'", coletar.extrai_datas_texto_pt("de 16 a 19 de Julho", "2026-07-12") == ("2026-07-16", "2026-07-19"))
verifica("extenso: 'até 19 de Julho' vira em cartaz", coletar.extrai_datas_texto_pt("promoção até 19 de Julho", "2026-07-12") == ("2026-07-12", "2026-07-19"))
verifica("extenso: dia único", coletar.extrai_datas_texto_pt("acontece dia 20 de junho de 2026", "2026-07-12") == ("2026-06-20", ""))
verifica("extenso: sem ano NUNCA vira ano seguinte", coletar.extrai_datas_texto_pt("dia 25 de abril", "2026-07-12")[0] == "2026-04-25")

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
verifica("categoria: dica de colecao show", "shows" in coletar.classifica("Nome neutro", dicas=["show-musica-festa"]))
# colecao real da Sympla: peca sem a palavra "teatro" no titulo vira teatro pela colecao
verifica("categoria: colecao teatro-espetaculo", coletar.classifica("O Alienista", dicas=["teatro-espetaculo"]) == ["teatro"])
verifica("categoria: colecao experiencias -> lazer", coletar.classifica("Passeio de barco", dicas=["experiencias"])[0] == "lazer")
verifica("categoria: parque aquatico -> lazer", "lazer" in coletar.classifica("Ingresso Parque Aquático SESC"))
verifica("categoria: sem match vira outros", coletar.classifica("zzzz qqqq") == ["outros"])
# uniao de categorias na deduplicacao (nao perde a categoria boa)
verifica("uniao: descarta outros se ha categoria real", coletar.uniao_categorias(["outros"], ["teatro"]) == ["teatro"])
verifica("uniao: junta sem repetir", coletar.uniao_categorias(["teatro"], ["shows", "teatro"]) == ["teatro", "shows"])
verifica("uniao: so outros permanece outros", coletar.uniao_categorias(["outros"], ["outros"]) == ["outros"])
_t1 = evento_base(categorias=["outros"])
_t2 = evento_base(categorias=["teatro"], descricao="mais completo")
verifica("dedup: une categorias das copias", coletar.remove_duplicados([_t1, _t2])[0]["categorias"] == ["teatro"])
# regressao do Happy Land: uma fonte so com a estreia + outra com o intervalo
# completo devem fundir mantendo o termino (senao o evento em temporada some)
_hl1 = evento_base(nome="Happy Land", dataInicio="2099-01-10", dataFim="", horaInicio="", descricao="x", endereco="y")
_hl2 = evento_base(nome="Happy Land", dataInicio="2099-01-10", dataFim="2099-02-10", fonte="BaladAPP",
                   fonteUrl="https://baladapp.com.br/e/1", urlInfo="https://baladapp.com.br/e/1", horaInicio="", local="Pecuária")
_hl = coletar.remove_duplicados([_hl1, _hl2])
verifica("dedup: funde periodo (mantem dataFim mais distante)", len(_hl) == 1 and _hl[0]["dataFim"] == "2099-02-10")
verifica("dedup: evento em temporada sobrevive ao filtro de passados",
         len(coletar.remove_passados_e_distantes(_hl, "2099-01-20")) == 1)

# ------------------------------------------------------------ 7. confiabilidade
verifica("confianca: completo = plataforma", coletar.confianca_de(evento_base()) == "plataforma")
verifica("confianca: sem hora = incompleta", coletar.confianca_de(evento_base(horaInicio="")) == "incompleta")
verifica("confianca: fonte oficial = oficial", coletar.confianca_de(evento_base(tipoFonte="oficial", horaInicio="")) == "oficial")
verifica("confianca: oficial sem local = incompleta", coletar.confianca_de(evento_base(tipoFonte="oficial", local="")) == "incompleta")

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
