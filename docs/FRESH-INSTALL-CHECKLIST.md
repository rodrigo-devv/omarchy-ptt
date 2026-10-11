# Validação numa instalação limpa

Use outra máquina ou VM com Omarchy Lua. A instalação existente não precisa
ser removida para esse teste. Execute como o usuário normal do desktop.

## Instalar

Baixe o pacote e o checksum da release beta.3, confira o SHA-256, extraia e rode:

```bash
./install.sh --install-deps --profile profiles/mouse9.json
```

Se for preparar antes da sessão gráfica, acrescente `--defer`. Em uma conta
Discord nova, entre na conta, selecione Push-to-Talk e grave o botão do perfil.
Em uma conta com atalho salvo, omita `--profile` para testar a importação.

## Registrar resultados

| Verificação | Resultado |
| --- | --- |
| Versões de Omarchy, Hyprland e Discord | Preencher |
| Mouse e botão escolhidos | Preencher |
| Instalação sem configuração anterior de PTT | Pendente |
| Importação de atalho existente, quando disponível | Pendente |
| PTT no próprio Discord/workspace | Pendente |
| PTT em aplicativo Wayland | Pendente |
| PTT em aplicativo XWayland | Pendente |
| Segurar, trocar workspace e soltar | Pendente |
| Foco permanece sem saltos | Pendente |
| Troca de botão pelo menu e gravação no Discord | Pendente |
| Segundo login: serviço inicia e PTT funciona | Pendente |
| Reinstalação não duplica include | Pendente |
| Remoção restaura o estado anterior | Pendente |

Execute `omarchy-ptt doctor --json` e `hyprctl configerrors`. Um diagnóstico
pronto confirma os componentes; a chamada confirma o comportamento de áudio.

Depois da remoção, confirme o launcher anterior e a ausência do serviço ativo.
Para finalizar o ambiente com o PTT instalado, instale outra vez com o perfil.
Não inclua bancos do Discord, backups ou credenciais no relatório compartilhado.
