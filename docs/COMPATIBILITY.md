# Compatibilidade

| Ambiente | Evidência |
| --- | --- |
| Omarchy 4.0.0.alpha, Hyprland 0.56.2, Discord oficial stable | Solução original confirmada manualmente pelo usuário |
| Pacote reutilizável, mesmos headers e parser | Testes isolados; ver `VALIDATION.md` |
| Outra máquina com Omarchy Lua | Precisa de validação funcional; instalação checa headers e parser |
| Hyprland com configuração `.conf` antiga | Não suportado nesta versão |
| Discord Flatpak, Canary, PTB, Vesktop | Não suportado nesta versão |

Os códigos de botões variam entre Linux e X11. Os perfis incluídos usam
`BTN_EXTRA`/276 → Mouse9 e `BTN_SIDE`/275 → Mouse8. Para outros botões laterais,
o seletor reconhece Mouse8–Mouse12 no mapeamento XWayland padrão. Se houver
remapeamento, configure ambos os códigos explicitamente após identificá-los;
não derive o código apenas do nome comercial do botão.

Dependências: `hyprland` com headers/pkg-config, `gcc`, `pkgconf`,
`python-xlib`, `discord`, `desktop-file-utils` e `systemd`. A integração
pressupõe os helpers Lua `o.bind` e `o.window` do Omarchy, XWayland/XTEST e uma
sessão gráfica systemd de usuário. Compilar para headers corretos não prova
compatibilidade funcional com futuras versões da API; testes são necessários.

A extensão verifica o hash ABI antes de registrar listeners. O cache separa
commit, código fonte, flags, compilador e versões de dependências. O serviço
recompila ao detectar uma nova identidade. Se a sessão ainda usa um compositor
anterior à atualização dos headers, reinicie a sessão antes de tentar novamente.

Uma falha na compilação inicial interrompe setup antes de modificar a
configuração do desktop. Falha de carregamento durante instalação em sessão
causa rollback. Falha no carregamento em um próximo login mantém o PTT comum
com liberação ao trocar de workspace; a continuidade do hold estará reduzida.

Janela do Discord na bandeja sem janela de destino, jogos com captura de
entrada, teclas modificadoras, dois monitores, lock e reconexão do mouse são
casos que precisam de teste manual no equipamento de destino.

Importação: cliente stable em `$XDG_CONFIG_HOME/discord/Local Storage/leveldb`,
um PTT ativo em `keybinds`, Linux/X11, Mouse8–Mouse12 sem modificadores.
Snappy (`libsnappy`) é necessário para blocos comprimidos; se não estiver
disponível, a seleção manual continua disponível. Não importa outros clientes.
