# -*- coding: utf-8 -*-
"""
Eventos - Partiu?! : robo de coleta de eventos reais.

Fontes (plataformas publicas de venda de ingressos):
  - Sympla     : paginas publicas por cidade (payload JSON embutido no HTML)
  - Eventbrite : paginas publicas de busca por cidade (window.__SERVER_DATA__)

Saida: docs/dados.js  ->  window.EVENTOS_DATA = {...}

Regras de honestidade dos dados:
  - Nada e inventado: todo campo vem da fonte; campo ausente fica vazio.
  - Preco so aparece quando a fonte informa (a listagem quase nunca informa),
    entao o app manda o usuario "ver no site" pelo link oficial.
  - Todo evento carrega nome da fonte + URL original + horario da coleta.

Uso:
  python scripts/coletar.py    # coleta e grava docs/dados.js
"""
import json
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
FUSO_BRASILIA = timezone(timedelta(hours=-3))
PAUSA_ENTRE_REQUISICOES = 1.5  # segundos, para nao sobrecarregar as fontes
PAGINAS_SYMPLA_POR_CIDADE = 3
MAX_DIAS_FUTURO = 240  # ignora eventos a mais de ~8 meses (incham o arquivo)

MESES_PT = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
            "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def log(*args):
    print("[coletar]", *args, flush=True)


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")


