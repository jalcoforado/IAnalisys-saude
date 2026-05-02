# Guia Prático — Como trabalhar com o Claude Code

## Antes de tudo

1. Abra o VS Code na pasta do projeto (`c:\projetos\pedro\ianalisys-saude`)
2. Abra o Docker Desktop e espere ele iniciar
3. Abra o terminal do VS Code (Ctrl + `)
4. Suba os containers:
   ```bash
   docker-compose up -d --build
   ```

---

## Como iniciar uma nova conversa com o Claude Code

### Passo 1: Abrir o Claude Code
No terminal do VS Code, dentro da pasta do projeto, digite:
```
claude
```

### Passo 2: Primeira mensagem
Sempre comece com:
```
consulte a memória e o roadmap (docs/07_ROADMAP.md), vamos continuar de onde paramos
```

O Claude vai:
- Ler a memória (sabe o que já foi feito)
- Ler o roadmap (sabe o que falta)
- Te dizer onde parou e o que sugere fazer

### Passo 3: Confirme o que quer fazer
O Claude vai sugerir próximos passos. Você escolhe:
- "sim, vamos com isso" — ele implementa
- "não, quero fazer X primeiro" — ele muda de direção
- "me explica o que isso faz" — ele explica antes de fazer

---

## Frases úteis para conversar com o Claude

| Situação | O que dizer |
|---|---|
| Começar o dia | "consulte a memória e o roadmap, vamos continuar" |
| Parar por hoje | "atualize a memória e a documentação, vamos parar por aqui" |
| Não entendeu algo | "me explica isso de forma simples" |
| Deu erro | cole o erro e diga "deu esse erro" |
| Ver o que foi feito | "me mostre o status do projeto" |
| Testar algo | "testa isso pra mim" |
| Quer ver código | "me mostra o arquivo X" |
| Não gostou | "não era isso, eu quero Y" |
| Quer commitar | "faz o commit e push" |

---

## Regras de ouro

1. **Sempre diga onde parou** — O Claude não lembra da conversa anterior automaticamente, mas lembra da memória
2. **Não precisa saber programar** — Descreva o que quer em português, o Claude faz o código
3. **Peça confirmação** — Se não entendeu o que o Claude vai fazer, pergunte antes de aprovar
4. **Erro é normal** — Cole o erro no chat, o Claude resolve
5. **Uma coisa de cada vez** — Não peça 5 coisas ao mesmo tempo. Peça uma, espere terminar, depois peça a próxima

---

## Comandos do terminal que você vai usar

```bash
# Subir o projeto
docker-compose up -d --build

# Ver se está rodando
docker-compose ps

# Ver logs do backend (se algo der errado)
docker-compose logs backend

# Parar tudo
docker-compose down

# Commitar (o Claude faz isso por você, mas se precisar)
git add . && git commit -m "mensagem" && git push
```

---

## Endereços quando o projeto está rodando

| O que | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Health check | http://localhost:8000/api/v1/health |
| Documentação API | http://localhost:8000/docs |

Login de teste: `admin@parente.com` / `admin123`

---

## Se o Claude "se perder"

Se sentir que o Claude não sabe onde está, diga:
```
leia docs/07_ROADMAP.md e a memória do projeto, e me diga o estado atual
```

Ele vai se reorientar.
