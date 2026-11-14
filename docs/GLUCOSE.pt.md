# Glicose

A página lê as leituras do sensor via LibreLinkUp (conta de seguidor) e mostra gráfico, média de 48 horas e histórico de registos. O registo manual de insulina permite editar e apagar.

**Isto não é um dispositivo médico.** Não substitui o médico nem o equipamento certificado. Não uses valores deste projeto para decidir doses.

## A calculadora vem desligada

O repositório **não traz nenhum valor de dose**. Para a ativar, o teu médico define o esquema e tu escreves-o em `~/.config/odysseus-kit/config.json`:

```json
"glucose": {
  "fiasp_start": 0,
  "fiasp_base": 0,
  "fiasp_step": 0,
  "carb_per_unit": 0,
  "max_dose": 0,
  "hypo": 70,
  "basal_default": 0,
  "basal_high_avg": 0,
  "basal_low_avg": 0,
  "basal_step": 0
}
```

(Substitui os zeros pelos valores do teu médico.) Os nomes dos campos refletem um esquema de insulina rápida com correção por glicose e relação hidratos/unidade, mais uma sugestão de ajuste da dose basal pela média de 2 dias. Sem todos os campos de cada bloco preenchidos, o bloco fica desativado.

- A sugestão é sempre para **confirmares tu**; nada é enviado a nenhum dispositivo.
- Abaixo do limiar `hypo` a página recusa sugerir insulina.
- A estimativa de hidratos por foto é aproximada; confirma sempre os valores.