def normaliza_nome(texto):
    """Chave de comparacao: minusculas, sem acento, sem pontuacao, espacos unicos."""
    t = sem_acento(texto).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def baixa(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", "ignore")


# ------------------------------------------------- classificador de categoria

CATEGORIAS = [
    ("infantil",     ["infantil", "crianca", "kids", "para criancas", "circo"]),
    ("teatro",       ["teatro", "espetaculo", "peca ", "drama", "musical "]),
    ("stand-up",     ["stand up", "stand-up", "standup", "humor", "comedy", "comedia"]),
    ("shows",        ["show", "tributo", "turne", "tour ", "ao vivo", "banda", "cantor", "sertanejo", "pagode", "samba", "rock", "mpb", "rap ", "forro", "eletronic"]),
    ("festas",       ["festa", "balada", "festival", "bloco", "arraia", "reveillon", "halloween", "after", "sunset"]),
    ("gastronomia",  ["gastronom", "degustacao", "cerveja", "vinho", "torresmo", "churrasco", "food", "culinar", "boteco", "cafe "]),
    ("cursos",       ["curso", "workshop", "oficina", "aula", "treinamento", "capacitacao", "imersao", "bootcamp", "masterclass"]),
    ("congressos",   ["congresso", "palestra", "simposio", "seminario", "summit", "conferencia", "forum", "encontro tecnico"]),
    ("esportes",     ["corrida", "maratona", "pedal", "ciclismo", "campeonato", "torneio", "esport", "luta", "jiu", "crossfit", "trilha"]),
    ("religiosos",   ["gospel", "louvor", "adoracao", "igreja", "catolic", "evangel", "espirit", "retiro"]),
    ("feiras",       ["feira", "bazar", "brecho", "expo ", "exposicao de produtos"]),
    ("exposicoes",   ["exposicao", "mostra", "museu", "galeria", "vernissage"]),
    ("danca",        ["danca", "ballet", "forrozeada", "zouk", "salsa"]),
    ("literatura",   ["literatura", "livro", "sarau", "poesia", "leitura"]),
    ("tecnologia",   ["tecnologia", "tech", "startup", "programacao", "dev ", "inteligencia artificial", "games", "geek"]),
    ("negocios",     ["negocio", "empreended", "marketing", "vendas", "financas", "investiment", "lideranca"]),
    ("universitarios", ["universitar", "calouros", "atletica", "intercurso"]),
    ("lazer",        ["parque aquatico", "zoologico", "zoo ", "aquario", "passeio", "city tour", "tour ", "experiencia", "arena laser", "laser game", "kart", "escape", "boliche", "termas", "hot park", "balneario"]),
]

# Coleções reais da Sympla (uuid exato das seções da página de cidade) e as
# etiquetas de categoria da Eventbrite -> categorias do app. As coleções de
# teatro/shows/infantil sao a fonte mais confiavel de categoria (o titulo de uma
# peca raramente traz a palavra "teatro").
MAPA_COLECAO = {
    "show-musica-festa": ["shows"],
    "teatro-espetaculo": ["teatro"],
    "infantil": ["infantil"],
    "curso-workshop": ["cursos"],
    "experiencias": ["lazer"],
    "gastronomia": ["gastronomia"],
    "congresso-palestra": ["congressos"],
    "esporte": ["esportes"],
    "religioso": ["religiosos"],
    "Music": ["shows"], "Performing & Visual Arts": ["teatro"], "Food & Drink": ["gastronomia"],
    "Business & Professional": ["negocios"], "Sports & Fitness": ["esportes"],
    "Religion & Spirituality": ["religiosos"], "Family & Education": ["infantil"],
    "Science & Technology": ["tecnologia"], "Community & Culture": ["exposicoes"],
}


def classifica(nome, descricao="", dicas=None):
    texto = " " + normaliza_nome(nome + " " + (descricao or "")) + " "
    achadas = []
    for dica in dicas or []:
        for cat in MAPA_COLECAO.get(dica, []):
            if cat not in achadas:
                achadas.append(cat)
    for cat, chaves in CATEGORIAS:
        if cat in achadas:
            continue
        if any(chave in texto for chave in chaves):
            achadas.append(cat)
    return achadas or ["outros"]


def eh_gratuito(nome, descricao=""):
    texto = normaliza_nome(nome + " " + (descricao or ""))
    return any(p in texto for p in ["gratuito", "gratis", "entrada franca", "entrada livre", "free "])


# ---------------------------------------------------------------- Sympla

def _desescapa_rsc(html):
    pedacos = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(
        p.encode("utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
        for p in pedacos
    )


def extrai_sympla(html):
    """Extrai os arrays "data":[...] do payload RSC, guardando a colecao (uuid) de origem."""
    blob = _desescapa_rsc(html)
    eventos = []
    for m in re.finditer(r'"data":\[\{', blob):
        ini = m.end() - 2
        prof, fim = 0, -1
        for i in range(ini, min(len(blob), ini + 500000)):
            c = blob[i]
            if c == "[":
                prof += 1
            elif c == "]":
                prof -= 1
                if prof == 0:
                    fim = i + 1
                    break
        if fim < 0:
            continue
        trecho_antes = blob[max(0, ini - 600):ini]
        m_uuid = re.findall(r'"uuid":"([a-z0-9-]+)"', trecho_antes)
        colecao = m_uuid[-1] if m_uuid else ""
        try:
            arr = json.loads(blob[ini:fim])
        except json.JSONDecodeError:
            continue
        for ev in arr:
            if isinstance(ev, dict) and "start_date" in ev and "name" in ev:
                ev["_colecao"] = colecao
                eventos.append(ev)
    return eventos


def _parse_data_pt(texto):
    """'Sex, 17 Jul - 2026 · 23:00' -> ('2026-07-17', '23:00')"""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s*-\s*(\d{4})(?:\s*·\s*(\d{2}:\d{2}))?", texto or "")
    if not m:
        return "", ""
    dia, mes_txt, ano, hora = m.groups()
    mes = MESES_PT.get(sem_acento(mes_txt).lower()[:3])
    if not mes:
        return "", ""
    return f"{ano}-{mes:02d}-{int(dia):02d}", hora or ""


def _data_utc_para_local(iso):
    """'2026-07-18T02:00:00+00:00' -> ('2026-07-17','23:00') no fuso de Brasilia."""
    try:
        dt = datetime.fromisoformat(iso).astimezone(FUSO_BRASILIA)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return "", ""


def normaliza_sympla(bruto, cidade_alvo):
    loc = bruto.get("location") or {}
    formatos = bruto.get("start_date_formats") or {}
    data_ini, hora_ini = _parse_data_pt(formatos.get("pt", ""))
    if not data_ini:
        data_ini, hora_ini = _data_utc_para_local(bruto.get("start_date", ""))
    data_fim, hora_fim = _parse_data_pt((bruto.get("end_date_formats") or {}).get("pt", ""))
    if not data_fim:
        data_fim, hora_fim = _data_utc_para_local(bruto.get("end_date", ""))
    nome = (bruto.get("name") or "").strip()
    url = bruto.get("url") or ""
    if not nome or not data_ini or not url:
        return None
    endereco = " ".join(x for x in [loc.get("address"), loc.get("address_num")] if x).strip()
    return {
        "nome": nome,
        "descricao": "",
        "categorias": classifica(nome, dicas=[bruto.get("_colecao", "")]),
        "dataInicio": data_ini,
        "horaInicio": hora_ini,
        "dataFim": data_fim,
        "horaFim": hora_fim,
        "local": (loc.get("name") or "").strip(),
        "endereco": endereco,
        "bairro": (loc.get("neighborhood") or "").strip(),
        "cidade": (loc.get("city") or cidade_alvo["nome"]).strip(),
        "uf": (loc.get("state") or cidade_alvo["uf"]).strip().upper(),
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "gratuito": eh_gratuito(nome),
        "online": False,
        "urlIngresso": url,
        "urlInfo": url,
        "imagem": (bruto.get("images") or {}).get("lg") or "",
        "fonte": "Sympla",
        "fonteUrl": url,
        "tipoFonte": "plataforma",
        "organizador": ((bruto.get("organizer") or {}).get("name") or "").strip(),
    }


def coleta_sympla(cidade, baixador=baixa):
    eventos = []
    for pagina in range(1, PAGINAS_SYMPLA_POR_CIDADE + 1):
        sufixo = f"?page={pagina}" if pagina > 1 else ""
        url = f"https://www.sympla.com.br/eventos/{cidade['slugSympla']}{sufixo}"
        try:
            html = baixador(url)
        except Exception as erro:  # fonte fora do ar nao derruba a coleta
            log(f"  AVISO sympla {cidade['slugSympla']} p{pagina}: {erro}")
            break
        brutos = extrai_sympla(html)
        novos = [n for n in (normaliza_sympla(b, cidade) for b in brutos) if n]
        log(f"  sympla {cidade['slugSympla']} p{pagina}: {len(novos)} eventos")
        eventos.extend(novos)
        if len(brutos) == 0:
            break
        time.sleep(PAUSA_ENTRE_REQUISICOES)
    return eventos


# ---------------------------------------------------------------- Eventbrite

def extrai_eventbrite(html):
    i = html.find("window.__SERVER_DATA__")
    if i < 0:
        return []
    i = html.find("{", i)
    try:
        dados, _ = json.JSONDecoder().raw_decode(html[i:])
        return (dados.get("search_data", {}).get("events", {}) or {}).get("results", []) or []
    except (json.JSONDecodeError, AttributeError):
        return []


def normaliza_eventbrite(bruto, cidade_alvo):
    if bruto.get("is_cancelled"):
        return None
    nome = (bruto.get("name") or "").strip()
    data_ini = bruto.get("start_date") or ""
    url = bruto.get("url") or ""
    if not nome or not data_ini or not url:
        return None
    venue = bruto.get("primary_venue") or {}
    end = venue.get("address") or {}
    etiquetas = [t.get("display_name", "") for t in (bruto.get("tags") or [])]
    resumo = (bruto.get("summary") or "").strip()
    # A busca da Eventbrite devolve eventos de toda a regiao (Santos, Sao Paulo,
    # Sao Jose dos Campos... aparecem na busca de Sao Sebastiao). O endereco do
    # local e a fonte da verdade: so aceitamos o evento se a cidade do local for
    # de fato a cidade pesquisada. Sem isso, carimbariamos falsamente o local.
    cidade_fonte = (end.get("city") or "").strip()
    if not cidade_fonte or normaliza_nome(cidade_fonte) != normaliza_nome(cidade_alvo["nome"]):
        return None
    return {
        "nome": nome,
        "descricao": resumo[:280],
        "categorias": classifica(nome, resumo, dicas=etiquetas),
        "dataInicio": data_ini,
        "horaInicio": (bruto.get("start_time") or "")[:5],
        "dataFim": bruto.get("end_date") or "",
        "horaFim": (bruto.get("end_time") or "")[:5],
        "local": (venue.get("name") or "").strip(),
        "endereco": (end.get("address_1") or "").strip(),
        "bairro": "",
        "cidade": cidade_alvo["nome"],
        "uf": cidade_alvo["uf"],
        "lat": float(end["latitude"]) if end.get("latitude") else None,
        "lon": float(end["longitude"]) if end.get("longitude") else None,
        "gratuito": eh_gratuito(nome, resumo),
        "online": bool(bruto.get("is_online_event")),
        "urlIngresso": bruto.get("tickets_url") or url,
        "urlInfo": url,
        "imagem": ((bruto.get("image") or {}).get("url") or ""),
        "fonte": "Eventbrite",
        "fonteUrl": url,
        "tipoFonte": "plataforma",
        "organizador": "",
    }


def coleta_eventbrite(cidade, baixador=baixa):
    url = f"https://www.eventbrite.com.br/d/brazil--{cidade['slugEventbrite']}/all-events/"
    try:
        html = baixador(url)
    except Exception as erro:
        log(f"  AVISO eventbrite {cidade['slugEventbrite']}: {erro}")
        return []
    brutos = extrai_eventbrite(html)
    novos = [n for n in (normaliza_eventbrite(b, cidade) for b in brutos) if n]
    log(f"  eventbrite {cidade['slugEventbrite']}: {len(novos)} eventos")
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return novos


# ---------------------------------------------------------------- Goiânia Pulsa
# Agenda oficial de turismo de Goiânia. Cobre eventos institucionais e de grande
# porte que nao passam por bilheteria (Centro de Convencoes, Teatro Goiania,
# Centro Cultural Oscar Niemeyer, Bosque dos Buritis, feiras, congressos). Traz
# titulo + data + local + link para a pagina do evento (a fonte que a usuaria
# segue manualmente). Sem hora na listagem -> confiabilidade "incompleta".

GOIANIAPULSA_URL = "https://goianiapulsa.tur.br/eventos/"

# venue -> cidade da regiao metropolitana (padrao Goiania)
_CIDADES_REGIAO = [
    ("aparecida", ("Aparecida de Goiânia", "GO")),
    ("trindade", ("Trindade", "GO")),
    ("anapolis", ("Anápolis", "GO")),
    ("caldas novas", ("Caldas Novas", "GO")),
    ("senador canedo", ("Senador Canedo", "GO")),
]


def _limpa_texto_html(t):
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def extrai_goianiapulsa(html):
    eventos = []
    for m in re.finditer(r'<a href="(https://goianiapulsa\.tur\.br/evento/[^"]+)" class="evento-item.*?</a>', html, re.S):
        bloco, url = m.group(0), m.group(1)
        partes = [_limpa_texto_html(t) for t in re.findall(r">([^<]{2,})<", bloco)]
        partes = [p for p in partes if p]
        data = next((p for p in partes if re.match(r"\d{1,2}/\d{1,2}/\d{4}", p)), "")
        resto = [p for p in partes if p != data]
        titulo = resto[0] if resto else ""
        local = resto[1] if len(resto) > 1 else ""
        if titulo and data:
            eventos.append({"url": url, "data": data, "titulo": titulo, "local": local})
    return eventos


def normaliza_goianiapulsa(bruto):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", bruto["data"])
    if not m:
        return None
    dia, mes, ano = m.groups()
    data_ini = f"{ano}-{int(mes):02d}-{int(dia):02d}"
    nome = bruto["titulo"].strip()
    url = bruto["url"]
    local = re.split(r"\s+[–-]\s+", bruto.get("local", ""))[0].strip()  # tira sufixo apos "– Estande X"
    cidade, uf = "Goiânia", "GO"
    alvo = normaliza_nome(bruto.get("local", ""))
    if "goiania" not in alvo:  # se Goiania aparece no local, ela prevalece
        for chave_reg, (c, u) in _CIDADES_REGIAO:
            if chave_reg in alvo:
                cidade, uf = c, u
                break
    if not nome or not url:
        return None
    return {
        "nome": nome,
        "descricao": "",
        "categorias": classifica(nome),
        "dataInicio": data_ini,
        "horaInicio": "",
        "dataFim": "",
        "horaFim": "",
        "local": local,
        "endereco": "",
        "bairro": "",
        "cidade": cidade,
        "uf": uf,
        "lat": None,
        "lon": None,
        "gratuito": eh_gratuito(nome),
        "online": False,
        "urlIngresso": url,
        "urlInfo": url,
        "imagem": "",
        "fonte": "Goiânia Pulsa",
        "fonteUrl": url,
        "tipoFonte": "institucional",
        "organizador": "",
    }


def coleta_goianiapulsa(baixador=baixa):
    try:
        html = baixador(GOIANIAPULSA_URL)
    except Exception as erro:
        log(f"  AVISO goiania pulsa: {erro}")
        return []
    novos = [n for n in (normaliza_goianiapulsa(b) for b in extrai_goianiapulsa(html)) if n]
    log(f"  goiania pulsa: {len(novos)} eventos")
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return novos


# --------------------------------------------------------------- CCGO
# Centro de Convencoes de Goiania (fonte oficial, prioridade da usuaria).
# Cards do tipo: titulo + "23/10/2026 - Teatro Rio Vermelho" ou "22 a 24/10/2026 - Espaco Cerrado".

CCGO_URL = "https://www.ccgo.com.br/eventos/"


def _parse_intervalo_ddmm(texto):
    """'22 a 24/10/2026' -> ('2026-10-22','2026-10-24'); '23/10/2026' -> (data, '')."""
    m = re.search(r"(\d{1,2})(?:\s*(?:a|e)\s*(\d{1,2}))?/(\d{1,2})/(\d{4})", texto)
    if not m:
        return "", ""
    d1, d2, mes, ano = m.groups()
    ini = f"{ano}-{int(mes):02d}-{int(d1):02d}"
    fim = f"{ano}-{int(mes):02d}-{int(d2):02d}" if d2 else ""
    return ini, fim


def extrai_ccgo(html):
    eventos = []
    blocos = re.findall(r"<div data-ajax-id='\d+' class='[^']*grid-entry.*?(?=<div data-ajax-id='|\Z)", html, re.S)
    for bloco in blocos:
        m_link = re.search(r'href="(https://www\.ccgo\.com\.br/[^"]+)"', bloco)
        textos = [_limpa_texto_html(t) for t in re.findall(r">([^<>]{3,200})<", bloco)]
        textos = [t for t in textos if t]
        i_data = next((i for i, t in enumerate(textos) if re.search(r"\d{1,2}/\d{1,2}/\d{4}", t)), -1)
        if i_data < 0 or not m_link:
            continue
        titulo = " | ".join(textos[:i_data]).strip(" |")
        linha_data = textos[i_data]
        local = linha_data.split(" - ", 1)[1].strip() if " - " in linha_data else ""
        eventos.append({"titulo": titulo, "linhaData": linha_data, "local": local, "url": m_link.group(1)})
    return eventos


def normaliza_ccgo(bruto):
    data_ini, data_fim = _parse_intervalo_ddmm(bruto["linhaData"])
    if not bruto["titulo"] or not data_ini:
        return None
    return {
        "nome": bruto["titulo"],
        "descricao": "",
        "categorias": classifica(bruto["titulo"]),
        "dataInicio": data_ini,
        "horaInicio": "",
        "dataFim": data_fim,
        "horaFim": "",
        "local": ("Centro de Convenções de Goiânia" + (" - " + bruto["local"] if bruto["local"] else "")),
        "endereco": "Rua 4, 1400, Setor Central",
        "bairro": "Setor Central",
        "cidade": "Goiânia",
        "uf": "GO",
        "lat": None, "lon": None,
        "gratuito": eh_gratuito(bruto["titulo"]),
        "online": False,
        "urlIngresso": bruto["url"],
        "urlInfo": bruto["url"],
        "imagem": "",
        "fonte": "Centro de Convenções GO",
        "fonteUrl": bruto["url"],
        "tipoFonte": "oficial",
        "organizador": "",
    }


def coleta_ccgo(baixador=baixa):
    try:
        html = baixador(CCGO_URL)
    except Exception as erro:
        log(f"  AVISO ccgo: {erro}")
        return []
    novos = [n for n in (normaliza_ccgo(b) for b in extrai_ccgo(html)) if n]
    log(f"  centro de convencoes goiania: {len(novos)} eventos")
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return novos


# --------------------------------------------------------------- Ulysses (Brasilia)
# Centro de Convencoes Ulysses Guimaraes: agenda oficial com JSON-LD schema.org/Event.

ULYSSES_URL = "https://ulysses.tur.br/agenda/"


def extrai_ulysses(html):
    eventos = []
    for m in re.finditer(r'<script type=.application/ld\+json.>(.*?)</script>', html, re.S):
        try:
            dados = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in (dados if isinstance(dados, list) else [dados]):
            if isinstance(item, dict) and "Event" in str(item.get("@type", "")):
                eventos.append(item)
    return eventos


def normaliza_ulysses(bruto):
    import html as _html
    nome = _html.unescape((bruto.get("name") or "")).strip()
    ini = (bruto.get("startDate") or "")[:16]
    url = bruto.get("url") or ""
    if not nome or len(ini) < 10 or not url:
        return None
    auditorio = ((bruto.get("location") or {}).get("name") or "").strip()
    return {
        "nome": nome,
        "descricao": _html.unescape((bruto.get("description") or "")).strip()[:280],
        "categorias": classifica(nome),
        "dataInicio": ini[:10],
        "horaInicio": ini[11:16],
        "dataFim": (bruto.get("endDate") or "")[:10],
        "horaFim": (bruto.get("endDate") or "")[11:16],
        "local": ("Centro de Convenções Ulysses Guimarães" + (" - " + auditorio if auditorio else "")),
        "endereco": "SDC Eixo Monumental",
        "bairro": "",
        "cidade": "Brasília",
        "uf": "DF",
        "lat": None, "lon": None,
        "gratuito": eh_gratuito(nome),
        "online": False,
        "urlIngresso": url,
        "urlInfo": url,
        "imagem": bruto.get("image") or "",
        "fonte": "Ulysses Centro de Convenções",
        "fonteUrl": url,
        "tipoFonte": "oficial",
        "organizador": "",
    }


def coleta_ulysses(baixador=baixa):
    try:
        html = baixador(ULYSSES_URL)
    except Exception as erro:
        log(f"  AVISO ulysses: {erro}")
        return []
    novos = [n for n in (normaliza_ulysses(b) for b in extrai_ulysses(html)) if n]
    log(f"  ulysses (brasilia): {len(novos)} eventos")
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return novos


# --------------------------------------------------------------- Shopping Cerrado
# Pagina "Acontece": lista de posts; a data fica no texto do post ("16 de Julho",
# "ate 19 de Julho"). Boa fonte de eventos infantis e gratuitos em Goiania.

CERRADO_URL = "https://shoppingcerrado.com.br/acontece/"
MESES_EXTENSO = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
                 "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def _data_extenso(dia, mes_txt, ano, hoje):
    mes = MESES_EXTENSO.get(sem_acento(mes_txt).lower())
    if not mes:
        return ""
    # Sem ano explicito, assume o ano corrente. NUNCA chuta ano futuro: um post
    # antigo com data passada deve ser filtrado como encerrado, nao virar um
    # "evento" inventado no ano seguinte.
    ano = int(ano) if ano else int(hoje[:4])
    try:
        datetime(int(ano), mes, int(dia))
    except ValueError:
        return ""
    return f"{ano}-{mes:02d}-{int(dia):02d}"


def extrai_datas_texto_pt(texto, hoje):
    """Acha intervalo de datas em texto corrido pt-BR. Devolve (ini, fim) ou ('','')."""
    t = " " + re.sub(r"\s+", " ", texto) + " "
    # "de 16 a 19 de julho( de 2026)?" / "16 a 19 de julho"
    m = re.search(r"(\d{1,2})\s*(?:de\s+[a-zçA-ZÇ]+\s+)?(?:a|à|ate|até)\s*(\d{1,2})\s+de\s+([a-zçA-ZÇ]+)(?:\s+de\s+(\d{4}))?", t)
    if m:
        d1, d2, mes, ano = m.groups()
        ini = _data_extenso(d1, mes, ano, hoje)
        fim = _data_extenso(d2, mes, ano, hoje)
        if ini and fim:
            return ini, fim
    # "ate 19 de julho" -> em cartaz ate la
    m = re.search(r"(?:ate|até)\s+(\d{1,2})\s+de\s+([a-zçA-ZÇ]+)(?:\s+de\s+(\d{4}))?", t, re.I)
    if m:
        fim = _data_extenso(m.group(1), m.group(2), m.group(3), hoje)
        if fim:
            return hoje, fim
    # "dia 19 de julho( de 2026)?" ou primeira data por extenso
    m = re.search(r"(\d{1,2})\s+de\s+([a-zçA-ZÇ]+)(?:\s+de\s+(\d{4}))?", t)
    if m:
        ini = _data_extenso(m.group(1), m.group(2), m.group(3), hoje)
        if ini:
            return ini, ""
    return "", ""


def coleta_cerrado(baixador=baixa, hoje=None):
    hoje = hoje or datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")
    try:
        listagem = baixador(CERRADO_URL)
    except Exception as erro:
        log(f"  AVISO shopping cerrado: {erro}")
        return []
    urls = []
    for u in re.findall(r'href="(https://shoppingcerrado\.com\.br/acontece/[^"]{5,})"', listagem):
        if u.rstrip("/") != CERRADO_URL.rstrip("/") and u not in urls:
            urls.append(u)
    eventos = []
    for u in urls[:15]:  # limite de cortesia
        try:
            pagina = baixador(u)
        except Exception:
            continue
        m_t = re.search(r"<h1[^>]*>(.*?)</h1>", pagina, re.S) or re.search(r"<title>(.*?)</title>", pagina, re.S)
        titulo = _limpa_texto_html(m_t.group(1)) if m_t else ""
        titulo = re.split(r"\s+[–|-]\s+", titulo)[0]  # tira sufixo "– Cerrado – O shopping..."
        titulo = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]+", "", titulo).strip()  # tira emojis
        sem_estilos = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", pagina, flags=re.S)
        corpo = re.sub(r"<[^>]+>", " ", sem_estilos)
        ini, fim = extrai_datas_texto_pt(corpo, hoje)
        if not titulo or not ini:
            continue  # sem data confiavel, nao inventa
        eventos.append({
            "nome": titulo,
            "descricao": "",
            "categorias": classifica(titulo),
            "dataInicio": ini,
            "horaInicio": "",
            "dataFim": fim,
            "horaFim": "",
            "local": "Shopping Cerrado",
            "endereco": "Av. Anhanguera, 10790",
            "bairro": "Setor Aeroviário",
            "cidade": "Goiânia",
            "uf": "GO",
            "lat": None, "lon": None,
            "gratuito": eh_gratuito(titulo, corpo[:8000]),
            "online": False,
            "urlIngresso": u,
            "urlInfo": u,
            "imagem": "",
            "fonte": "Shopping Cerrado",
            "fonteUrl": u,
            "tipoFonte": "oficial",
            "organizador": "",
        })
        time.sleep(PAUSA_ENTRE_REQUISICOES)
    log(f"  shopping cerrado: {len(eventos)} eventos")
    return eventos


# --------------------------------------------------- pos-processamento comum

def confianca_de(ev):
    if not ev["local"]:
        return "incompleta"
    if ev["tipoFonte"] == "oficial":
        # confirmado no site oficial do local/organizador (hora pode faltar,
        # mas a existencia do evento esta confirmada na origem)
        return "oficial"
    if not ev["horaInicio"]:
        return "incompleta"
    return "plataforma"


def remove_duplicados(eventos):
    """Mesmo nome normalizado + mesma data + mesma cidade = mesmo evento.
    Mantem o registro mais completo e anexa a outra fonte como link adicional."""
    por_chave = {}
    for ev in eventos:
        chave = (normaliza_nome(ev["nome"]), ev["dataInicio"], normaliza_nome(ev["cidade"]))
        chave_url = ev["urlInfo"].split("?")[0]
        existente = por_chave.get(chave)
        if existente is None:
            ja = next((e for e in por_chave.values() if e["urlInfo"].split("?")[0] == chave_url), None)
            if ja is None:
                por_chave[chave] = ev
                continue
            existente = ja
        campos = ["horaInicio", "local", "endereco", "descricao"]
        completo = sum(1 for c in campos if ev[c])
        completo_ex = sum(1 for c in campos if existente[c])
        principal, extra = (ev, existente) if completo > completo_ex else (existente, ev)
        # Une categorias das copias: o mesmo evento aparece em varias colecoes da
        # Sympla (teatro-espetaculo, em-alta, hoje...); sem unir, a categoria boa
        # se perde quando a copia vencedora veio de uma colecao generica.
        principal["categorias"] = uniao_categorias(principal["categorias"], extra["categorias"])
        if extra["fonte"] != principal["fonte"]:
            fontes_extras = principal.setdefault("fontesAdicionais", [])
            if not any(f["url"] == extra["fonteUrl"] for f in fontes_extras):
                fontes_extras.append({"nome": extra["fonte"], "url": extra["fonteUrl"]})
        if principal is not existente:
            por_chave[chave] = principal
    return list(por_chave.values())


def uniao_categorias(a, b):
    """Junta duas listas de categorias; descarta 'outros' se houver categoria real."""
    juntas = []
    for c in list(a) + list(b):
        if c not in juntas:
            juntas.append(c)
    reais = [c for c in juntas if c != "outros"]
    return reais or ["outros"]


def remove_passados_e_distantes(eventos, hoje=None):
    hoje = hoje or datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")
    limite = (datetime.strptime(hoje, "%Y-%m-%d") + timedelta(days=MAX_DIAS_FUTURO)).strftime("%Y-%m-%d")
    validos = []
    for ev in eventos:
        fim = ev["dataFim"] or ev["dataInicio"]
        if fim < hoje:  # ja terminou
            continue
        if ev["dataInicio"] > limite:  # longe demais
            continue
        validos.append(ev)
    return validos


def executa(cidades, baixador=baixa, agora=None):
    agora = agora or datetime.now(FUSO_BRASILIA)
    todos = []
    for cidade in cidades:
        log(f"cidade: {cidade['nome']}/{cidade['uf']}")
        todos.extend(coleta_sympla(cidade, baixador))
        todos.extend(coleta_eventbrite(cidade, baixador))
    # Fontes oficiais/institucionais por regiao (eventos que nao passam por bilheteria)
    monitora = {normaliza_nome(c["nome"]) for c in cidades}
    monitora_goiania = "goiania" in monitora
    monitora_brasilia = "brasilia" in monitora
    if monitora_goiania:
        log("fontes locais de Goiânia: Goiânia Pulsa, CCGO, Shopping Cerrado")
        todos.extend(coleta_goianiapulsa(baixador))
        todos.extend(coleta_ccgo(baixador))
        todos.extend(coleta_cerrado(baixador))
    if monitora_brasilia:
        log("fontes locais de Brasília: Ulysses")
        todos.extend(coleta_ulysses(baixador))
    antes = len(todos)
    todos = remove_duplicados(todos)
    duplicados = antes - len(todos)
    todos = remove_passados_e_distantes(todos, agora.strftime("%Y-%m-%d"))
    for i, ev in enumerate(todos):
        ev["id"] = f"ev{i:05d}"
        ev["confianca"] = confianca_de(ev)
        ev["coletadoEm"] = agora.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    todos.sort(key=lambda e: (e["dataInicio"], e["horaInicio"] or "99"))
    log(f"total: {len(todos)} eventos ({duplicados} duplicados removidos)")
    return {
        "geradoEm": agora.strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "cidades": [{"nome": c["nome"], "uf": c["uf"]} for c in cidades],
        "fontes": [
            {"nome": "Sympla", "url": "https://www.sympla.com.br"},
            {"nome": "Eventbrite", "url": "https://www.eventbrite.com.br"},
        ] + ([
            {"nome": "Goiânia Pulsa", "url": "https://goianiapulsa.tur.br"},
            {"nome": "Centro de Convenções GO", "url": "https://www.ccgo.com.br/eventos/"},
            {"nome": "Shopping Cerrado", "url": "https://shoppingcerrado.com.br/acontece/"},
        ] if monitora_goiania else []) + ([
            {"nome": "Ulysses Centro de Convenções", "url": "https://ulysses.tur.br/agenda/"},
        ] if monitora_brasilia else []),
        "duplicadosRemovidos": duplicados,
        "eventos": todos,
    }


def grava_dados_js(dados, caminho):
    conteudo = "window.EVENTOS_DATA = " + json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + ";\n"
    Path(caminho).write_text(conteudo, encoding="utf-8")
    log(f"gravado {caminho} ({len(conteudo) // 1024} KB)")


def principal():
    cidades = json.loads((RAIZ / "dados" / "cidades_monitoradas.json").read_text(encoding="utf-8"))
    dados = executa(cidades)
    if len(dados["eventos"]) < 10:
        log("ERRO: menos de 10 eventos coletados; mantendo dados.js anterior para nao publicar arquivo vazio.")
        sys.exit(1)
    grava_dados_js(dados, RAIZ / "docs" / "dados.js")


if __name__ == "__main__":
    principal()
