# Catálogo de fontes (do levantamento de 15/07/2026)

Origem: documento "Eventos Partiu Fontes públicas para coletores de eventos em Goiânia,
Aparecida e Brasília". Status de implementação após sondagem técnica real de cada uma.

## Implementadas (coletadas pelo robô)

| Fonte | Cidade | Como coleta |
|---|---|---|
| Sympla | todas monitoradas | JSON embutido nas páginas por cidade |
| Eventbrite | todas monitoradas | window.__SERVER_DATA__ (só aceita evento com local na cidade) |
| Goiânia Pulsa | Goiânia (agenda oficial de turismo) | cartões HTML `evento-item` |
| Centro de Convenções Goiânia (ccgo.com.br/eventos) | Goiânia | cartões `grid-entry` (título + data/intervalo + espaço) |
| Shopping Cerrado (acontece) | Goiânia | listagem + página de cada post (datas por extenso) |
| Ulysses Centro de Convenções (ulysses.tur.br/agenda) | Brasília | JSON-LD schema.org/Event completo (com hora) |

## Sondadas e inviáveis por enquanto (15/07/2026)

| Fonte | Motivo |
|---|---|
| BaladAPP (baladapp.com.br) | sem listagem pública por cidade (home em JavaScript, sem sitemap/API); páginas individuais são legíveis, então entra via `dados/eventos_avulsos.json` (link a link) |
| Boulevard Brasília (acontece) | página montada por JavaScript (Next.js sem dados no HTML) |
| Teatro SESI (programacao) | conteúdo montado por JavaScript |
| Bilheteria Digital /GO | conteúdo montado por JavaScript |
| Guichê Web | página sem listagem extraível no HTML |
| Flamboyant (lazer) | página montada por JavaScript (18 KB de casca) |
| Centro Cultural UFG | mistura notícias e editais; datas são de publicação, não do evento |
| Plataforma de Cultura de Aparecida | não é MapasCulturais; sem API/listagem estruturada encontrada |
| Secult Goiânia / goias.gov.br cultura | páginas institucionais sem agenda corrente estruturada |
| CCBB Brasília / CAIXA Cultural / Sesc DF / Agenda DF | páginas grandes sem JSON-LD de evento; extração exigiria manutenção alta (candidatas a próxima rodada) |
| Curta Mais / Mais Goiás / Metrópoles / Revista Zelo | portais de notícia: cada evento é uma matéria, sem agenda estruturada |
| Instagram (CCON, CCGO, Aparecida Shopping) | rede social; scraping bloqueado, só revisão manual/API oficial |

## Como acrescentar uma nova fonte

1. Sondar: a página entrega título + data + link no HTML puro (sem JavaScript)?
2. Escrever `extrai_<fonte>()` + `normaliza_<fonte>()` em `scripts/coletar.py`.
3. Registrar em `executa()` (condicionada à cidade monitorada) e na lista `fontes`.
4. Salvar um fixture em `tests/fixtures/` e cobrir no `scripts/autoteste.py`.
5. Regra de ouro: sem data confiável na fonte, o evento NÃO entra (nada de chutar ano).
