import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


DEFAULT_URL = "https://sou.caixa.gov.br/"
DEFAULT_KEYWORDS = (
    "holerite",
    "contracheque",
    "folha de pagamento",
    "folha pagamento",
    "remuneracao",
)

MONTHS = {
    "jan": 1,
    "janeiro": 1,
    "fev": 2,
    "fevereiro": 2,
    "mar": 3,
    "marco": 3,
    "marco": 3,
    "abr": 4,
    "abril": 4,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "jul": 7,
    "julho": 7,
    "ago": 8,
    "agosto": 8,
    "set": 9,
    "setembro": 9,
    "out": 10,
    "outubro": 10,
    "nov": 11,
    "novembro": 11,
    "dez": 12,
    "dezembro": 12,
}


@dataclass(frozen=True)
class PaycheckCandidate:
    reference_date: datetime
    text: str


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.split())


def parse_reference_dates(text: str) -> list[datetime]:
    dates = []

    numeric_patterns = [
        r"\b(0?[1-9]|1[0-2])[/.-](20\d{2})\b",
        r"\b(20\d{2})[/.-](0?[1-9]|1[0-2])\b",
    ]
    for pattern in numeric_patterns:
        for match in re.finditer(pattern, text):
            first, second = match.groups()
            if first.startswith("20"):
                year, month = int(first), int(second)
            else:
                month, year = int(first), int(second)
            dates.append(datetime(year, month, 1))

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    month_year_pattern = rf"\b({month_names})\s*(?:de\s*)?(20\d{{2}})\b"
    for match in re.finditer(month_year_pattern, normalize(text)):
        month_name, year = match.groups()
        dates.append(datetime(int(year), MONTHS[month_name], 1))

    return dates


def candidate_from_text(text: str, keywords: Iterable[str]) -> list[PaycheckCandidate]:
    normalized = normalize(text)
    if keywords and not any(keyword in normalized for keyword in keywords):
        return []

    candidates = []
    for reference_date in parse_reference_dates(text):
        candidates.append(PaycheckCandidate(reference_date=reference_date, text=text.strip()))
    return candidates


def collect_text_candidates(page: "Page", keywords: Iterable[str], timeout_error: type[Exception]) -> list[PaycheckCandidate]:
    selectors = [
        "a",
        "button",
        "[role='button']",
        "li",
        "tr",
        ".card",
        ".mat-card",
        ".v-list-item",
        ".list-group-item",
        "[data-testid]",
    ]

    candidates = []
    seen_texts = set()
    for selector in selectors:
        for element in page.locator(selector).all():
            try:
                text = element.inner_text(timeout=800)
            except timeout_error:
                continue
            text_key = normalize(text)
            if len(text_key) < 6 or text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            candidates.extend(candidate_from_text(text, keywords))
    return candidates


def try_click_by_labels(page: "Page", labels: Iterable[str], timeout_ms: int, timeout_error: type[Exception]) -> bool:
    for label in labels:
        locators = [
            page.get_by_role("link", name=re.compile(label, re.I)),
            page.get_by_role("button", name=re.compile(label, re.I)),
            page.get_by_text(re.compile(label, re.I)),
        ]
        for locator in locators:
            try:
                if locator.count() > 0:
                    locator.first.click(timeout=timeout_ms)
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    return True
            except timeout_error:
                continue
    return False


def wait_for_user(message: str) -> None:
    print(message)
    input("Pressione ENTER aqui no terminal quando a pagina de holerites estiver visivel...")


def run(args: argparse.Namespace) -> int:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("Dependencia ausente: instale o Playwright com `pip install -r requirements.txt`.")
        print("Depois execute `python -m playwright install chromium`.")
        return 1

    keywords = tuple(normalize(keyword) for keyword in args.keywords)

    with sync_playwright() as playwright:
        try:
            launch_options = {"headless": args.headless}
            if args.channel:
                launch_options["channel"] = args.channel
            browser = playwright.chromium.launch(**launch_options)
        except PlaywrightError as error:
            message = str(error)
            if "Executable doesn't exist" in message or "playwright install" in message:
                print("O Playwright esta instalado, mas o navegador Chromium ainda nao foi baixado.")
                print("Execute no mesmo ambiente Python usado pelo PyCharm/Anaconda:")
                print("    python -m playwright install chromium")
                return 1
            if "spawn UNKNOWN" in message:
                print("O Windows bloqueou ou nao conseguiu iniciar o Chromium baixado pelo Playwright.")
                print("Tente executar usando o Microsoft Edge instalado no Windows:")
                print("    python holerite_program.py --channel msedge")
                print("Ou, se tiver Google Chrome instalado:")
                print("    python holerite_program.py --channel chrome")
                return 1
            raise
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()

        print(f"Abrindo {args.url}")
        page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)

        if not args.headless:
            wait_for_user(
                "\nFaca login manualmente no SOU CAIXA no navegador aberto.\n"
                "Se o sistema nao abrir direto nos holerites, navegue ate Holerite/Contracheque/Folha de pagamento."
            )

        if args.auto_click:
            try_click_by_labels(page, args.keywords, args.timeout, PlaywrightTimeoutError)

        page.wait_for_load_state("networkidle", timeout=args.timeout)
        candidates = collect_text_candidates(page, keywords, PlaywrightTimeoutError)

        if not candidates:
            print("\nNao consegui identificar nenhum holerite com mes/ano na tela atual.")
            print("Dica: abra a tela/lista de holerites e execute novamente, ou ajuste --keywords.")
            browser.close()
            return 2

        latest = max(candidates, key=lambda candidate: candidate.reference_date)
        reference = latest.reference_date.strftime("%m/%Y")

        print("\nUltimo holerite disponivel para consulta:")
        print(f"- Referencia: {reference}")
        print(f"- Texto encontrado: {latest.text[:500]}")

        browser.close()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Consulta o SOU CAIXA no navegador e informa o ultimo holerite disponivel."
    )
    parser.add_argument(
        "--url",
        default=os.getenv("SOU_CAIXA_URL", DEFAULT_URL),
        help="URL inicial do SOU CAIXA. Tambem pode ser definida por SOU_CAIXA_URL.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Executa sem abrir janela. Use apenas se a sessao ja estiver autenticada por outro meio.",
    )
    parser.add_argument(
        "--channel",
        choices=("chromium", "chrome", "msedge"),
        help="Navegador instalado que o Playwright deve usar. Ex.: msedge ou chrome.",
    )
    parser.add_argument(
        "--auto-click",
        action="store_true",
        help="Tenta clicar automaticamente em links/botoes com as palavras-chave informadas.",
    )
    parser.add_argument(
        "--keyword",
        dest="keywords",
        action="append",
        default=list(DEFAULT_KEYWORDS),
        help="Palavra-chave para reconhecer itens de holerite. Pode repetir.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Tempo maximo de espera por acoes no navegador, em milissegundos.",
    )
    return parser


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
