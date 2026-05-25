# Consulta do ultimo holerite no SOU CAIXA

Programa em Python para abrir o SOU CAIXA no navegador, permitir login manual e informar qual e o ultimo holerite disponivel para consulta.

Esta versao nao usa Playwright. Ela usa Selenium com Microsoft Edge por padrao.

## Arquivos

- `holerite_program.py`: programa principal.
- `requirements.txt`: dependencia Python.
- `sample_holerites.html`: arquivo local para testar a extracao sem entrar no SOU CAIXA.

## Como testar no VS Code

1. Abra esta pasta no VS Code.
2. No terminal do VS Code, crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instale a dependencia:

```powershell
pip install -r requirements.txt
```

4. Teste primeiro com o HTML local:

```powershell
python .\holerite_program.py --html .\sample_holerites.html
```

Tambem deixei configuracoes prontas em `.vscode/launch.json`. No painel "Run and Debug" do VS Code, use:

- `Testar extracao local`
- `Consultar SOU CAIXA no Edge`
- `Consultar SOU CAIXA no Chrome`

Resultado esperado:

```text
Ultimo holerite disponivel para consulta:
- Referencia: 05/2026
```

## Como usar no SOU CAIXA

Execute:

```powershell
python .\holerite_program.py
```

O programa vai abrir o Microsoft Edge.

1. Faca login manualmente no SOU CAIXA.
2. Navegue ate a tela/lista de holerites, contracheques ou folha de pagamento.
3. Volte ao terminal e pressione `ENTER`.

O programa vai ler os textos exibidos na pagina e mostrar a referencia mais recente encontrada.

## Usar Chrome em vez de Edge

```powershell
python .\holerite_program.py --browser chrome
```

## URL diferente

```powershell
python .\holerite_program.py --url "https://endereco-correto-do-sou-caixa"
```

## Observacao

O programa nao salva usuario, senha, token nem PDF. A autenticacao fica manual porque sistemas bancarios/corporativos podem ter captcha, autenticacao forte e telas internas que mudam sem aviso.
