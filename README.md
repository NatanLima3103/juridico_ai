# Juridico AI

## Etapa 14.8 - Logs de producao

Objetivo: deixar os logs de producao consultaveis, correlacionaveis e com rotacao basica no Docker, sem gravar dados sensiveis em arquivos dentro da aplicacao.

### Como ficou

- A aplicacao configura logging no bootstrap com `LOG_LEVEL` e `LOG_FORMAT`.
- Em producao, o padrao e `LOG_FORMAT=json`, adequado para `docker compose logs`, agentes de coleta e provedores de observabilidade.
- Cada requisicao HTTP gera um log com metodo, caminho sem query string, status, duracao, ambiente, IP de origem e `request_id`.
- O header `X-Request-ID` e preservado quando enviado pelo proxy; quando ausente, a aplicacao gera um identificador e devolve no response.
- Os servicos Docker de producao usam o driver `json-file` com rotacao por `LOG_MAX_SIZE` e `LOG_MAX_FILE`.
- O log operacional fica no stdout/stderr dos containers; auditoria de negocio continua em `audit_logs`.

### Variaveis

No `.env.production`, ajuste conforme o ambiente:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_MAX_SIZE=10m
LOG_MAX_FILE=5
```

Use `LOG_LEVEL=DEBUG` apenas temporariamente para investigar incidentes, pois pode aumentar volume e custo de armazenamento.

### Comandos uteis

Logs recentes da aplicacao:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 web
```

Acompanhar a stack VPS com HTTPS:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml logs -f --tail=100
```

Acompanhar a stack com Nginx:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.nginx.yml logs -f --tail=100
```

Filtrar por um request id recebido pelo usuario ou proxy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs web | grep "req-123"
```

### Observacoes de producao

- Nao registre conteudo de documentos, prompts, respostas de IA, senhas, tokens ou parametros de query nos logs operacionais.
- Para retencao longa, envie stdout/stderr para um coletor externo do provedor de nuvem; a rotacao local evita crescimento indefinido, mas nao substitui observabilidade centralizada.
- Em incidente, correlacione `X-Request-ID` entre proxy, aplicacao e relato do usuario antes de buscar dados no banco.

## Etapa 14.7 - Reverse proxy (Nginx)

Objetivo: adicionar um caminho de deploy com Nginx como reverse proxy na frente do servico FastAPI, mantendo o Uvicorn acessivel apenas localmente na stack de producao.

### Como ficou

- `docker-compose.nginx.yml` adiciona o servico `nginx`, dependente do `web` saudavel, publicando a porta `80` por padrao.
- `deploy/nginx/default.conf` faz proxy para `web:8000`, preserva headers `Host`, `X-Forwarded-*` e `X-Real-IP`, habilita gzip e aplica headers HTTP basicos.
- `.env.production.example` agora documenta `NGINX_HTTP_PORT` para trocar a porta publicada pelo proxy quando necessario.
- O `docker-compose.prod.yml` continua publicando o app em `127.0.0.1:8000` por padrao, evitando exposicao direta do Uvicorn.

### Como executar com Nginx

Crie e edite o arquivo real de producao:

```bash
cp .env.production.example .env.production
```

Defina pelo menos:

- `POSTGRES_PASSWORD`, com senha forte
- `SECRET_KEY`, com valor longo e aleatorio
- `APP_BIND_HOST=127.0.0.1`
- `NGINX_HTTP_PORT=80`, ou outra porta se houver outro proxy/load balancer na frente
- `OPENAI_API_KEY`, quando a geracao real estiver habilitada

Prepare o banco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm web python scripts/prepare_production_database.py
```

Suba a stack com Nginx:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.nginx.yml up --build -d
```

Valide:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.nginx.yml ps
curl -f http://localhost/health
```

### Observacoes de producao

- Esta configuracao Nginx entrega HTTP. Para internet publica, coloque TLS na frente com um load balancer, Cloudflare, Certbot/Let's Encrypt ou use o overlay Caddy da etapa 14.6 para HTTPS automatico.
- Se `MAX_UPLOAD_SIZE_MB` for alterado para mais de `10`, ajuste tambem `client_max_body_size` em `deploy/nginx/default.conf`.
- Nao suba `docker-compose.vps.yml` e `docker-compose.nginx.yml` ao mesmo tempo no mesmo host sem alterar portas, pois ambos tentam publicar a porta `80`.

## Etapa 14.6 - Deploy em nuvem/VPS

