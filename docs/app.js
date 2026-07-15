/* Eventos - Partiu?! — logica do aplicativo (roda 100% no navegador).
   Dados: window.EVENTOS_DATA (gerado pelo robo scripts/coletar.py)
          window.CIDADES_BR  (municipios do IBGE, para autocomplete/CEP)
   Busca simples: cidade + data inicial + data final (opcional) + tipo de evento.
   Foco em lazer e entretenimento: cursos so aparecem se o tipo for marcado.
   Nada e inventado: todo evento tem fonte e link. */
(function () {
  "use strict";

  var DADOS = window.EVENTOS_DATA || { eventos: [], cidades: [], fontes: [], geradoEm: "" };
  var CIDADES_BR = window.CIDADES_BR || [];

  var DIAS_SEMANA = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
  var MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

  // Tipos mostrados ao usuario -> categorias internas dos eventos.
  // "Cursos e oficinas" fica fora do "Todos": o foco do buscador e lazer.
  var TIPOS_UI = [
    ["todos", "Todos", null],
    ["shows", "Shows e música", ["shows"]],
    ["teatro", "Teatro", ["teatro"]],
    ["stand-up", "Stand-up", ["stand-up"]],
    ["festas", "Festas e festivais", ["festas"]],
    ["gastronomia", "Gastronomia", ["gastronomia"]],
    ["infantil", "Infantil", ["infantil"]],
    ["lazer", "Lazer e atrações", ["lazer"]],
    ["exposicoes", "Exposições e feiras", ["exposicoes", "feiras"]],
    ["danca", "Dança", ["danca"]],
    ["esportes", "Esportes", ["esportes"]],
    ["cursos", "Cursos e oficinas", ["cursos"]],
    ["outros", "Outros", ["outros", "congressos", "negocios", "tecnologia", "universitarios", "religiosos", "literatura"]]
  ];
  var ROTULO_TIPO = {};
  TIPOS_UI.forEach(function (t) { ROTULO_TIPO[t[0]] = t[1]; });

  // Rotulos das categorias internas (para as etiquetas dos cartoes)
  var ROTULO_CATEGORIA = {
    shows: "Shows e música", teatro: "Teatro", "stand-up": "Stand-up", festas: "Festas e festivais",
    gastronomia: "Gastronomia", infantil: "Infantil", cursos: "Cursos e oficinas",
    congressos: "Congressos e palestras", esportes: "Esportes", feiras: "Feiras",
    exposicoes: "Exposições e mostras", danca: "Dança", religiosos: "Religiosos",
    literatura: "Literatura", tecnologia: "Tecnologia", negocios: "Negócios",
    universitarios: "Universitários", lazer: "Lazer e atrações", outros: "Outros"
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
    return /^https?:\/\//i.test(u || "") ? u : "";
  }
  function dataISO(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function deISO(iso) {
    var p = iso.split("-");
    return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
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

  var CIDADES_COM_EVENTOS = {};
  DADOS.eventos.forEach(function (ev) {
    CIDADES_COM_EVENTOS[chave(ev.cidade) + "|" + ev.uf] = ev.cidade + "|" + ev.uf;
  });
  var CIDADES_MONITORADAS = (DADOS.cidades || []).map(function (c) { return c.nome + "/" + c.uf; });

  // ------------------------------------------------------------- estado

  var estado = {
    cidade: null,          // {nome, uf}
    ultimaConsulta: null,
    ultimaLista: []
  };

  function cidadesMonitoradasTexto() {
    return CIDADES_MONITORADAS.join(", ");
  }

  function defineCidade(nome, uf, origem) {
    estado.cidade = { nome: nome, uf: uf };
    $("campo-cidade").value = nome + "/" + uf;
    try { localStorage.setItem("partiu_cidade", JSON.stringify(estado.cidade)); } catch (e) { /* privado */ }
    var ajuda = $("ajuda-cidade");
    if (CIDADES_COM_EVENTOS[chave(nome) + "|" + uf]) {
      ajuda.textContent = origem === "cep" ? "CEP localizado em " + nome + "/" + uf + "." : "";
      ajuda.classList.remove("erro");
    } else {
      ajuda.textContent = nome + "/" + uf + " ainda não é monitorada. Cidades disponíveis: " + cidadesMonitoradasTexto() + ".";
      ajuda.classList.add("erro");
    }
  }

  // ------------------------------------------------------- autocomplete/CEP

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

  // ------------------------------------------------------- chips de tipo

  function montaTipos() {
    $("chips-categorias").innerHTML = TIPOS_UI.map(function (t) {
      var marcado = t[0] === "todos" ? " checked" : "";
      return '<label><input type="checkbox" value="' + t[0] + '"' + marcado + "> " + escapaHtml(t[1]) + "</label>";
    }).join("");
    var caixa = $("chips-categorias");
    caixa.addEventListener("change", function (e) {
      var alvo = e.target;
      if (alvo.value === "todos" && alvo.checked) {
        caixa.querySelectorAll("input").forEach(function (i) { if (i.value !== "todos") i.checked = false; });
      } else if (alvo.value !== "todos" && alvo.checked) {
        caixa.querySelector('input[value="todos"]').checked = false;
      }
      // nada marcado volta para Todos
      if (!caixa.querySelector("input:checked")) caixa.querySelector('input[value="todos"]').checked = true;
    });
  }

  function tiposMarcados() {
    return Array.prototype.slice.call(document.querySelectorAll("#chips-categorias input:checked"))
      .map(function (i) { return i.value; });
  }

  // ------------------------------------------------------------- criterios

  function montaCriterios() {
    var ini = $("filtro-data-ini").value;
    var fim = $("filtro-data-fim").value;
    if (ini && fim && fim < ini) { var tmp = ini; ini = fim; fim = tmp; }
    if (ini && !fim) fim = ini;            // um dia so
    if (!ini && fim) ini = HOJE;           // ate uma data
    var marcados = tiposMarcados();
    var todos = marcados.indexOf("todos") >= 0 || !marcados.length;
    var categorias = [];
    if (!todos) {
      marcados.forEach(function (id) {
        var def = TIPOS_UI.filter(function (t) { return t[0] === id; })[0];
        if (def && def[2]) def[2].forEach(function (c) { if (categorias.indexOf(c) < 0) categorias.push(c); });
      });
    }
    return {
      cidadeSelecionada: estado.cidade,
      intervalo: (ini || fim) ? [ini, fim] : null,
      todos: todos,
      tiposMarcados: todos ? [] : marcados,
      categorias: categorias,
      incluiCursos: marcados.indexOf("cursos") >= 0
    };
  }

  // ------------------------------------------------------------- filtragem

  function eventoNoIntervalo(ev, ini, fim) {
    var evIni = ev.dataInicio, evFim = ev.dataFim || ev.dataInicio;
    return evIni <= fim && evFim >= ini;
  }

  function filtraEventos(criterios) {
    return DADOS.eventos.filter(function (ev) {
      if (criterios.cidadeSelecionada &&
        chave(ev.cidade) + "|" + ev.uf !== chave(criterios.cidadeSelecionada.nome) + "|" + criterios.cidadeSelecionada.uf) return false;
      var fimEv = ev.dataFim || ev.dataInicio;
      if (fimEv < HOJE) return false; // nunca mostra evento encerrado
      if (criterios.intervalo && !eventoNoIntervalo(ev, criterios.intervalo[0], criterios.intervalo[1])) return false;
      var ehCurso = ev.categorias.indexOf("cursos") >= 0;
      if (ehCurso && !criterios.incluiCursos) return false; // cursos so quando pedidos
      if (!criterios.todos && criterios.categorias.length &&
        !criterios.categorias.some(function (c) { return ev.categorias.indexOf(c) >= 0; })) return false;
      return true;
    });
  }

  function ordenaEventos(lista, modo) {
    var copia = lista.slice();
    copia.sort(function (a, b) {
      if (modo === "gratuitos" && a.gratuito !== b.gratuito) return a.gratuito ? -1 : 1;
      return (a.dataInicio + (a.horaInicio || "99")).localeCompare(b.dataInicio + (b.horaInicio || "99"));
    });
    return copia;
  }

  // ------------------------------------------------------------- cartoes

  var ROTULO_CONFIANCA = {
    oficial: ["confianca-oficial", "Fonte oficial", "Evento confirmado no site oficial do local ou organizador."],
    plataforma: ["confianca-plataforma", "Plataforma confiável", "Evento encontrado em plataforma de ingressos reconhecida."],
    incompleta: ["confianca-incompleta", "Informação incompleta", "Faltam dados como horário ou local; confirme no link da fonte."]
  };

  function cartaoEvento(ev) {
    var urlIngresso = urlSegura(ev.urlIngresso), urlInfo = urlSegura(ev.urlInfo), urlFonte = urlSegura(ev.fonteUrl);
    var ehInscricao = ev.categorias.indexOf("cursos") >= 0 || ev.categorias.indexOf("congressos") >= 0;
    var rotuloBotao = (ev.gratuito || ehInscricao) ? "Inscrição / Detalhes" : "Ingressos";
    var etiquetas = "";
    if (ev.gratuito) etiquetas += '<span class="etiqueta gratuito">Gratuito</span>';
    if (ev.online) etiquetas += '<span class="etiqueta online">On-line</span>';
    ev.categorias.slice(0, 3).forEach(function (c) {
      etiquetas += '<span class="etiqueta">' + escapaHtml(ROTULO_CATEGORIA[c] || c) + "</span>";
    });
    var conf = ROTULO_CONFIANCA[ev.confianca] || ROTULO_CONFIANCA.incompleta;
    etiquetas += '<span class="etiqueta ' + conf[0] + '" title="' + escapaHtml(conf[2]) + '">' + escapaHtml(conf[1]) + "</span>";

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
      (urlInfo && urlInfo !== urlIngresso ? '<a class="acao-info" href="' + escapaHtml(urlInfo) + '" target="_blank" rel="noopener noreferrer">Mais informações</a>' : "") +
      "</div>" +
      '<p class="fonte-cartao">Fonte: <a href="' + escapaHtml(urlFonte) + '" target="_blank" rel="noopener noreferrer">' + escapaHtml(ev.fonte) + "</a>" + fontesExtras +
      " · coletado em " + escapaHtml(formataDataCurta((ev.coletadoEm || "").slice(0, 10) || HOJE)) + "</p>" +
      "</div></article>";
  }

  // ------------------------------------------------------------- resultados

  function chipsDoResumo(criterios) {
    var cidade = criterios.cidadeSelecionada;
    var chips = ["Cidade: " + (cidade ? cidade.nome + "/" + cidade.uf : "todas")];
    if (criterios.intervalo) {
      chips.push(criterios.intervalo[0] === criterios.intervalo[1]
        ? "Dia " + formataDataCurta(criterios.intervalo[0])
        : "De " + formataDataCurta(criterios.intervalo[0]) + " a " + formataDataCurta(criterios.intervalo[1]));
    } else {
      chips.push("A partir de hoje");
    }
    if (criterios.todos) chips.push("Todos os tipos (sem cursos)");
    else criterios.tiposMarcados.forEach(function (t) { chips.push(ROTULO_TIPO[t] || t); });
    return chips;
  }

  function renderiza(criterios, lista, modoOrdenacao) {
    var painel = $("painel-resultados"), vazio = $("painel-vazio");
    var chips = chipsDoResumo(criterios);

    $("resumo-pesquisa").innerHTML =
      "<div>Dados coletados em " + escapaHtml(formataDataHora(DADOS.geradoEm)) +
      " · pesquisa feita em " + escapaHtml(formataDataHora(agoraISO())) + "</div>" +
      '<div class="criterios">' + chips.map(function (c) { return '<span class="criterio">' + escapaHtml(c) + "</span>"; }).join("") + "</div>";

    if (!lista.length) {
      painel.hidden = true;
      vazio.hidden = false;
      var cidade = criterios.cidadeSelecionada;
      var sugestoes = ["Amplie o intervalo de datas.", "Marque “Todos” nos tipos de evento."];
      if (cidade && !CIDADES_COM_EVENTOS[chave(cidade.nome) + "|" + cidade.uf]) {
        sugestoes.unshift("A cidade " + cidade.nome + "/" + cidade.uf + " ainda não é monitorada. Cidades com eventos hoje: " + cidadesMonitoradasTexto() + ".");
      }
      $("texto-vazio").innerHTML =
        "<p>Nenhum evento atende aos critérios usados:</p>" +
        '<div class="criterios">' + chips.map(function (c) { return '<span class="criterio">' + escapaHtml(c) + "</span>"; }).join("") + "</div>" +
        "<p>Sugestões:</p><ul>" + sugestoes.map(function (s) { return "<li>" + escapaHtml(s) + "</li>"; }).join("") + "</ul>";
      vazio.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    vazio.hidden = true;
    var ordenada = ordenaEventos(lista, modoOrdenacao);
    $("titulo-resultados").textContent = lista.length + (lista.length === 1 ? " evento encontrado" : " eventos encontrados");

    var html = "";
    if (modoOrdenacao === "data") {
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

  function pesquisar() {
    var criterios = montaCriterios();
    estado.ultimaConsulta = criterios;

    var carregando = $("painel-carregando");
    $("painel-resultados").hidden = true;
    $("painel-vazio").hidden = true;
    carregando.hidden = false;

    setTimeout(function () {
      carregando.hidden = true;
      estado.ultimaLista = filtraEventos(criterios);
      renderiza(criterios, estado.ultimaLista, $("ordenar").value);
    }, 350);
  }

  // ------------------------------------------------------------- PDF

  function gerarPdf() {
    if (!estado.ultimaConsulta) return;
    var criterios = estado.ultimaConsulta;
    var cidade = criterios.cidadeSelecionada;
    var cidadeTexto = cidade ? cidade.nome + "/" + cidade.uf : "todas as cidades";
    var chips = chipsDoResumo(criterios);
    var cab = $("cabecalho-impressao");
    cab.innerHTML = "<h1>Eventos - Partiu?!</h1>" +
      "<p><strong>" + escapaHtml(estado.ultimaLista.length + " eventos em " + cidadeTexto) + "</strong></p>" +
      "<p>" + chips.map(escapaHtml).join(" · ") + "</p>" +
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
    montaTipos();

    var salva = null;
    try { salva = JSON.parse(localStorage.getItem("partiu_cidade") || "null"); } catch (e) { /* ignora */ }
    if (salva && salva.nome) defineCidade(salva.nome, salva.uf, "memoria");
    else defineCidade("Goiânia", "GO", "padrao");

    $("filtro-data-ini").min = HOJE;
    $("filtro-data-fim").min = HOJE;

    $("botao-pesquisar").addEventListener("click", pesquisar);
    $("ordenar").addEventListener("change", function () {
      if (estado.ultimaConsulta) renderiza(estado.ultimaConsulta, estado.ultimaLista, this.value);
    });
    $("botao-pdf").addEventListener("click", gerarPdf);
    $("botao-nova").addEventListener("click", function () {
      $("painel-resultados").hidden = true;
      $("painel-vazio").hidden = true;
      window.scrollTo({ top: 0, behavior: "smooth" });
      $("campo-cidade").focus();
    });

    $("rodape-fontes").textContent = (DADOS.fontes || []).map(function (f) { return f.nome; }).join(", ");
    $("rodape-atualizacao").textContent = "Última coleta de eventos: " + formataDataHora(DADOS.geradoEm) +
      " · " + DADOS.eventos.length + " eventos na base.";
    $("rodape-cidades").textContent = "Cidades monitoradas: " + cidadesMonitoradasTexto() + ".";
  }

  // Exposto para verificacao manual no console
  window.PARTIU = {
    filtraEventos: filtraEventos,
    ordenaEventos: ordenaEventos,
    montaCriterios: montaCriterios
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", arranca);
  else arranca();
})();
