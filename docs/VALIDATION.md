# Validação da versão 0.1.0-beta.3

Data: 11/10/2026. Headers e parser locais: Hyprland 0.56.2.

Executado:

```bash
OMARCHY_PTT_NATIVE_TESTS=1 OMARCHY_PTT_GUI_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -v
bash -n install.sh bin/omarchy-ptt examples/fresh-install.sh
```

Resultado: **37 testes passaram** (incluindo `OMARCHY_PTT_GUI_TESTS=1`). A suíte cobre:

- Importação da chave local, Snappy, manifest, sequência e exclusões, checksums,
  formato incompatível, ambiguidade, prioridade de perfis e cancelamento.
- Janela real do seletor: press, release, confirmação e cancelamento.
- Hold de PTT, release, promoção de rota nativa, deduplicação, reload e saída.
- Instalação nova, repetição sem duplicação, perfil alternativo e remoção.
- Preservação de MIME/launcher, arquivos originais e edições pessoais posteriores.
- Migração explícita e restauração da integração local anterior.
- Rollback após falha de validação de configuração ou prontidão da ponte.
- Atualização com recuperação do binário anterior e manutenção do registro de
  componentes antigos para remoção posterior.
- Recusa de conflitos, perfis inválidos, includes modificados e symlinks.
- Callbacks Lua reais com troca de workspace, bind perdido, botão diferente,
  próximo clique e fallback sem extensão.
- Extensão C++ de produção com sinais reais do Hyprutils e compositor simulado:
  guarda ABI, filtro de solturas, código físico e descarregamento limpo.
- Instalação/remoção offline reais em diretórios XDG temporários, inclusive
  caminhos com espaços, compilação da extensão, parser real do Hyprland,
  validação de launcher e criação/remoção do link de inicialização systemd.
- Execução de `--help`, `--version` e `doctor --json` pelo launcher instalado
  no ambiente temporário.

A unit gerada passou em `systemd-analyze --user verify` como verificação
separada; esse comando não instala nem inicia o serviço.

Os testes não carregam plugins na sessão ativa. O teste gráfico usa Xvfb em
um display alto explicitamente separado e eventos restritos a esse servidor.
Não gera eventos de mouse ou áudio no desktop do usuário.

Também executado na sessão real:

- Importação do atalho atual: Mouse9 / Linux 276, sem escrever no Discord.
- Migração da solução local anterior para a beta. Serviço antigo desativado.
- `doctor --json`: extensão carregada, serviço habilitado/ativo, ponte pronta,
  Discord XWayland, `configerrors` vazio.
- Mudança real do perfil Mouse9 → Mouse8 → importação de Mouse9. Ponte e
  serviço prontos em ambas as configurações; foco preservado. Não foram
  simulados cliques na sessão real; o botão do Discord continua Mouse9.

Durante a validação, a sondagem automática de display do Xvfb interferiu no
caminho do socket XWayland. O listener original permaneceu ativo; a conexão
foi restaurada sem fechar aplicações. O teste foi corrigido para nunca sondar
o display do desktop. A tentativa de migração fez rollback; a nova tentativa
concluiu depois da correção. Esse incidente pertence ao teste de desenvolvimento,
que não roda durante instalação do pacote.

Evidência manual: a solução original foi confirmada pelo usuário com Discord
em XWayland, foco preservado e soltura após mudar de workspace. Após a correção beta.3, o usuário confirmou que o comportamento está
funcionando bem nesta máquina. Ainda falta validar uma instalação completa
em outra máquina ou VM recém-instalada; a versão permanece beta por esse motivo.


## Correção beta.3

Durante a investigação do salto de workspace, o Mouse9 só possuía os dois
bindings do PTT. A ponte estava pronta. Uma observação passiva do X11 identificou
pedidos `_NET_ACTIVE_WINDOW` de um aplicativo Wine em outro workspace, enquanto
a regra existente protegia somente o Discord. Esses pedidos são uma explicação provável para o salto. A confirmação do
usuário demonstra que a proteção resolveu o comportamento relatado, sem
afirmar que todos os caminhos internos do aplicativo foram rastreados.

A correção habilita uma regra temporária `focus_on_activate=false` para XWayland
antes de encaminhar PTT nativo/sintético e a desabilita 200 ms após o release.
Ela não força retorno ao workspace anterior nem bloqueia mudanças manuais.
Regra e timer são reutilizados; novo hold cancela a desativação pendente; reload
e shutdown limpam a proteção. O teste Lua exercita esse ciclo completo.

O usuário confirmou: “Está funcionando bem agora”, após instalar a beta.3,
e autorizou subir a correção ao repositório. A release beta.2 continua imutável.
A suíte completa voltou a passar nos 37 testes, incluindo a proteção de foco.