Objetivo: deixar um caminho repetivel para publicar o Juridico AI em um VPS ou servidor de nuvem usando Docker Compose, PostgreSQL persistente e HTTPS automatico via Caddy.

### Como ficou

- `docker-compose.prod.yml` agora publica a aplicacao em `127.0.0.1:8000` por padrao, evitando expor o Uvicorn diretamente na internet.
- `docker-compose.vps.yml` adiciona um proxy Caddy com portas `80` e `443`, certificado TLS automatico e proxy reverso para o servico `web`.
- `deploy/Caddyfile` centraliza a configuracao de dominio, compressao e headers HTTP basicos.
- `.env.production.example` documenta `APP_BIND_HOST`, `DOMAIN` e `ACME_EMAIL` para uso no servidor.
- O deploy reaproveita os volumes persistentes de Postgres, armazenamento da aplicacao e certificados do Caddy.

### Pre-requisitos do VPS

- Ubuntu/Debian atualizado ou distribuicao equivalente.
- Docker Engine e Docker Compose Plugin instalados.
- Portas `80` e `443` liberadas no firewall/security group.
- Dominio ou subdominio apontando para o IP publico do VPS por registro `A`.
- Arquivo `.env.production` criado a partir de `.env.production.example`, com senhas e chaves reais.

### Primeiro deploy

No servidor, clone o repositorio e entre na pasta do projeto:

```bash
git clone <url-do-repositorio> juridico_ai
cd juridico_ai
cp .env.production.example .env.production
```

Edite `.env.production` e defina, no minimo:

- `DOMAIN`, por exemplo `app.seudominio.com.br`
- `ACME_EMAIL`, usado pelo emissor do certificado TLS
- `POSTGRES_PASSWORD`, com senha forte
- `SECRET_KEY`, com valor longo e aleatorio
- `OPENAI_API_KEY`, quando a geracao real estiver habilitada
- `PAYMENT_*`, quando checkout e webhooks reais estiverem ativos

Prepare o banco:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm web python scripts/prepare_production_database.py
```

Suba a stack com HTTPS:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml up --build -d
```

Valide os containers e a saude da aplicacao:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml ps
curl -f https://app.seudominio.com.br/health
```

### Atualizacao de versao

Para publicar uma nova versao no VPS:

```bash
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml up --build -d
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml ps
```

Se houver mudanca de schema, rode novamente a preparacao antes de liberar trafego:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm web python scripts/prepare_production_database.py
```

### Backup rapido

Crie um dump do Postgres:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup_juridico_ai.sql
```

Restaure em um banco vazio:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < backup_juridico_ai.sql
```

Arquivos enviados e geracoes ficam no volume `juridico_ai_storage`; inclua esse volume na rotina de snapshot/backup do provedor de nuvem.

### Checklist de producao

- DNS do dominio aponta para o VPS antes de subir o Caddy.
- `.env.production` nao foi versionado.
- `APP_ENV=production`, `DEBUG=false` e `SESSION_COOKIE_SECURE=true`.
- `APP_BIND_HOST=127.0.0.1`, quando o acesso externo passa pelo Caddy.
- `/health` responde via HTTPS.
- Snapshot ou backup automatizado do banco e do volume de arquivos esta ativo.
- Logs foram verificados apos o primeiro deploy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml logs -f --tail=100
```

## Etapa 14.5 - Banco de producao

Objetivo: preparar o Juridico AI para rodar em producao com PostgreSQL, evitando SQLite em ambiente real e deixando um caminho repetivel para provisionar e validar o schema.

### Como ficou

- `psycopg[binary]` foi adicionado as dependencias para habilitar `DATABASE_URL=postgresql+psycopg://...`.
- Em producao (`APP_ENV=production`), a aplicacao agora bloqueia qualquer `DATABASE_URL` SQLite e exige PostgreSQL.
- `docker-compose.prod.yml` sobe um Postgres 16 com volume persistente e inicia a aplicacao somente depois do banco ficar saudavel.
- `.env.production.example` documenta as variaveis minimas para o banco, seguranca, armazenamento, IA, planos, pagamento e retencao.
- `scripts/prepare_production_database.py` valida que o ambiente esta em producao, cria o schema com os modelos atuais e testa a conexao.
- A engine SQLAlchemy usa `pool_pre_ping` fora de SQLite para reduzir falhas com conexoes recicladas em ambiente de servidor.

### Como preparar

