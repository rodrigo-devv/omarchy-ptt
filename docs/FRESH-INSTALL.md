# Incorporar ao seu pack de fresh install

Guarde uma distribuição versionada do Omarchy PTT e um perfil, por exemplo:

```text
meu-pack/
├── apps/
│   └── omarchy-ptt-0.1.0-beta.3/
└── profiles/
    └── ptt.json
```

Copie `profiles/mouse9.json` para o perfil do pack ou exporte suas preferências
com `omarchy-ptt export-profile`. Esses arquivos podem ser versionados; não
inclua o registro local de instalação, backups ou dados do Discord.

Depois de instalar Omarchy e criar o usuário do desktop, execute **como esse
usuário**:

```bash
./apps/omarchy-ptt-0.1.0-beta.3/install.sh \
  --install-deps --profile ./profiles/ptt.json
```

O instalador reconhece quando ainda não existe sessão Hyprland e prepara o
serviço para o primeiro login. Para deixar essa intenção explícita, acrescente
`--defer`. Dentro da sessão gráfica, omita essa opção para validar e ativar.

O modo offline requer Omarchy já instalado com configuração Lua no diretório
do usuário e os headers correspondentes ao Hyprland instalado. Ele não é um
instalador de sistema operacional nem uma etapa para rodar como root no chroot.

No primeiro login, abra o Discord pelo menu, entre na conta e configure o PTT
com o botão do perfil. Launcher, serviço, regra de foco e recuperação de
soltura já estarão preparados. Execute `omarchy-ptt doctor` e valide a chamada.

Para reaplicar o pack em uma máquina já configurada, execute o mesmo comando.
O include não é duplicado e os arquivos pessoais são preservados. Uma nova
distribuição atualiza os componentes; um perfil explícito reaplica as
preferências do pack. Sem `--profile`, o perfil instalado é mantido.

Não rode uma atualização automaticamente com o PTT pressionado: a reinstalação
libera o hold ao reiniciar a ponte. O instalador não encerra chamadas do Discord.

Comportamento diante de conflitos: um bind existente para o botão é recusado
durante a instalação em sessão. No modo offline, bindings gerados dinamicamente
não podem ser consultados; revise o botão antes de preparar um desktop com
atalhos próprios. Em um fresh install padrão, o perfil Mouse9 é o ponto de
partida. A solução local anterior precisa de `--migrate`.

Para homologar uma máquina nova, preencha [FRESH-INSTALL-CHECKLIST.md](FRESH-INSTALL-CHECKLIST.md).
