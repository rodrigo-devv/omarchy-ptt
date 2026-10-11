# Omarchy PTT

Push-to-talk do Discord entre workspaces, preservando o foco e a soltura do
botão após trocar de workspace. Instalação por usuário, perfil portátil e
inicialização automática com a sessão gráfica.

**Versão: 0.1.0-beta.2.** Baseada na solução funcional validada no Omarchy
4.0.0.alpha com Hyprland 0.56.2 e o cliente oficial stable do Discord.
A distribuição reutilizável é beta: ainda não há validação em outras máquinas.

[English](README.en.md) · [Fresh install](docs/FRESH-INSTALL.md) ·
[Compatibilidade](docs/COMPATIBILITY.md) · [Arquitetura](docs/ARCHITECTURE.md) ·
[Demonstração](docs/DEMO.md) · [Validação](docs/VALIDATION.md)

## Instalação

Extraia a distribuição, abra um terminal no diretório e execute **como seu
usuário normal**:

```bash
./install.sh --install-deps
```

Na primeira instalação, o instalador tenta importar um único atalho PTT
compatível salvo no Discord. Se não encontrar, abre o seletor de botão.
Um perfil explícito tem prioridade; atualizações preservam o perfil instalado.
Use `--no-detect` para escolher o padrão Mouse9 (`mouse:276`). O instalador usa sudo somente se precisar instalar pacotes ausentes
pelo pacman. Não execute o instalador inteiro com sudo.

O instalador prepara launcher X11, ponte, extensão de soltura, serviço e regra
de foco. Dentro do Hyprland, valida e ativa a integração; fora da sessão
gráfica, prepara a inicialização no próximo login. Não encerra o Discord nem
interrompe chamadas automaticamente.

No primeiro uso de uma conta/instalação nova:

1. Abra o Discord pelo menu de aplicações. Se já estiver aberto em Wayland,
   encerre-o completamente antes de reabrir.
2. Em **Voz e Vídeo → Modo de entrada → Push-to-Talk**, grave o botão escolhido, se ainda não estiver configurado.
3. Segure o botão, mude de workspace e solte. A voz deve parar ao soltar e o
   foco deve continuar na aplicação que você estava usando.

A importação aproveita o atalho existente; o modo de voz precisa estar em
Push-to-Talk. Em uma conta nova, ou ao trocar o botão pelo seletor, grave esse
botão também no Discord. O projeto não altera o armazenamento do Discord.
O leitor processa os blocos locais para localizar apenas a chave `keybinds`;
não exporta, imprime ou copia o banco nem acessa a conta pela rede.
PTT requer que a janela do cliente esteja aberta em algum workspace.

Se `~/.local/bin` não estiver no PATH, use `~/.local/bin/omarchy-ptt` nos
comandos abaixo.

## Configuração PTT Discord

Procure **Configuração PTT Discord** no menu de aplicações ou execute:

```bash
omarchy-ptt configure                 # Aperte, solte e confirme outro botão
omarchy-ptt configure --from-discord  # Importar o atalho atual do Discord
omarchy-ptt detect-discord            # Apenas consultar, sem alterar nada
./install.sh --capture                # Escolher durante a primeira instalação
```

O seletor suporta Mouse8–Mouse12 no mapeamento Linux/XWayland padrão. Cancela
com Esc. A aplicação verifica conflitos antes de salvar, reinicia a ponte e
valida o Hyprland; falhas restauram o estado anterior. Mudanças no Discord
podem ser importadas novamente quando quiser, sem serviço de monitoramento.
A importação não configura antecipadamente uma conta que ainda não tem PTT.

A chave interna do Discord é um formato não documentado e pode mudar. Atalhos
com teclado/modificadores, múltiplos PTT ativos e formatos desconhecidos são
recusados. Mouses com remapeamento precisam de um perfil com ambos os códigos.
Fora da sessão gráfica, informe `--profile` ou `--no-detect` se não existir
atalho importável. A opção `--from-discord` exige sucesso e nunca substitui
silenciosamente um atalho não suportado.

## Perfis e fresh install