Crie o arquivo real de producao a partir do exemplo:

```powershell
Copy-Item .env.production.example .env.production
```

Edite `.env.production` com valores reais para:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`, se usar um banco externo em vez do servico `db` do Compose
- `SECRET_KEY`
- `OPENAI_API_KEY`, quando a geracao real com IA estiver habilitada
- `PAYMENT_*`, quando checkout e webhooks reais forem ativados

Prepare e valide o banco antes de liberar trafego:

```powershell
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm web python scripts/prepare_production_database.py
```

Suba a stack de producao:

```powershell
docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Para usar um PostgreSQL gerenciado, defina `DATABASE_URL` apontando para o endpoint externo e mantenha `APP_ENV=production`, `DEBUG=false` e `SESSION_COOKIE_SECURE=true`.

## Etapa 14.4 - Docker Compose

Objetivo: padronizar a subida do Juridico AI com Docker Compose, mantendo configuracao por ambiente, healthcheck e persistencia fora da imagem.

### Como ficou

- `docker-compose.yml` define o projeto `juridico_ai` e o servico `web`, com build local da imagem `juridico-ai:local`.
- O arquivo `.env` e carregado quando existir, mas o Compose tambem funciona com os valores padrao do `docker-compose.yml`.
- `APP_PORT` permite trocar a porta publicada sem editar o arquivo, por exemplo `APP_PORT=8080`.
- `COMPOSE_DATABASE_URL` aponta por padrao para `sqlite:////data/juridico_ai.db`, persistido no volume `juridico_ai_data`.
- `COMPOSE_UPLOAD_DIR` e `COMPOSE_GENERATIONS_DIR` permitem ajustar os caminhos usados dentro do container; por padrao eles ficam em `/app/storage`, persistido no volume `juridico_ai_storage`.
- O healthcheck usa `/health` para validar se a aplicacao inicializou corretamente.

### Como executar

Prepare o arquivo de ambiente local, se ainda nao existir:

```powershell
Copy-Item .env.example .env
```

Suba a aplicacao:

```powershell
docker compose up --build
```

Acesse:

- Aplicacao: http://localhost:8000
- Healthcheck: http://localhost:8000/health

Para usar outra porta local:

```powershell
$env:APP_PORT="8080"
docker compose up --build
```

Para rodar em segundo plano:

```powershell
docker compose up --build -d
docker compose ps
```

### Observacoes de deploy

- O Compose foi pensado para desenvolvimento e homologacao simples com SQLite persistente em volume Docker.
- Em producao com outro banco, defina `COMPOSE_DATABASE_URL` para a URL real do ambiente.
- Para producao, mantenha `APP_ENV=production`, defina `SECRET_KEY` forte, `SESSION_COOKIE_SECURE=true` e aponte `DATABASE_URL` para o banco real do ambiente.
- O arquivo `.env` real continua fora da imagem e nao deve ser versionado.

## Etapa 14.3 - Docker

Objetivo: preparar a execucao do Juridico AI em container, mantendo a configuracao por variaveis de ambiente e evitando que dados locais entrem na imagem.

### Como ficou

- `Dockerfile` cria uma imagem Python 3.12 enxuta, instala as dependencias do `requirements.txt`, executa a aplicacao com `uvicorn` e usa usuario sem privilegios.
- `.dockerignore` reduz o contexto de build e evita copiar `.env`, banco local, uploads, caches e ambiente virtual para a imagem.
- `/health` responde um JSON simples para uso por healthchecks.

## Etapa 14.2 - Variaveis de ambiente

Objetivo: deixar explicito quais variaveis controlam o Juridico AI por ambiente e bloquear configuracoes inseguras antes do deploy.

### Como ficou

- `ENV_FILE` permite escolher o arquivo carregado pelo `python-dotenv` antes da aplicacao iniciar, por exemplo `.env`, `.env.staging` ou `.env.production`.
- `.env.example` passou a incluir `ENV_FILE` como ponto de entrada para padronizar ambientes locais, homologacao e producao.
- A validacao centralizada agora acumula erros de configuracao, facilitando corrigir varias variaveis de uma vez.
- Em producao (`APP_ENV=production`), a aplicacao exige `SECRET_KEY` real, `DATABASE_URL` diferente do SQLite local padrao e `SESSION_COOKIE_SECURE=true`.
- Limites numericos sensiveis, como tokens da OpenAI, retencao, upload, RAG e cotas de planos, agora sao validados contra valores nulos ou negativos.

