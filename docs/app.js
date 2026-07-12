/* Eventos - Partiu?! — logica do aplicativo (roda 100% no navegador).
   Dados: window.EVENTOS_DATA (gerado pelo robo scripts/coletar.py)
          window.CIDADES_BR  (municipios do IBGE, para autocomplete/CEP)
   Interpretacao da consulta: baseada em regras (sem chave de IA), conforme
   documentado no README. Nada e inventado: todo evento tem fonte e link. */
(function () {
  "use strict";

  var DADOS = window.EVENTOS_DATA || { eventos: [], cidades: [], fontes: [], geradoEm: "" };
  var CIDADES_BR = window.CIDADES_BR || [];

  var DIAS_SEMANA = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
  var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

  var CATEGORIAS_APP = [
    ["shows", "Shows e música"], ["teatro", "Teatro"], ["stand-up", "Stand-up"],
    ["festas", "Festas e festivais"], ["gastronomia", "Gastronomia"], ["infantil", "Infantil"],
    ["cursos", "Cursos e oficinas"], ["congressos", "Congressos e palestras"],
    ["esportes", "Esportes"], ["feiras", "Feiras"], ["exposicoes", "Exposições e mostras"],
    ["danca", "Dança"], ["religiosos", "Religiosos"], ["literatura", "Literatura"],
    ["tecnologia", "Tecnologia"], ["negocios", "Negócios"], ["universitarios", "Universitários"],
    ["outros", "Outros"]
  ];
  var ROTULO_CATEGORIA = {};
  CATEGORIAS_APP.forEach(function (par) { ROTULO_CATEGORIA[par[0]] = par[1]; });

  // Palavras da consulta livre -> categorias
  var PALAVRAS_CATEGORIA = {
    shows: ["show", "shows", "musica", "banda", "cantor", "cantora", "sertanejo", "pagode", "samba", "rock", "mpb", "forro", "eletronica"],
    teatro: ["teatro", "peca", "espetaculo", "musical"],
    "stand-up": ["stand", "standup", "humor", "comedia"],
    festas: ["festa", "festas", "balada", "festival", "arraia"],
    gastronomia: ["gastronomia", "gastronomico", "gastronomicos", "comida", "cerveja", "vinho", "boteco", "restaurante"],
    infantil: ["infantil", "infantis", "crianca", "criancas", "kids", "familia"],
    cursos: ["curso", "cursos", "oficina", "oficinas", "workshop", "aula"],
    congressos: ["congresso", "congressos", "palestra", "palestras", "seminario", "simposio"],
    esportes: ["esporte", "esportivo", "esportivos", "corrida", "campeonato", "torneio", "pedal"],
    feiras: ["feira", "feiras", "bazar", "brecho"],
    exposicoes: ["exposicao", "exposicoes", "mostra", "mostras", "museu", "galeria"],
    danca: ["danca", "ballet", "forrozeada"],
    religiosos: ["religioso", "religiosos", "gospel", "louvor", "igreja"],
    literatura: ["literatura", "livro", "livros", "sarau", "poesia"],
    tecnologia: ["tecnologia", "tech", "startup", "programacao", "games", "geek"],
    negocios: ["negocio", "negocios", "empreendedorismo", "marketing", "vendas"],
    universitarios: ["universitario", "universitarios", "atletica", "calouros"]
  };

  // ------------------------------------------------------------- utilidades

  function $(id) { return document.getElementById(id); }

  function semAcento(t) {
    return (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }
  function chave(t) {
    return semAcento(t).toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  }
  function escapaHtml(t) {
    return String(t || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function urlSegura(u) {
    // So aceita http(s) absoluto; qualquer outra coisa vira vazio.
    return /^https?:\/\//i.test(u || "") ? u : "";
  }
  function dataISO(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function deISO(iso) {
    var p = iso.split("-");
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
  }
  function somaDias(iso, n) {
    var d = deISO(iso); d.setDate(d.getDate() + n); return dataISO(d);
  }
  function formataDataLonga(iso) {
    var d = deISO(iso);
    return DIAS_SEMANA[d.getDay()] + ", " + d.getDate() + " de " + MESES[d.getMonth()] +
      (d.getFullYear() !== new Date().getFullYear() ? " de " + d.getFullYear() : "");
  }
  function formataDataCurta(iso) {
    var p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
  }

  var HOJE = dataISO(new Date());

  // Conjunto de cidades que possuem eventos na base
  var CIDADES_COM_EVENTOS = {};
  DADOS.eventos.forEach(function (ev) {
    CIDADES_COM_EVENTOS[chave(ev.cidade) + "|" + ev.uf] = ev.cidade + "|" + ev.uf;
  });
  var CIDADES_MONITORADAS = (DADOS.cidades || []).map(function (c) { return c.nome + "/" + c.uf; });

  // -------------------------------------------------- interpretacao de datas

  function proximoDiaSemana(aPartirDe, diaAlvo, pulaHoje) {
    var d = deISO(aPartirDe);
    for (var i = pulaHoje ? 1 : 0; i <= 7; i++) {
      var c = new Date(d); c.setDate(d.getDate() + i);
      if (c.getDay() === diaAlvo) return dataISO(c);
    }
    return aPartirDe;
  }

  function intervaloDoPeriodo(codigo, hoje) {
    hoje = hoje || HOJE;
    var d = deISO(hoje), dia = d.getDay();
    switch (codigo) {
      case "hoje": return [hoje, hoje, "hoje"];
      case "amanha": return [somaDias(hoje, 1), somaDias(hoje, 1), "amanhã"];
      case "depois-amanha": return [somaDias(hoje, 2), somaDias(hoje, 2), "depois de amanhã"];
      case "fds": {
        // fim de semana corrente: sexta a domingo (se hoje for domingo, so hoje)
        var sexta = dia <= 5 ? somaDias(hoje, 5 - dia) : hoje;
        var domingo = somaDias(hoje, (7 - dia) % 7);
        if (dia === 0) { sexta = hoje; domingo = hoje; }
        return [sexta < hoje ? hoje : sexta, domingo, "este fim de semana"];
      }
      case "prox-fds": {
        var proxSab = proximoDiaSemana(somaDias(hoje, (7 - dia) % 7 + 1), 6, false);
        return [somaDias(proxSab, -1), somaDias(proxSab, 1), "próximo fim de semana"];
      }
      case "semana": return [hoje, somaDias(hoje, (7 - dia) % 7), "esta semana"];
      case "prox-semana": {
        var proxSeg = somaDias(hoje, ((8 - dia) % 7) || 7);
        return [proxSeg, somaDias(proxSeg, 6), "próxima semana"];
      }
      case "mes": {
        var fimMes = new Date(d.getFullYear(), d.getMonth() + 1, 0);
        return [hoje, dataISO(fimMes), "este mês"];
      }
      case "prox-mes": {
        var ini = new Date(d.getFullYear(), d.getMonth() + 1, 1);
        var fim = new Date(d.getFullYear(), d.getMonth() + 2, 0);
        return [dataISO(ini), dataISO(fim), "próximo mês"];
      }
      default: return null;
    }
  }

  function interpretaDatasDoTexto(texto, hoje) {
    hoje = hoje || HOJE;
    var t = " " + chave(texto) + " ";
    function acha(re) { return re.test(t); }

    if (acha(/ depois de amanha /)) return intervaloDoPeriodo("depois-amanha", hoje);
    if (acha(/ amanha /)) return intervaloDoPeriodo("amanha", hoje);
    if (acha(/ hoje | esta noite | hoje a noite /)) return intervaloDoPeriodo("hoje", hoje);
    if (acha(/ proximo (fim de semana|fds) | proxima (fim de semana)? ?fds /)) return intervaloDoPeriodo("prox-fds", hoje);
    if (acha(/ (neste|nesse|no|este|esse) (fim de semana|fds) | fim de semana | fds /)) return intervaloDoPeriodo("fds", hoje);
    if (acha(/ proxima semana /)) return intervaloDoPeriodo("prox-semana", hoje);
    if (acha(/ (esta|essa|nesta|nessa) semana /)) return intervaloDoPeriodo("semana", hoje);
    if (acha(/ proximo mes /)) return intervaloDoPeriodo("prox-mes", hoje);
    if (acha(/ (este|esse|neste|nesse) mes /)) return intervaloDoPeriodo("mes", hoje);

    // dias da semana: "no sabado", "proximo domingo", "sexta"
    var nomesDia = [["domingo", 0], ["segunda", 1], ["terca", 2], ["quarta", 3], ["quinta", 4], ["sexta", 5], ["sabado", 6]];
    for (var i = 0; i < nomesDia.length; i++) {
      var re = new RegExp(" (no |na |neste |nesta |proximo |proxima |)" + nomesDia[i][0] + "( feira)? ");
      var m = t.match(re);
      if (m) {
        var pulaHoje = /proxim/.test(m[1] || "");
        var dia = proximoDiaSemana(hoje, nomesDia[i][1], pulaHoje);
        if (pulaHoje && dia === hoje) dia = somaDias(dia, 7);
        var rotulo = (pulaHoje ? "próximo " : "") + nomesDia[i][0];
        return [dia, dia, rotulo];
      }
    }

    // data explicita dd/mm ou dd/mm/aaaa
    var md = t.match(/ (\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))? /);
    if (md) {
      var ano = md[3] ? (md[3].length === 2 ? "20" + md[3] : md[3]) : hoje.slice(0, 4);
      var iso = ano + "-" + md[2].padStart(2, "0") + "-" + md[1].padStart(2, "0");
      if (!md[3] && iso < hoje) iso = (Number(ano) + 1) + iso.slice(4);
      return [iso, iso, "dia " + formataDataCurta(iso)];
    }
    return null;
  }

  // ------------------------------------------- interpretacao da consulta livre

  function detectaCidadeNoTexto(texto) {
    var t = " " + chave(texto) + " ";
    var achada = null;
    // procura "em <cidade>" / "de <cidade>" contra municipios do IBGE (nomes mais longos primeiro)
    for (var i = 0; i < CIDADES_BR.length; i++) {
      var nome = CIDADES_BR[i][0], uf = CIDADES_BR[i][1];
      var c = chave(nome);
      if (c.length < 4) continue; // evita falsos positivos com nomes muito curtos
      if (t.indexOf(" em " + c + " ") >= 0 || t.indexOf(" de " + c + " ") >= 0 || t.indexOf(" na cidade de " + c + " ") >= 0) {
        if (!achada || c.length > chave(achada.nome).length) achada = { nome: nome, uf: uf };
      }
    }
    return achada;
  }

  function interpretaConsulta(texto, hoje) {
    var criterios = {
      texto: (texto || "").slice(0, 200),
      categorias: [],
      gratuito: false,
      periodoDia: null,
      intervalo: null,
      cidade: null,
      avisoPreco: false,
      termosLivres: []
    };
    if (!texto) return criterios;
    var t = " " + chave(texto) + " ";

    criterios.intervalo = interpretaDatasDoTexto(texto, hoje);

    if (/ (gratuito|gratuitos|gratuita|gratuitas|gratis|de graca|sem pagar) /.test(t)) criterios.gratuito = true;
    if (/ (a noite|de noite|noturno|noturnos) /.test(t)) criterios.periodoDia = "noite";
    else if (/ (a tarde|de tarde) /.test(t)) criterios.periodoDia = "tarde";
    else if (/ (de manha|pela manha|matinal) /.test(t)) criterios.periodoDia = "manha";

    // preco maximo ("ate R$ 100"): a base nao tem precos, entao vira aviso honesto
    if (/ (ate|por ate|maximo|max) (r ?)?\d+ /.test(t) || / r \d+ /.test(t)) criterios.avisoPreco = true;

    Object.keys(PALAVRAS_CATEGORIA).forEach(function (cat) {
      if (PALAVRAS_CATEGORIA[cat].some(function (p) { return t.indexOf(" " + p + " ") >= 0; })) {
        criterios.categorias.push(cat);
      }
    });
    // "casal" e "familia" nao viram categoria rigida; entram como termos de relevancia
    criterios.cidade = detectaCidadeNoTexto(texto);

    // termos livres para relevancia/local especifico (ignora palavras vazias)
    var VAZIAS = ["o", "a", "os", "as", "que", "tem", "para", "pra", "fazer", "quero", "quais", "qual", "eventos", "evento",
      "em", "de", "do", "da", "no", "na", "um", "uma", "e", "ou", "com", "por", "ate", "neste", "nesta", "este", "esta",
      "hoje", "amanha", "fim", "semana", "mes", "proximo", "proxima", "sabado", "domingo", "segunda", "terca", "quarta",
      "quinta", "sexta", "feira", "noite", "tarde", "manha", "gratuito", "gratuitos", "gratis", "acontecem", "acontecendo",
      "existem", "havera", "esta", "estao", "algo", "r"];
    var tokensCidade = criterios.cidade ? chave(criterios.cidade.nome).split(" ") : [];
    criterios.termosLivres = chave(texto).split(" ").filter(function (p) {
      return p.length >= 3 && VAZIAS.indexOf(p) < 0 && tokensCidade.indexOf(p) < 0 && !/^\d+$/.test(p);
    });
    return criterios;
  }

  // ------------------------------------------------------------ filtragem

  function horaDoPeriodo(hora, periodo) {
    if (!periodo || periodo === "any") return true;
    if (!hora) return false;
    var h = Number(hora.slice(0, 2));
    if (periodo === "manha") return h < 12;
    if (periodo === "tarde") return h >= 12 && h < 18;
    return h >= 18 || h < 5; // noite (inclui madrugada)
  }

  function eventoNoIntervalo(ev, ini, fim) {
    var evIni = ev.dataInicio, evFim = ev.dataFim || ev.dataInicio;
    return evIni <= fim && evFim >= ini;
  }

  function pontuaRelevancia(ev, criterios) {
    var pontos = 0;
    var textoEv = chave(ev.nome + " " + ev.local + " " + ev.bairro + " " + (ev.descricao || ""));
    criterios.termosLivres.forEach(function (termo) {
      if (textoEv.indexOf(termo) >= 0) pontos += 10;
    });
    criterios.categorias.forEach(function (cat) {
      if (ev.categorias.indexOf(cat) >= 0) pontos += 6;
    });
    if (criterios.gratuito && ev.gratuito) pontos += 4;
    if (ev.horaInicio && ev.local) pontos += 1; // completude
    return pontos;
  }

  function filtraEventos(criterios) {
    var lista = DADOS.eventos.filter(function (ev) {
      if (criterios.cidadeSelecionada &&
        chave(ev.cidade) + "|" + ev.uf !== chave(criterios.cidadeSelecionada.nome) + "|" + criterios.cidadeSelecionada.uf) return false;
      var fimEv = ev.dataFim || ev.dataInicio;
      if (fimEv < HOJE) return false; // nunca mostra evento encerrado
      if (criterios.intervalo && !eventoNoIntervalo(ev, criterios.intervalo[0], criterios.intervalo[1])) return false;
      if (criterios.gratuito && !ev.gratuito) return false;
      if (criterios.presencial && ev.online) return false;
      if (criterios.periodoDia && !horaDoPeriodo(ev.horaInicio, criterios.periodoDia)) return false;
      if (criterios.categorias.length &&
        !criterios.categorias.some(function (c) { return ev.categorias.indexOf(c) >= 0; })) return false;
      return true;
    });
    // com termos livres, exige ao menos 1 termo presente OU categoria detectada ja filtrou
    if (criterios.termosLivres.length && !criterios.categorias.length) {
      var comTermo = lista.filter(function (ev) { return pontuaRelevancia(ev, criterios) >= 10; });
      if (comTermo.length) lista = comTermo;
    }
    return lista;
  }

  function ordenaEventos(lista, modo, criterios) {
    var copia = lista.slice();
    if (modo === "relevancia") {
      copia.sort(function (a, b) {
        var d = pontuaRelevancia(b, criterios) - pontuaRelevancia(a, criterios);
        return d !== 0 ? d : (a.dataInicio + (a.horaInicio || "99")).localeCompare(b.dataInicio + (b.horaInicio || "99"));
      });
    } else if (modo === "gratuitos") {
      copia.sort(function (a, b) {
        if (a.gratuito !== b.gratuito) return a.gratuito ? -1 : 1;
        return (a.dataInicio + (a.horaInicio || "99")).localeCompare(b.dataInicio + (b.horaInicio || "99"));
      });
    } else {
      copia.sort(function (a, b) {
        return (a.dataInicio + (a.horaInicio || "99")).localeCompare(b.dataInicio + (b.horaInicio || "99"));
      });
    }
    return copia;
  }

  // ------------------------------------------------------------- interface

  var estado = {
    cidade: null,          // {nome, uf}
    ultimaConsulta: null,  // criterios da ultima pesquisa
    ultimaLista: []
  };

  function cidadesMonitoradasTexto() {
    return CIDADES_MONITORADAS.join(", ");
  }

  function defineCidade(nome, uf, origem) {
    estado.cidade = { nome: nome, uf: uf };
    $("campo-cidade").value = nome + "/" + uf;
    try { localStorage.setItem("partiu_cidade", JSON.stringify(estado.cidade)); } catch (e) { /* privado */ }
    var monitorada = CIDADES_COM_EVENTOS[chave(nome) + "|" + uf];
    var ajuda = $("ajuda-cidade");
    if (monitorada) {
      ajuda.textContent = origem === "cep" ? "CEP localizado em " + nome + "/" + uf + "." : "";
      ajuda.classList.remove("erro");
    } else {
      ajuda.textContent = nome + "/" + uf + " ainda não é monitorada. Cidades disponíveis: " + cidadesMonitoradasTexto() + ".";
      ajuda.classList.add("erro");
    }
  }

  // ---- autocomplete de cidade
  function montaAutocomplete() {
    var campo = $("campo-cidade"), lista = $("lista-cidades");
    var opcoes = [], indiceAtivo = -1;

    function fecha() { lista.hidden = true; lista.innerHTML = ""; opcoes = []; indiceAtivo = -1; }

    function abre(termo) {
      var t = chave(termo);
      if (t.length < 2) { fecha(); return; }
      var monitoradas = [], demais = [];
      for (var i = 0; i < CIDADES_BR.length && (monitoradas.length + demais.length) < 200; i++) {
        var nome = CIDADES_BR[i][0], uf = CIDADES_BR[i][1];
        if (chave(nome).indexOf(t) === 0) {
          (CIDADES_COM_EVENTOS[chave(nome) + "|" + uf] ? monitoradas : demais).push([nome, uf]);
        }
      }
      opcoes = monitoradas.concat(demais).slice(0, 12);
      if (!opcoes.length) { fecha(); return; }
      lista.innerHTML = opcoes.map(function (par, i) {
        var mon = CIDADES_COM_EVENTOS[chave(par[0]) + "|" + par[1]];
        return '<button type="button" role="option" data-i="' + i + '" class="' + (mon ? "" : "nao-monitorada") + '">' +
          escapaHtml(par[0]) + "/" + par[1] +
          (mon ? '<span class="etiqueta-monitorada">com eventos</span>' : "") + "</button>";
      }).join("");
      lista.hidden = false;
      indiceAtivo = -1;
    }

    function escolhe(i) {
      if (i < 0 || i >= opcoes.length) return;
      defineCidade(opcoes[i][0], opcoes[i][1], "manual");
      fecha();
    }

    campo.addEventListener("input", function () { abre(campo.value); });
    campo.addEventListener("keydown", function (e) {
      if (lista.hidden) return;
      var botoes = lista.querySelectorAll("button");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        indiceAtivo = e.key === "ArrowDown" ? Math.min(indiceAtivo + 1, botoes.length - 1) : Math.max(indiceAtivo - 1, 0);
        botoes.forEach(function (b, i) { b.setAttribute("aria-selected", i === indiceAtivo ? "true" : "false"); });
        botoes[indiceAtivo].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter" && indiceAtivo >= 0) {
        e.preventDefault(); escolhe(indiceAtivo);
      } else if (e.key === "Escape") { fecha(); }
    });
    lista.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (b) escolhe(Number(b.dataset.i));
    });
    document.addEventListener("click", function (e) {
      if (!lista.hidden && !lista.contains(e.target) && e.target !== campo) fecha();
    });
  }

  // ---- CEP via ViaCEP (unica chamada externa do app; falha vira mensagem clara)
  function montaCep() {
    var campo = $("campo-cep"), ajuda = $("ajuda-cep");
    campo.addEventListener("input", function () {
      var digitos = campo.value.replace(/\D/g, "").slice(0, 8);
      campo.value = digitos.length > 5 ? digitos.slice(0, 5) + "-" + digitos.slice(5) : digitos;
      ajuda.textContent = ""; ajuda.classList.remove("erro");
      if (digitos.length !== 8) return;
      ajuda.textContent = "Consultando CEP...";
      fetch("https://viacep.com.br/ws/" + digitos + "/json/")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.erro || !d.localidade) {
            ajuda.textContent = "CEP não encontrado."; ajuda.classList.add("erro"); return;
          }
          ajuda.textContent = "";
          defineCidade(d.localidade, d.uf, "cep");
        })
        .catch(function () {
          ajuda.textContent = "Não foi possível consultar o CEP agora."; ajuda.classList.add("erro");
        });
    });
  }

  // ---- chips de categorias
  function montaCategorias() {
    $("chips-categorias").innerHTML = CATEGORIAS_APP.map(function (par) {
      return '<label><input type="checkbox" value="' + par[0] + '"> ' + escapaHtml(par[1]) + "</label>";
    }).join("");
  }

  function categoriasMarcadas() {
    return Array.prototype.slice.call(document.querySelectorAll("#chips-categorias input:checked"))
      .map(function (i) { return i.value; });
  }

  // ---- montagem dos criterios ao pesquisar (texto livre + filtros combinados)
  function montaCriterios() {
    var texto = $("campo-consulta").value.trim();
    var criterios = interpretaConsulta(texto, HOJE);

    // cidade: a citada no texto vence a selecionada
    if (criterios.cidade) {
      defineCidade(criterios.cidade.nome, criterios.cidade.uf, "texto");
    }
    criterios.cidadeSelecionada = estado.cidade;

    // filtros estruturados complementam (texto vence quando ambos existem)
    var periodoSel = $("filtro-periodo").value;
    if (!criterios.intervalo) {
      if (periodoSel === "datas") {
        var ini = $("filtro-data-ini").value, fim = $("filtro-data-fim").value;
        if (ini || fim) {
          ini = ini || HOJE; fim = fim || ini;
          if (fim < ini) { var tmp = ini; ini = fim; fim = tmp; }
          criterios.intervalo = [ini, fim, "de " + formataDataCurta(ini) + " a " + formataDataCurta(fim)];
        }
      } else if (periodoSel !== "tudo") {
        criterios.intervalo = intervaloDoPeriodo(periodoSel, HOJE);
      }
    }
    if (!criterios.periodoDia) {
      var h = $("filtro-horario").value;
      if (h !== "any") criterios.periodoDia = h;
    }
    categoriasMarcadas().forEach(function (c) {
      if (criterios.categorias.indexOf(c) < 0) criterios.categorias.push(c);
    });
    if ($("filtro-gratuito").checked) criterios.gratuito = true;
    criterios.presencial = $("filtro-presencial").checked;
    return criterios;
  }

  // ------------------------------------------------------------- cartoes

  function cartaoEvento(ev) {
    var urlIngresso = urlSegura(ev.urlIngresso), urlInfo = urlSegura(ev.urlInfo), urlFonte = urlSegura(ev.fonteUrl);
    var ehInscricao = ev.categorias.indexOf("cursos") >= 0 || ev.categorias.indexOf("congressos") >= 0;
    var rotuloBotao = ev.gratuito ? "Inscrição" : (ehInscricao ? "Inscrição" : "Ingressos");
    var etiquetas = "";
    if (ev.gratuito) etiquetas += '<span class="etiqueta gratuito">Gratuito</span>';
    if (ev.online) etiquetas += '<span class="etiqueta online">On-line</span>';
    ev.categorias.slice(0, 3).forEach(function (c) {
      etiquetas += '<span class="etiqueta">' + escapaHtml(ROTULO_CATEGORIA[c] || c) + "</span>";
    });
    etiquetas += ev.confianca === "incompleta"
      ? '<span class="etiqueta confianca-incompleta" title="Faltam dados como horário ou local; confirme no link da fonte.">Informação incompleta</span>'
      : '<span class="etiqueta confianca-plataforma" title="Evento encontrado em plataforma de ingressos reconhecida.">Plataforma confiável</span>';

    var quando = formataDataCurta(ev.dataInicio) + (ev.horaInicio ? " às " + ev.horaInicio : "");
    if (ev.dataFim && ev.dataFim !== ev.dataInicio) quando += " até " + formataDataCurta(ev.dataFim);

    var onde = [ev.local, ev.bairro, ev.cidade + "/" + ev.uf].filter(Boolean).join(" · ");
    var fontesExtras = (ev.fontesAdicionais || []).map(function (f) {
      var u = urlSegura(f.url);
      return u ? ' · também em <a href="' + escapaHtml(u) + '" target="_blank" rel="noopener noreferrer">' + escapaHtml(f.nome) + "</a>" : "";
    }).join("");

    return '<article class="cartao-evento">' +
      (urlSegura(ev.imagem) ? '<img class="foto" loading="lazy" src="' + escapaHtml(ev.imagem) + '" alt="">' : "") +
      '<div class="corpo">' +
      "<h4>" + escapaHtml(ev.nome) + "</h4>" +
      '<p class="linha-info"><strong>' + escapaHtml(quando) + "</strong></p>" +
      '<p class="linha-info">' + escapaHtml(onde) + "</p>" +
      (ev.endereco ? '<p class="linha-info">' + escapaHtml(ev.endereco) + "</p>" : "") +
      '<div class="etiquetas">' + etiquetas + "</div>" +
      (ev.descricao ? '<p class="descricao">' + escapaHtml(ev.descricao) + "</p>" : "") +
      '<p class="linha-info">Preço: ' + (ev.gratuito ? "gratuito (segundo a fonte)" : "consulte no site oficial") + "</p>" +
      '<div class="acoes-cartao">' +
      (urlIngresso ? '<a class="acao-ingresso" href="' + escapaHtml(urlIngresso) + '" target="_blank" rel="noopener noreferrer">' + rotuloBotao + "</a>" : "") +
      (urlInfo ? '<a class="acao-info" href="' + escapaHtml(urlInfo) + '" target="_blank" rel="noopener noreferrer">Mais informações</a>' : "") +
      "</div>" +
      '<p class="fonte-cartao">Fonte: <a href="' + escapaHtml(urlFonte) + '" target="_blank" rel="noopener noreferrer">' + escapaHtml(ev.fonte) + "</a>" + fontesExtras +
      " · coletado em " + escapaHtml(formataDataCurta((ev.coletadoEm || "").slice(0, 10) || HOJE)) + "</p>" +
      "</div></article>";
  }

  function renderiza(criterios, lista, modoOrdenacao) {
    var painel = $("painel-resultados"), vazio = $("painel-vazio");
    var cidade = criterios.cidadeSelecionada;
    var cidadeTexto = cidade ? cidade.nome + "/" + cidade.uf : "todas as cidades monitoradas";

    // resumo da pesquisa
    var chips = [];
    chips.push("Cidade: " + cidadeTexto);
    if (criterios.intervalo) chips.push("Período: " + criterios.intervalo[2] + " (" + formataDataCurta(criterios.intervalo[0]) +
      (criterios.intervalo[1] !== criterios.intervalo[0] ? " a " + formataDataCurta(criterios.intervalo[1]) : "") + ")");
    criterios.categorias.forEach(function (c) { chips.push(ROTULO_CATEGORIA[c] || c); });
    if (criterios.gratuito) chips.push("Somente gratuitos");
    if (criterios.periodoDia) chips.push("Período do dia: " + { manha: "manhã", tarde: "tarde", noite: "noite" }[criterios.periodoDia]);
    if (criterios.texto) chips.push("Busca: “" + criterios.texto + "”");

    var avisos = "";
    if (criterios.avisoPreco) {
      avisos += "<p><strong>Sobre preço:</strong> as fontes não informam o valor na listagem, então o filtro de preço não pode ser aplicado. Confira o valor no link de cada evento.</p>";
    }
    $("resumo-pesquisa").innerHTML =
      "<div>Pesquisa em <strong>" + escapaHtml(cidadeTexto) + "</strong> · dados coletados em " +
      escapaHtml(formataDataHora(DADOS.geradoEm)) + " · pesquisa feita em " + escapaHtml(formataDataHora(agoraISO())) + "</div>" +
      '<div class="criterios">' + chips.map(function (c) { return '<span class="criterio">' + escapaHtml(c) + "</span>"; }).join("") + "</div>" +
      avisos;

    if (!lista.length) {
      painel.hidden = true;
      vazio.hidden = false;
      var sugestoes = ["Amplie o período (ex.: “este mês” em vez de “hoje”).",
        "Remova alguma categoria ou o filtro de gratuidade.",
        "Confira a ortografia do que digitou."];
      if (cidade && !CIDADES_COM_EVENTOS[chave(cidade.nome) + "|" + cidade.uf]) {
        sugestoes.unshift("A cidade " + cidade.nome + "/" + cidade.uf + " ainda não é monitorada. Cidades com eventos hoje: " + cidadesMonitoradasTexto() + ".");
      }
      $("texto-vazio").innerHTML =
        "<p>Nenhum evento atende a todos os critérios usados:</p>" +
        '<div class="criterios">' + chips.map(function (c) { return '<span class="criterio">' + escapaHtml(c) + "</span>"; }).join("") + "</div>" +
        "<p>Sugestões:</p><ul>" + sugestoes.map(function (s) { return "<li>" + escapaHtml(s) + "</li>"; }).join("") + "</ul>";
      vazio.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    vazio.hidden = true;
    var ordenada = ordenaEventos(lista, modoOrdenacao, criterios);
    $("titulo-resultados").textContent = lista.length + (lista.length === 1 ? " evento encontrado" : " eventos encontrados");

    var html = "";
    if (modoOrdenacao === "data") {
      // agrupa por data; eventos ja em andamento ficam em "Em cartaz"
      var grupos = {}, emCartaz = [];
      ordenada.forEach(function (ev) {
        if (ev.dataInicio < HOJE) { emCartaz.push(ev); return; }
        (grupos[ev.dataInicio] = grupos[ev.dataInicio] || []).push(ev);
      });
      if (emCartaz.length) {
        html += '<section class="grupo-data"><h3>Em cartaz (já começou e ainda está em andamento)</h3><div class="cartoes">' +
          emCartaz.map(cartaoEvento).join("") + "</div></section>";
      }
      Object.keys(grupos).sort().forEach(function (dia) {
        html += '<section class="grupo-data"><h3>' + escapaHtml(formataDataLonga(dia)) + "</h3>" +
          '<div class="cartoes">' + grupos[dia].map(cartaoEvento).join("") + "</div></section>";
      });
    } else {
      html = '<div class="cartoes">' + ordenada.map(cartaoEvento).join("") + "</div>";
    }
    $("lista-resultados").innerHTML = html;
    painel.hidden = false;
    painel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function agoraISO() {
    var d = new Date();
    return dataISO(d) + "T" + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }
  function formataDataHora(iso) {
    if (!iso) return "-";
    return formataDataCurta(iso.slice(0, 10)) + " às " + iso.slice(11, 16);
  }

  // ------------------------------------------------------------- pesquisa

  var ETAPAS_CARREGANDO = [
    "Interpretando sua solicitação...",
    "Filtrando os eventos coletados...",
    "Organizando os resultados por data...",
    "Preparando sua programação..."
  ];

  function pesquisar() {
    var criterios = montaCriterios();
    estado.ultimaConsulta = criterios;

    var carregando = $("painel-carregando");
    $("painel-resultados").hidden = true;
    $("painel-vazio").hidden = true;
    carregando.hidden = false;

    var etapa = 0;
    $("texto-carregando").textContent = ETAPAS_CARREGANDO[0];
    var timer = setInterval(function () {
      etapa++;
      if (etapa >= ETAPAS_CARREGANDO.length) {
        clearInterval(timer);
        carregando.hidden = true;
        estado.ultimaLista = filtraEventos(criterios);
        var modo = $("ordenar").value;
        if (criterios.termosLivres.length && modo === "data") { /* mantem data como padrao */ }
        renderiza(criterios, estado.ultimaLista, modo);
        return;
      }
      $("texto-carregando").textContent = ETAPAS_CARREGANDO[etapa];
    }, 220);
  }

  // ------------------------------------------------------------- PDF

  function gerarPdf() {
    if (!estado.ultimaConsulta) return;
    var criterios = estado.ultimaConsulta;
    var cidade = criterios.cidadeSelecionada;
    var cidadeTexto = cidade ? cidade.nome + "/" + cidade.uf : "todas as cidades";
    var cab = $("cabecalho-impressao");
    cab.innerHTML = "<h1>Eventos - Partiu?!</h1>" +
      "<p><strong>" + escapaHtml(estado.ultimaLista.length + " eventos em " + cidadeTexto) + "</strong></p>" +
      (criterios.intervalo ? "<p>Período: " + escapaHtml(criterios.intervalo[2] + " (" + formataDataCurta(criterios.intervalo[0]) + " a " + formataDataCurta(criterios.intervalo[1]) + ")") + "</p>" : "") +
      (criterios.texto ? "<p>Busca: " + escapaHtml(criterios.texto) + "</p>" : "") +
      "<p>Dados coletados em " + escapaHtml(formataDataHora(DADOS.geradoEm)) + " · PDF gerado em " + escapaHtml(formataDataHora(agoraISO())) + "</p>" +
      "<p>Links dos botões permanecem clicáveis no PDF. Fontes: " +
      escapaHtml((DADOS.fontes || []).map(function (f) { return f.nome; }).join(", ")) + "</p>";
    var tituloAntes = document.title;
    var nomeCidade = cidade ? chave(cidade.nome).replace(/ /g, "-") : "brasil";
    document.title = "eventos-partiu-" + nomeCidade + "-" + HOJE;
    window.print();
    document.title = tituloAntes;
  }

  // ------------------------------------------------------------- arranque

  function arranca() {
    montaAutocomplete();
    montaCep();
    montaCategorias();

    // cidade inicial: ultima usada ou Goiania/GO
    var salva = null;
    try { salva = JSON.parse(localStorage.getItem("partiu_cidade") || "null"); } catch (e) { /* ignora */ }
    if (salva && salva.nome) defineCidade(salva.nome, salva.uf, "memoria");
    else defineCidade("Goiânia", "GO", "padrao");

    $("filtro-periodo").addEventListener("change", function () {
      $("grupo-datas").hidden = this.value !== "datas";
    });
    $("botao-pesquisar").addEventListener("click", pesquisar);
    $("campo-consulta").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); pesquisar(); }
    });
    document.querySelectorAll(".exemplo").forEach(function (b) {
      b.addEventListener("click", function () {
        $("campo-consulta").value = b.textContent;
        pesquisar();
      });
    });
    $("ordenar").addEventListener("change", function () {
      if (estado.ultimaConsulta) renderiza(estado.ultimaConsulta, estado.ultimaLista, this.value);
    });
    $("botao-pdf").addEventListener("click", gerarPdf);
    $("botao-nova").addEventListener("click", function () {
      $("painel-resultados").hidden = true;
      $("painel-vazio").hidden = true;
      $("campo-consulta").value = "";
      window.scrollTo({ top: 0, behavior: "smooth" });
      $("campo-consulta").focus();
    });

    // rodape
    $("rodape-fontes").textContent = (DADOS.fontes || []).map(function (f) { return f.nome; }).join(" e ");
    $("rodape-atualizacao").textContent = "Última coleta de eventos: " + formataDataHora(DADOS.geradoEm) +
      " · " + DADOS.eventos.length + " eventos na base.";
    $("rodape-cidades").textContent = "Cidades monitoradas: " + cidadesMonitoradasTexto() + ".";
  }

  // Exposto para testes manuais no console
  window.PARTIU = {
    interpretaConsulta: interpretaConsulta,
    interpretaDatasDoTexto: interpretaDatasDoTexto,
    intervaloDoPeriodo: intervaloDoPeriodo,
    filtraEventos: filtraEventos,
    ordenaEventos: ordenaEventos
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arranca);
  else arranca();
})();
