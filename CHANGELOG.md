# Changelog

## 0.1.0-beta.2 — 2026-10-11

- Seletor gráfico de botão com confirmação após soltura e cancelamento.
- Comando configure e entrada Configuração PTT Discord no menu de aplicações.
- Importação local somente de leitura do atalho PTT existente no Discord.
- Primeira instalação detecta atalho; atualização preserva preferências.
- Validação do banco LevelDB, sequência, tombstones, manifest e checksums.
- Testes de importação, prioridade, rejeição e janela real num Xvfb isolado.


## 0.1.0-beta.1 — 2026-10-11

- Perfis portáteis para Mouse9 e Mouse8.
- CLI setup/status/doctor/remove/export-profile/launch-discord.
- Instalação por usuário com suporte XDG, include único, backups e rollback.
- Preparação de fresh install sem sessão gráfica, com ativação no próximo login.
- Instalação opcional de dependências via pacman.
- Migração explícita da integração local anterior.
- Ponte persistente e observador de soltura com botão configurável.
- Cache de compilação e proteção de ABI para a extensão.
- Documentação em português/inglês e exemplo para packs.
- Testes de controle, Lua, C++ e instalação offline isolada.