### Arquivos de ambiente sugeridos

Use `.env` para desenvolvimento local. Para homologacao e producao, defina `ENV_FILE` no processo antes de iniciar a aplicacao:

```powershell
$env:ENV_FILE=".env.production"
uvicorn app.main:app
```

O arquivo real de ambiente nao deve ser versionado. Mantenha apenas `.env.example` como referencia publica.

### Checklist minimo de producao

- `APP_ENV=production`
- `ENV_FILE=.env.production`, quando houver arquivo separado no servidor
- `DEBUG=false`
- `DATABASE_URL` apontando para o banco real
- `SECRET_KEY` forte e exclusiva do ambiente
- `SESSION_COOKIE_SECURE=true`
- `UPLOAD_DIR` e `GENERATIONS_DIR` apontando para armazenamento persistente
- `OPENAI_API_KEY`, quando a geracao real com IA estiver habilitada
- `PAYMENT_*`, quando checkout e webhooks reais forem ativados

## Etapa 14.1 - Centralizar configuracoes

Objetivo: preparar o Juridico AI para sair do ambiente local, concentrando configuracoes de aplicacao, seguranca, banco, armazenamento, IA, RAG, planos, pagamento e retencao em uma unica camada.

### Como ficou

- `app/core/config.py` passou a expor `AppSettings`, um objeto tipado carregado por ambiente.
- As constantes antigas continuam disponiveis no mesmo modulo para manter compatibilidade com o restante da aplicacao e com os testes existentes.
- `.env.example` documenta as variaveis esperadas para local, homologacao e producao.
- Em producao (`APP_ENV=production`), a aplicacao bloqueia o uso de `SECRET_KEY=changeme`.
- `DEBUG` e `SESSION_COOKIE_SECURE` agora podem ser controlados por ambiente, com defaults seguros para producao.
- Os diretorios de upload e geracoes continuam sendo criados automaticamente a partir de `UPLOAD_DIR` e `GENERATIONS_DIR`.

### Variaveis essenciais para deploy

- `APP_ENV=production`
- `DEBUG=false`
- `DATABASE_URL`
- `SECRET_KEY`
- `SESSION_COOKIE_SECURE=true`
- `UPLOAD_DIR`
- `GENERATIONS_DIR`
- `OPENAI_API_KEY`, quando a geracao com IA real estiver habilitada
- `PAYMENT_CHECKOUT_URL` e `PAYMENT_WEBHOOK_SECRET`, quando o pagamento real for ativado

## Etapa 12.8 - Estrategia comercial inicial

Objetivo: iniciar a validacao comercial do Juridico AI com uma oferta simples, mensuravel e compativel com o mercado juridico.

### Posicionamento

Juridico AI deve ser apresentado como uma ferramenta de produtividade para advogados e pequenos escritorios que precisam gerar primeiras versoes de pecas, documentos e textos juridicos com mais velocidade, mantendo revisao humana obrigatoria.

Mensagem central:

> Ganhe tempo na primeira versao da sua minuta juridica, sem abrir mao da revisao profissional.

O produto nao deve prometer resultado juridico, substituicao do advogado ou captacao automatica de clientes.

### Publico inicial

Prioridade 1:

- Advogados autonomos e pequenos escritorios com alta recorrencia de documentos.
- Profissionais que ja usam modelos prontos, IA generica ou editores manuais, mas querem um fluxo mais organizado.
- Usuarios que precisam reaproveitar documentos, perfis de escrita e geracoes anteriores.

Prioridade 2:

- Escritorios boutique que produzem minutas repetitivas por area.
- Equipes juridicas pequenas que ainda nao tem ferramenta robusta de legal ops.

### Oferta inicial

Manter dois planos no lancamento:

- Plano gratuito: porta de entrada, com limite diario de geracoes e limite reduzido de perfis de escrita.
- Plano Pro: plano pago para uso recorrente, com limite mensal ampliado, mais perfis de escrita e recursos premium.

Preco sugerido para validacao:

- Pro mensal inicial: R$ 97 a R$ 149 por usuario/mes.
- Oferta de validacao: desconto para os primeiros clientes em troca de feedback estruturado.

Antes de fixar preco definitivo, validar:

- Quanto tempo o produto economiza por documento.
- Quantas geracoes por mes o usuario realmente usa.
- Se o maior valor percebido esta em geracao, organizacao de documentos, perfis de escrita ou reutilizacao de historico.

