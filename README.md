# Eventos - Partiu?!

Buscador de eventos reais em cidades brasileiras, com Goiânia/GO como cidade inicial.
Site publicado no GitHub Pages e compartilhável por link, funciona em computador, tablet e celular.

**Link do app:** https://erikalemes.github.io/eventos-partiu/

## O que o app faz

- Busca por **nome da cidade** (com autocomplete de todos os 5.571 municípios do IBGE) ou por **CEP** (convertido em cidade pelo ViaCEP). A busca por raio em km não foi adotada porque as fontes de eventos não fornecem coordenadas confiáveis para todos os eventos; o CEP resolve o mesmo problema de forma mais confiável.
- Aceita **consulta em linguagem natural**: "shows em Brasília no próximo mês", "teatro infantil no domingo", "eventos gratuitos neste fim de semana". A interpretação identifica cidade, datas relativas (hoje, amanhã, fim de semana, próxima semana, este mês...), categorias, gratuidade e período do dia.
- **Filtros combináveis**: período (inclusive intervalo de datas), período do dia, 18 categorias, somente gratuitos, somente presenciais.
- **Resultados agrupados por data**, com grupo "Em cartaz" para eventos longos ainda vigentes; ordenação por data, relevância ou gratuitos primeiro.
- Cada cartão mostra nome, data, hora, local, endereço, bairro, cidade, categorias, selo de gratuidade, **nível de confiabilidade**, botões de **Ingressos/Inscrição** e **Mais informações** (abrem a página original em nova aba) e a **fonte com link**. Nada é inventado: preço não informado pela fonte aparece como "consulte no site oficial".
- **Gerar PDF**: usa a impressão do navegador com layout próprio; os links continuam clicáveis no PDF salvo.
- Eventos **encerrados nunca aparecem** (filtro duplo: na coleta e na tela).
- A última cidade consultada fica salva no navegador.

## Como os dados são obtidos

O robô `scripts/coletar.py` roda no GitHub Actions **todo dia às 06:00 (Brasília)** e também sob demanda (aba Actions, botão "Run workflow"). Ele:

1. Lê as cidades de `dados/cidades_monitoradas.json`.
2. Baixa as páginas públicas por cidade da **Sympla** e da **Eventbrite** (plataformas de ingressos) e extrai o JSON embutido nelas.
3. Normaliza, classifica categorias por palavras-chave, marca gratuidade quando a fonte declara, e registra fonte + URL + horário da coleta em cada evento.
4. Remove duplicados (mesmo nome + data + cidade, ou mesma URL), mantendo o registro mais completo e guardando a outra fonte como link adicional.
5. Exclui eventos encerrados e os muito distantes (mais de 240 dias).
6. Grava `docs/dados.js`; se a coleta falhar ou vier vazia, o arquivo anterior é mantido.

A coleta respeita as fontes: usa só páginas públicas, com pausa entre requisições, e o app sempre exibe e vincula a origem.

### Níveis de confiabilidade

- **Plataforma confiável** - evento encontrado em plataforma de ingressos reconhecida, com dados completos.
- **Informação incompleta** - falta horário ou local; conferir no link da fonte.

## Cidades monitoradas

Goiânia/GO, Aparecida de Goiânia/GO, Anápolis/GO, Brasília/DF, São Paulo/SP, Rio de Janeiro/RJ, Belo Horizonte/MG e Caldas Novas/GO.

**Para adicionar uma cidade:** inclua uma linha em `dados/cidades_monitoradas.json` com o nome, UF, o slug da Sympla (fim da URL de `https://www.sympla.com.br/eventos/<slug>`) e o slug da Eventbrite (fim da URL de `https://www.eventbrite.com.br/d/brazil--<slug>/all-events/`). A próxima coleta já inclui a cidade.

Se o usuário pesquisar uma cidade não monitorada, o app avisa com clareza e lista as disponíveis, sem inventar resultados.

## Estrutura

```
docs/               site publicado (GitHub Pages em main:/docs)
  index.html        página única do app
  estilo.css        visual (mobile-first) + layout de impressão do PDF
  app.js            interpretação da consulta, filtros, cartões, PDF
  dados.js          eventos coletados (gerado pelo robô; não editar à mão)
  cidades.js        municípios do IBGE (gerado por scripts/gerar_cidades.py)
scripts/
  coletar.py        robô de coleta (Sympla + Eventbrite)
  gerar_cidades.py  atualiza docs/cidades.js pela API do IBGE
  autoteste.py      30 verificações automáticas (roda no workflow)
dados/
  cidades_monitoradas.json   cidades coletadas
tests/fixtures/     páginas HTML salvas para o autoteste rodar sem internet
.github/workflows/coletar.yml  coleta diária + sob demanda
```

## Rodar localmente

```
python scripts/coletar.py     # atualiza docs/dados.js (precisa de internet)
python scripts/autoteste.py   # roda as verificações
python -m http.server 8766 --directory docs   # abre http://localhost:8766
```

Não há chaves, senhas nem serviços pagos: o projeto usa apenas páginas públicas e roda inteiro no navegador + GitHub Actions.

## Segurança e privacidade

- Todo texto vindo das fontes é escapado antes de ir para a tela (proteção contra XSS); conteúdo externo é tratado como dado, nunca como comando.
- Só links `http(s)` absolutos são aceitos nos botões.
- A consulta do usuário é limitada a 200 caracteres e processada só no navegador; nada é enviado a servidores próprios (a única chamada externa do app é o ViaCEP, para converter CEP em cidade).
- Não há login, conta, rastreamento nem armazenamento além da última cidade (localStorage do próprio navegador).

## Limitações conhecidas

- **Preço**: as listagens das fontes não informam valor, então não há filtro por faixa de preço; quando o usuário pede "até R$ X", o app avisa que o valor deve ser conferido no link. Gratuidade só é marcada quando o próprio título/descrição declara.
- **Cobertura**: os eventos vêm de Sympla e Eventbrite. Agendas de teatros públicos, shoppings e prefeituras ainda não são coletadas (os sites não oferecem dados estruturados estáveis); muitos desses eventos também vendem pela Sympla e acabam aparecendo.
- **Cidades**: só as monitoradas têm eventos; qualquer cidade pode ser adicionada editando um arquivo.
- **Atualização**: os dados são do horário da última coleta (mostrado no rodapé e em cada pesquisa), não do instante da consulta.
- A extração depende do formato das páginas das fontes; se mudarem, o autoteste acusa e o robô mantém os dados anteriores.

## Próximas melhorias possíveis

- Novas fontes (agendas oficiais de teatros e centros culturais, outras bilheterias).
- Extração de preço visitando a página de cada evento.
- Filtro por distância usando as coordenadas disponíveis em parte dos eventos.
- Mais cidades monitoradas.
