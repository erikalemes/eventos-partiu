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
]

MAPA_COLECAO = {
    "show-musica-festa": ["shows"],
    "teatro": ["teatro"],
    "infantil": ["infantil"],
    "gastronomia": ["gastronomia"],
    "curso-workshop": ["cursos"],
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
    # Eventbrite as vezes poe o bairro no campo cidade; fixa a cidade pesquisada.
    cidade_fonte = (end.get("city") or "").strip()
    bairro = ""
    if cidade_fonte and normaliza_nome(cidade_fonte) != normaliza_nome(cidade_alvo["nome"]):
        bairro = cidade_fonte
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
        "bairro": bairro,
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


# --------------------------------------------------- pos-processamento comum

def confianca_de(ev):
    if not ev["horaInicio"] or not ev["local"]:
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
        if extra["fonte"] != principal["fonte"]:
            fontes_extras = principal.setdefault("fontesAdicionais", [])
            if not any(f["url"] == extra["fonteUrl"] for f in fontes_extras):
                fontes_extras.append({"nome": extra["fonte"], "url": extra["fonteUrl"]})
        if principal is not existente:
            por_chave[chave] = principal
    return list(por_chave.values())


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
        ],
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
