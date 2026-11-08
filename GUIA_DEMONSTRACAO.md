# Guia de demonstração

## Preparação

1. Crie a base PostgreSQL `gestao_associacao` e defina as credenciais em `.env`, a partir de `.env.example`.
2. Inicie PostgreSQL e MongoDB. Para MongoDB local com Docker: `docker run --rm -p 27017:27017 --name gestao-mongo mongo:7`.
3. Instale dependências: `python3 -m pip install -r requirements.txt`.
4. Aplique os scripts SQL na base de demonstração, pela ordem: `01_tabelas.sql`, `02_procedures.sql`, `03_views.sql`, `04_alter_associado_password.sql`, `05_functions.sql`, `06_triggers.sql`, `09_migration_movimento_bancario_associacao.sql`, `10_fase21_financeiro.sql`, `11_migration_recalcular_estados_quotas.sql`, `12_fase22_conciliacao_bancaria.sql` e `13_fase25_mandatos_posse.sql`.
5. Inicie a aplicação: `python3 manage.py runserver`.

## Credenciais de demonstração

Crie uma associação de demonstração no registo público e defina uma palavra-passe exclusiva para a sessão de demonstração. Entre com o NIPC da associação e essa palavra-passe; não use nem registe credenciais reais neste guia.

## Dados mínimos

- Uma associação, associados ativos e uma localidade.
- Órgão social `Direção` com cargos `Presidente` e `Tesoureiro`.
- Um mandato ativo e cargos atribuídos aos associados.
- Uma quota mensal e uma anual, quotas de associados geradas e pelo menos um pagamento parcial e um total.
- Um CSV com colunas `data_movimento,valor_movimento,descricao_movimento,referencia_movimento` e um documento PDF pequeno.

## Ordem recomendada

1. Autenticar como Direção e mostrar o painel administrativo.
2. Criar/editar um associado e consultar a lista.
3. Mostrar órgãos, cargos, mandato e respetiva composição.
4. Criar quotas, gerar quotas de associados e registar pagamentos.
5. Importar o CSV, conciliar um movimento e demonstrar a reversão.
6. Carregar, consultar e descarregar um documento.
7. Consultar auditoria e estatísticas.
8. Demonstrar alteração de palavra-passe ou passagem de posse; a palavra-passe gerada deve ser comunicada apenas ao novo presidente e não registada em logs.