```bash
# Configuração portátil incluída no pacote
./install.sh --install-deps --profile profiles/mouse9.json

# Preparar explicitamente fora da sessão gráfica
./install.sh --install-deps --defer --profile profiles/mouse9.json

# Outro botão lateral: Mouse8 / mouse:275
./install.sh --profile profiles/mouse8.json

# Exportar somente as preferências, para levar ao seu pack
omarchy-ptt export-profile ./meu-pack/ptt.json
```

O perfil contém botão e cliente, sem nome de usuário, caminhos ou dados da
conta. O [exemplo de bootstrap](examples/fresh-install.sh) pode ser incorporado
ao seu pack depois da instalação do Omarchy. O procedimento completo está
em [FRESH-INSTALL.md](docs/FRESH-INSTALL.md).

## Atualização, diagnóstico e remoção

```bash
omarchy-ptt status
omarchy-ptt doctor --json
journalctl --user -u omarchy-ptt.service -n 50 --no-pager

# Avaliar arquivos e conflitos sem instalar, compilar ou baixar pacotes
./install.sh --dry-run

# Atualizar usando uma nova distribuição: preserva o perfil existente
./install.sh

# Remover e restaurar os arquivos anteriores
omarchy-ptt remove
```

Instalar novamente não duplica o bloco de configuração. Arquivos anteriores
são registrados em `~/.local/state/omarchy-ptt/installation.json`, ou no
diretório definido por `XDG_STATE_HOME`. Se houver falha durante a instalação,
as alterações de arquivos e os estados anteriores dos serviços são revertidos.
Pacotes instalados com `--install-deps` e o cache da compilação permanecem.

Na remoção, mudanças pessoais posteriores são preservadas. Se um arquivo
gerenciado tiver sido editado, o comando informa seu caminho e conserva o
registro de recuperação. Um bloco de inclusão modificado precisa ser
resolvido antes de remover os componentes referenciados por ele.

Links simbólicos nos arquivos que seriam substituídos são recusados, para
preservar repositórios de dotfiles; adapte o include no seu gerenciador de
dotfiles antes de instalar nesses ambientes.

## Migração da integração local anterior

Se você usa os blocos `discord-ptt-mouse9` / `discord-ptt-focus` da solução
original desta sessão:

```bash
./install.sh --migrate
```

A migração é explícita, salva os originais e substitui esses blocos por um
include único. Desabilita o serviço anterior para evitar duas pontes. A
remoção restaura a configuração anterior e o estado habilitado do serviço.
Os scripts antigos ficam preservados.

## Compatibilidade e limites

- Destino inicial: Omarchy com configuração **Lua** e Discord oficial stable.
  Configurações `.conf` antigas não são convertidas por esta versão.
- A extensão é compilada com os headers da máquina de destino. Um build
  incompatível é recusado antes de alterar a configuração do desktop.
- Após uma atualização, o serviço recompila quando os headers correspondem
  ao compositor em execução. Pode ser necessário reiniciar a sessão.
- Se a extensão não puder carregar no próximo login, o serviço mantém o PTT
  comum; nesse modo reduzido, trocar de workspace encerra o hold. `doctor`
  informa essa condição.
- XTEST atua no XWayland: outro aplicativo X11 com o mesmo botão pode receber
  a entrada. Valide o comportamento no seu jogo, com seus modificadores.
- Não lê `/dev/input`, não adiciona usuários ao grupo `input` e não altera
  arquivos do Omarchy em `/usr/share/omarchy`.

## Desenvolvimento

Sem dependências Python adicionais para a suíte de testes de controle:

```bash
/usr/bin/python3 -m unittest discover -s tests -v

# Integração local: compilador, headers Hyprland, Lua, Xvfb e Omarchy necessários.
# Usa diretórios temporários e Xvfb em display separado; não injeta input no desktop.
OMARCHY_PTT_NATIVE_TESTS=1 OMARCHY_PTT_GUI_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -v

# Gerar distribuição fonte e checksum
/usr/bin/python3 tools/build-release.py
```

O runtime usa o Python do sistema e `python-xlib`. Não redistribua o `.so`
compilado em uma máquina como se fosse compatível com todas as outras.

## Licença e relação com os projetos

MIT. Projeto comunitário independente; não é uma ferramenta oficial do
Omarchy, Hyprland ou Discord. As dependências mantêm suas próprias licenças.
