# Pacote de calibração de catálogo v1

40 casos sintéticos em português, propostos pelo assistente e ainda sem aprovação humana. Não são dados reais do CatalogForge. A finalidade desta primeira entrega é tornar o contrato de qualidade concreto e verificar se o EvalDock detecta erros conhecidos antes de introduzir uma IA.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `calibration.jsonl` | 30 casos de desenvolvimento, três por cenário |
| `validation.jsonl` | 10 casos separados, um por cenário; versão marcada como held-out |
| `*-reference-outputs.json` | Controles positivos, com respostas de referência explícitas |
| `*-challenge-outputs.json` | Controles mistos: respostas corretas e falhas deliberadas |
| `RUBRIC.md` | Regras de extração, decisões e instruções para revisão |
| `evaluators.json` | Seis avaliadores determinísticos com limiar 1 |
| `gate.json` | Política estrita para os controles deste pacote |
| `expected-decisions.json` | Resultado esperado de cada métrica para cada saída desafiadora |
| `human-review.csv` | Planilha de aprovação/correção de referências; todas pendentes |
| `manifest.json` | Procedência, contagens e hashes SHA-256 dos arquivos |

As saídas são objetos com três chaves obrigatórias: `material`, `weight_g` e `country`. Ausência explícita é null, peso é número em gramas e país é código ISO de fabricação. Ver a rubrica para equivalências e situações ambíguas. A comparação de texto é estrita: sinônimos ou variações não declaradas precisam de decisão e nova versão de normalização antes de avaliar um sistema real.

## Cenários

Campos explícitos; informação ausente; conversão kg→g; fontes contraditórias; peso líquido/transporte; unidade/conjunto; fabricação/design/distribuição; material inferido da aparência; instrução maliciosa no texto; zero e tipos JSON. Cada cenário tem três casos de calibração e um de validação. Há 20 falhas deliberadas nos 30 casos de calibração e cinco nos dez casos de validação.

O conjunto separado foi fixado antes das execuções. Esta é validação da configuração com controles conhecidos, não um teste cego nem uma estimativa de desempenho em dados reais. Após repetidos ajustes, reservar novos casos reais para validação final.

## Reprodução

Na raiz do EvalDock, com os serviços em execução e o workspace inicial configurado:

```bash
uv run python scripts/prepare_catalog_calibration.py
uv run python scripts/load_catalog_calibration.py
cd apps/web
npm run e2e -- e2e/calibration.spec.ts
```

O primeiro comando regenera os arquivos a partir das referências explícitas no script de autoria. Para mudar rótulos, crie uma nova versão do pacote; não sobrescreva decisões humanas na planilha gerada. O segundo comando usa a API pública, cria um projeto próprio e reutiliza seus recursos/execuções quando compatíveis. Ele para diante de versões ou configurações divergentes. Não remove dados, não altera os projetos originais, não cria avaliações humanas e não chama alvos/modelos. Credenciais permanecem no `.env` local. O teste de navegador só lê dados e manipula controles sem salvar.

Resultado executado: `docs/catalog-calibration-v1.json` e `docs/catalog-calibration-v1.md`. Referências são fixadas separadamente por conjunto: `main` para os 30 casos e `validation-v1` para os dez. Evite comparar conjuntos diferentes como se fossem o mesmo baseline. Não use o controle positivo, que já contém as respostas, como medida de qualidade de um modelo.
