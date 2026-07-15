# Eventos - Partiu?!

Buscador de eventos reais em cidades brasileiras, com Goiânia/GO como cidade inicial.
Site publicado no GitHub Pages e compartilhável por link, funciona em computador, tablet e celular.

**Link do app:** https://erikalemes.github.io/eventos-partiu/

## O que o app faz

- Busca por **nome da cidade** (com autocomplete de todos os 5.571 municípios do IBGE) ou por **CEP** (convertido em cidade pelo ViaCEP). A busca por raio em km não foi adotada porque as fontes de eventos não fornecem coordenadas confiáveis para todos os eventos; o CEP resolve o mesmo problema de forma mais confiável.
- **Busca simples e direta**: data inicial, data final (opcional; só a inicial = um único dia; vazio = tudo a partir de hoje) e tipo de evento, com o botão "Todos" e os tipos individuais.
- **Foco em lazer e entretenimento** (shows ao vivo, teatro, festas, gastronomia, infantil, atrações): cursos e oficinas só aparecem na lista se o usuário marcar o tipo "Cursos e oficinas".
- **Resultados agrupados por data**, com grupo "Em cartaz" para eventos longos ainda vigentes; ordenação por data, relevância ou gratuitos primeiro.
- Cada cartão mostra nome, data, hora, local, endereço, bairro, cidade, categorias, selo de gratuidade, **nível de confiabilidade**, botões de **Ingressos/Inscrição** e **Mais informações** (abrem a página original em nova aba) e a **fonte com link**. Nada é inventado: preço não informado pela fonte aparece como "consulte no site oficial".
- **Gerar PDF**: usa a impressão do navegador com layout próprio; os links continuam clicáveis no PDF salvo.
- Eventos **encerrados nunca aparecem** (filtro duplo: na coleta e na tela).
- A última cidade consultada fica salva no navegador.

## Como os dados são obtidos

O robô `scripts/coletar.py` roda no GitHub Actions **todo dia às 06:00 (Brasília)** e também sob demanda (aba Actions, botão "Run workflow"). Ele:

1. Lê as cidades de `dados/cidades_monitoradas.json`.
2. Baixa as páginas públicas por cidade da **Sympla** e da **Eventbrite** (plataformas de ingressos) e extrai o JSON embutido nelas. Para Goiânia, coleta também três fontes oficiais locais: **Goiânia Pulsa** (agenda de turismo, cobre Centro Cultural Oscar Niemeyer, Teatro Goiânia, feiras e congressos), **Centro de Convenções de Goiânia** (ccgo.com.br, agenda oficial do espaço) e **Shopping Cerrado** (eventos infantis e gratuitos). Para Brasília, coleta o **Centro de Convenções Ulysses Guimarães** (agenda oficial com data e hora). O catálogo completo de fontes sondadas, com o motivo das que ficaram de fora, está em `dados/fontes_catalogo.md`.
3. Normaliza, classifica categorias por palavras-chave, marca gratuidade quando a fonte declara, e registra fonte + URL + horário da coleta em cada evento.
4. Remove duplicados (mesmo nome + data + cidade, ou mesma URL), mantendo o registro mais completo e guardando a outra fonte como link adicional.
5. Exclui eventos encerrados e os muito distantes (mais de 240 dias).
6. Grava `docs/dados.js`; se a coleta falhar ou vier vazia, o arquivo anterior é mantido.

A coleta respeita as fontes: usa só páginas públicas, com pausa entre requisições, e o app sempre exibe e vincula a origem.

### Níveis de confiabilidade

- **Fonte oficial** - evento confirmado no site oficial do local ou organizador (Centro de Convenções, Ulysses, Shopping Cerrado).
- **Plataforma confiável** - evento encontrado em plataforma de ingressos reconhecida, com dados completos.
- **Informação incompleta** - falta horário ou local; conferir no link da fonte. Os eventos do Goiânia Pulsa entram aqui, porque a agenda lista data e local mas não o horário.

## Cidades monitoradas

Goiânia/GO, Aparecida de Goiânia/GO, Anápolis/GO, Caldas Novas/GO, Brasília/DF, Rio de Janeiro/RJ, Belo Horizonte/MG e, em São Paulo, São Paulo, São Sebastião e as cidades do trajeto litoral–capital (Caraguatatuba, Paraibuna, São José dos Campos, Jacareí, Guararema, Arujá, Mogi das Cruzes e Guarulhos).

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
- **Eventos gratuitos/culturais só divulgados em jornais**: alguns eventos (ex.: exposições no Bosque dos Buritis) aparecem apenas em portais de notícia, sem página estruturada de agenda, e ainda não são coletados. Os locais prioritários com agenda própria (Centro de Convenções, Teatro Goiânia, Oscar Niemeyer) já são cobertos pelo Goiânia Pulsa. Acrescentar um portal de notícias local é o próximo passo natural para ampliar ainda mais.
- **Cobertura / busca no Google**: os eventos vêm de Sympla, Eventbrite e Goiânia Pulsa. A busca **não** usa o Google. O Google não oferece uma API gratuita de eventos estruturados (a "caixa de eventos" dele é montada com raspagem própria e só é acessível por serviços pagos como o SerpAPI); a API de busca genérica devolve páginas soltas, sem data/local/link confiáveis, e exige chave paga — o que quebraria o modelo atual (sem chaves, rodando de graça no GitHub Pages) e ainda arriscaria trazer resultado sem fonte verificável. O caminho confiável para ampliar a cobertura é acrescentar **mais fontes estruturadas** (outras bilheterias como Ingresse, Uhuu, Blueticket; agendas oficiais de teatros e centros culturais). É só pedir a fonte que eu integro.
- **Cidades**: só as monitoradas têm eventos; qualquer cidade pode ser adicionada editando um arquivo.
- **Atualização**: os dados são do horário da última coleta (mostrado no rodapé e em cada pesquisa), não do instante da consulta.
- A extração depende do formato das páginas das fontes; se mudarem, o autoteste acusa e o robô mantém os dados anteriores.

## Próximas melhorias possíveis

- Novas fontes (agendas oficiais de teatros e centros culturais, outras bilheterias).
- Extração de preço visitando a página de cada evento.
- Filtro por distância usando as coordenadas disponíveis em parte dos eventos.
- Mais cidades monitoradas.
