# Publicar a beta no GitHub

Destino proposto: `rodrigo-devv/omarchy-ptt`, repositório público independente.
A intenção de publicar foi autorizada durante a criação da versão reutilizável.
A revisão automática exige confirmação específica do destino e do conteúdo
público antes de executar o script. Nada foi enviado ao GitHub ainda.

O repositório local contém apenas fonte, testes, perfis, documentação e a
captura da janela de configuração em ambiente isolado. Dados do Discord,
backups da máquina, manifest local, binários `.so` e arquivos de cache não
entram no commit nem no arquivo distribuído.

Com a conta correta autenticada no GitHub CLI:

```bash
gh auth login -h github.com
./tools/publish-beta.sh
```

O script verifica conta, alterações não commitadas e destino de origin; cria
o repositório público se ausente, envia main e a tag, e cria uma prerelease
com arquivo fonte e SHA-256. Não força push nem substitui releases existentes.
Depois confira a execução dos testes no GitHub Actions.

Download: arquivo da release, seguido da verificação do checksum. Para instalar,
extraia e rode `./install.sh --install-deps` como usuário normal. Evite instruções
que executam diretamente conteúdo remoto com `curl | sh`.

Antes de anunciar suporte amplo, execute a demonstração em uma instalação
limpa completa e confirme o teste de voz. Os limites e as pendências atuais
estão em `COMPATIBILITY.md` e `VALIDATION.md`.