### Canais iniciais

Comecar com canais de baixa complexidade:

- Conteudo educativo para advogados, com foco em produtividade e uso responsavel de IA.
- Demonstracoes individuais para advogados conhecidos e pequenos escritorios.
- Lista de espera ou formulario simples para captar interessados.
- Parcerias com comunidades juridicas, eventos locais e grupos de inovacao juridica.
- Onboarding manual dos primeiros clientes pagos para aprender objecoes e casos de uso.

Todo conteudo comercial deve ser informativo, moderado e sem promessa de resultado. Para comunicacao voltada a advogados, observar as regras do Provimento OAB 205/2021 sobre marketing juridico.

### Funil comercial inicial

1. Atrair: conteudos curtos sobre produtividade juridica, revisao de minutas e organizacao de pecas.
2. Converter: cadastro gratuito com CTA para testar geracoes e perfis de escrita.
3. Ativar: orientar o usuario a criar uma primeira geracao real e um perfil de escrita.
4. Monetizar: oferecer upgrade quando o limite gratuito for atingido ou quando o usuario demonstrar uso recorrente.
5. Reter: acompanhar uso mensal, coletar feedback e priorizar melhorias que reduzam retrabalho.

### Metricas para acompanhar

- Cadastros por semana.
- Usuarios que geram pelo menos 1 documento.
- Usuarios que voltam em ate 7 dias.
- Geracoes por usuario ativo.
- Taxa de usuarios gratuitos que atingem limite.
- Conversao de gratuito para Pro.
- Cancelamentos e motivo de cancelamento.
- Tempo economizado estimado por geracao, coletado por feedback.

### Regras comerciais para a proxima etapa

- Nao liberar pagamento real antes de definir provedor, webhook e confirmacao de assinatura.
- Nao mudar o plano do usuario apenas pelo retorno visual de sucesso; a troca para Pro deve depender de confirmacao confiavel do provedor.
- Criar uma pagina simples de termos de uso antes de venda real.
- Adicionar aviso claro de que o conteudo gerado exige revisao profissional.
- Registrar eventos basicos de checkout iniciado, pagamento confirmado e plano alterado.

### Hipoteses de validacao

- Hipotese A: advogados pagam pelo produto se ele reduzir tempo de primeira minuta em casos recorrentes.
- Hipotese B: perfis de escrita aumentam valor percebido porque aproximam a geracao do estilo do escritorio.
- Hipotese C: o limite gratuito ajuda a demonstrar valor sem consumir custo operacional excessivo.
- Hipotese D: o melhor gatilho de upgrade e atingir limite de geracoes, nao uma pagina comercial isolada.

### Referencias

- AB2L: pagina institucional sobre o ecossistema brasileiro de inovacao juridica, com categorias como lawtechs, legaltechs, escritorios de advocacia, departamentos juridicos e empresas: https://ab2l.org.br/
- OAB Provimento 205/2021: regras de publicidade e informacao na advocacia: https://eticaedisciplina.oab.org.br/assets/docs/Provimento%20n.%20205.2021%20-%20Publicidade.pdf

## Etapa 13.8 - Preparacao para LGPD

Objetivo: preparar controles tecnicos iniciais para tratamento de dados pessoais no Juridico AI, com foco em inventario, acesso, portabilidade, retencao e anonimizacao administrativa.

### Controles implementados

- Inventario LGPD no painel admin com entidades tratadas, categorias de dados, finalidade operacional e retencao esperada.
- Exportacao estruturada dos dados do titular por usuario, incluindo conta, documentos, geracoes, perfis de escrita e auditorias vinculadas.
- Anonimizacao administrativa do titular, com desativacao da conta, remocao de identificadores diretos, limpeza de conteudos sensiveis, exclusao de arquivos fisicos quando estiverem no armazenamento permitido e quarentena dos registros tratados.
- Reducao dos payloads de auditoria vinculados ao titular anonimizado, preservando rastreabilidade minima do ato sem manter snapshots pessoais.
- Registro auditavel das acoes administrativas de exportacao e anonimizacao LGPD.

### Limites assumidos

- A anonimizacao nao substitui uma politica juridica formal de privacidade, termos de uso ou avaliacao de base legal.
- Auditorias antigas seguem retidas de forma minimizada conforme a politica de retencao configurada.
- Arquivos fora do armazenamento permitido nao sao apagados automaticamente; o relatorio marca esses casos como bloqueados.
