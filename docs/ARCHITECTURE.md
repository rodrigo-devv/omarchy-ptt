# Arquitetura

O include único no `hyprland.lua` carrega `ptt.lua`, gerado do perfil.
Ele mantém a rota do pressionamento e emite eventos personalizados na conexão
IPC ordenada do Hyprland. A ponte Python mantém um único processo e injeta
Mouse9 (ou o botão escolhido) no XWayland usando XTEST quando necessário.
Com um cliente XWayland em foco, o botão físico permanece nativo; um hold que
atravessa foco/workspace é promovido à ponte. Release é deduplicado.

A extensão C++ usa o sinal de entrada anterior à checagem que perde releases
em Hyprland 0.56.2. Ela observa solturas de botões laterais e inclui o código
físico no evento customizado; Lua filtra o botão configurado. Não cancela os
eventos nem altera o tracker interno de botões do compositor.

O serviço systemd de usuário carrega a extensão antes de iniciar a ponte.
O heartbeat inclui assinatura da sessão e impressão do perfil. Isso evita
que uma configuração atualizada use uma ponte ainda configurada para outro
botão. Ao reiniciar depois de falha, uma soltura de recuperação usa o botão
anterior registrado no estado. Nenhum pressionamento é gerado na inicialização.

Reload, parada do processo e shutdown liberam o hold. Sem a extensão, Lua
libera o hold na mudança de workspace. O botão é passado normalmente quando
o Discord ou a ponte estão indisponíveis. A regra `focus_on_activate = false`
é específica ao Discord e mantém a seleção manual.

## Instalação

Pré-checagens, resolução de conflito e compilação precedem a alteração dos
arquivos. Escritas são atômicas. O registro guarda conteúdo e permissões
originais, mais hashes do conteúdo instalado. Reinstalação conserva os
originais da primeira instalação. Falhas restauram arquivos e estado dos
serviços; dependências instaladas e cache não são removidos.

Na remoção, arquivos sem alterações voltam ao estado original. Edições
posteriores são preservadas. O include gerenciado pode ser removido preservando
mudanças fora do bloco; se o próprio bloco foi editado, a remoção é interrompida.

## Referências

- [Regras de janela](https://wiki.hypr.land/Configuring/Basics/Window-Rules/)
- [Global binds e ressalvas XWayland](https://wiki.hypr.land/configuring/core/binds/globals/)
- [Hyprland IPC](https://wiki.hypr.land/IPC/)
- [InputManager 0.56.2](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/managers/input/InputManager.cpp)
- [Monitor 0.56.2](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/output/Monitor.cpp)
- [Plugins](https://wiki.hypr.land/Plugins/Using-Plugins/)


## Preferências e importação

`configure` recebe o botão numa janela X11 focada, aguarda release e confirmação,
verifica conflitos e reaplica a instalação transacional. Nenhum listener global
ou acesso a dispositivos de input é usado para selecionar o botão.

Na primeira instalação sem perfil, `discord_settings` consulta apenas o valor
`keybinds` da origem `https://discord.com` no armazenamento local. O leitor segue
CURRENT/MANIFEST, os arquivos de tabela vivos e logs, usa a maior sequência,
respeita exclusões e verifica CRC32C. Blocos Snappy usam a biblioteca local.
Não abre o banco via API mutável, não copia o diretório e não exporta os dados.
Mudança de manifest, arquivo parcial/corrompido, atalho ambíguo ou formato não
suportado cancela a importação. O seletor é o fallback no desktop.

O formato de atalhos do Discord é interno. Um único atalho PTT mouse Linux/X11
sem modificadores é aceito. Importar o atalho não determina o modo de entrada
da conta nem habilita PTT numa conta nova. Atualizações preservam o perfil
existente; uma nova importação é explícita com `configure --from-discord`.
