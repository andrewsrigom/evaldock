# EvalDock — primeira base de calibração

[Abrir o projeto](http://localhost:5188/projects/4c9c6814-b3cd-4890-968c-41d935755c24/overview) · [Comparar os controles](http://localhost:5188/projects/4c9c6814-b3cd-4890-968c-41d935755c24/compare) · [Fila de revisão](http://localhost:5188/projects/4c9c6814-b3cd-4890-968c-41d935755c24/reviews)

## Entrega

O projeto **Calibração de catálogo · sintética v1** contém 40 casos em português, dois datasets versionados (30 calibração e 10 validação), seis avaliadores determinísticos, uma suite e quatro execuções concluídas. Os projetos Catalog extraction e Support triage foram preservados.

Todos os casos e rótulos foram propostos pelo assistente. A procedência sintética e a aprovação humana pendente aparecem no contexto de cada caso, nas tags, no nome e na descrição do projeto. Nenhum resultado foi registrado como avaliação humana.

O contrato exige exatamente `material`, `weight_g` e `country`, com null explícito quando necessário, peso numérico em gramas e país de fabricação normalizado. Há casos de informação ausente, conflitos, unidades, embalagem, conjuntos, origem, aparência, instruções maliciosas e zero/tipos.

## Execução conferida

| Resultado | Calibração | Validação |
|---|---:|---:|
| Casos distintos | 30 | 10 |
| Controles positivos corretos | 30/30 | 10/10 |
| Falhas propositais detectadas no registro completo | 20/20 | 5/5 |
| Registros corretos no controle misto | 10/30 | 5/10 |
| Cobertura das seis métricas | 100% | 100% |
| Erros de execução/avaliação | 0 | 0 |
| Gate do controle com falhas | Reprovado como esperado | Reprovado como esperado |

Foram verificadas **480 decisões**: 80 execuções de casos × seis métricas. Cada decisão foi comparada com o manifesto esperado. Os 40 controles positivos passaram nos seis critérios. Os controles negativos reprovaram pelas falhas deliberadas, sem erros de infraestrutura. Os relatórios foram persistidos como artefatos no EvalDock. Não houve chamadas a alvos nem a modelos; latência e custo de modelo não são inferidos.

Esta validação comprova o funcionamento dos critérios e do fluxo local. A proporção de falhas foi escolhida para testar detecção, portanto as porcentagens não medem a qualidade de um extrator ou de uma IA.

## Como revisar agora

1. Em **Compare**, selecione `record_exact`. A seleção inicial usa os controles de 30 casos. Devem aparecer 20 regressões e dez casos aprovados em ambos os lados. Em `field_accuracy`, aparecem 18 regressões: duas saídas têm campos corretos, mas incluem uma chave extra, detectada por `schema_valid` e `record_exact`.
2. Comece pelos casos `catalog-v1-02-01` (chave omitida versus null), `catalog-v1-03-01` (kg versus g), `catalog-v1-07-01` (design versus fabricação) e `catalog-v1-09-01` (instrução maliciosa). Confira a passagem, a referência e a justificativa.
3. Para aprovar/corrigir os rótulos, preencha `human-review.csv`: status, responsável e observação. O estado inicial de todos os 40 casos é `pending`. Se uma referência precisar mudar, crie uma nova versão do dataset e mantenha o histórico.
4. Na **Human review**, pesquise `controle negativo · 30 calibração` para reduzir a fila de 80 execuções a 30. Abra um caso e registre a decisão humana para `record_exact`, citando a evidência. Essa decisão é sobre a saída avaliada; não substitui a revisão da referência nem apaga a decisão automática.
5. Só depois de aprovar as referências e a rubrica, testar um extrator real por outputs importados. A primeira IA pode avaliar fidelidade ao texto. Comparar decisões com uma amostra aprovada por uma pessoa e analisar falsos aprovados/reprovados por cenário antes de usar o juiz em gates.

Os dez casos separados já foram usados para conferir a configuração congelada. Continuam identificados como validação, mas não constituem teste cego de um modelo. Reserve novos casos reais quando começar a ajustar prompts repetidamente.

## Ajuste de UX encontrado

O checklist agora reconhece saídas importadas como entrada válida. Projetos sem alvo HTTP abrem o lançador no modo de importação. Isso evita cobrar uma integração que este fluxo não precisa. O build inclui a checagem estrita de TypeScript.

## Referências fixadas

- Calibração: [controle positivo](http://localhost:5188/experiments/12aaadd9-f5a2-4d19-957e-39cc9b3aab36) e [falhas injetadas](http://localhost:5188/experiments/6a021a44-e126-4a3f-aef3-d67b35cba630); baseline `main`.
- Validação: [controle positivo](http://localhost:5188/experiments/29a52d68-92a5-40c7-ab54-76cadc7a1aa8) e [falhas injetadas](http://localhost:5188/experiments/e8b329b2-1d0f-401d-936c-11a6d88623c4); baseline `validation-v1`.

Pacote no repositório: `calibration/catalog-v1/`. Relatório estruturado: `docs/catalog-calibration-v1.json`. Os scripts preservam os projetos originais e não excluem dados.

## Verificação da entrega

A jornada Playwright desta calibração passou: checklist de importação, lançador sem alvo, comparação 30/10, filtro de instruções maliciosas e fila humana sem avaliações fabricadas. O navegador não apresentou erros. TypeScript estrito, build de produção e lint/formatação dos dois scripts passaram. As suítes anteriores de testes não foram repetidas; o backend não foi alterado.
