import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DEFAULT_URL = "https://sou.caixa.gov.br/"
DEFAULT_KEYWORDS = (
    "holerite",
    "contracheque",
    "folha de pagamento",
    "folha pagamento",
    "remuneracao",
    "demonstrativo",
    "recibo de pagamento",
)

MONTHS = {
    "jan": 1,
    "janeiro": 1,
    "fev": 2,
    "fevereiro": 2,
    "mar": 3,
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


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self._parts.append(clean)

    @property
    def text(self) -> str:
        return "\n".join(self._parts)


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.split())


def parse_reference_dates(text: str) -> list[datetime]:
    dates = []

    numeric_patterns = (
        r"\b(0?[1-9]|1[0-2])[/.-](20\d{2})\b",
        r"\b(20\d{2})[/.-](0?[1-9]|1[0-2])\b",
    )
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


def split_text_blocks(page_text: str) -> list[str]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    blocks = []

    for index, line in enumerate(lines):
        previous_line = lines[index - 1] if index > 0 else ""
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        blocks.append(" ".join(part for part in (previous_line, line, next_line) if part))

    return blocks or [page_text]


def find_latest_paycheck(text_blocks: Iterable[str], keywords: Iterable[str]) -> PaycheckCandidate | None:
    normalized_keywords = tuple(normalize(keyword) for keyword in keywords)
    candidates = []

    for block in text_blocks:
        normalized_block = normalize(block)
        if normalized_keywords and not any(keyword in normalized_block for keyword in normalized_keywords):
            continue

        for reference_date in parse_reference_dates(block):
            candidates.append(PaycheckCandidate(reference_date=reference_date, text=block.strip()))

    if not candidates:
        return None

    return max(candidates, key=lambda candidate: candidate.reference_date)


def read_html_text(path: Path) -> str:
    parser = TextExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.text


def create_driver(browser_name: str):
    try:
        if browser_name == "chrome":
            from selenium.webdriver import Chrome
            from selenium.webdriver.chrome.options import Options

            options = Options()
            options.add_argument("--start-maximized")
            return Chrome(options=options)

        from selenium.webdriver import Edge
        from selenium.webdriver.edge.options import Options

        options = Options()
        options.add_argument("--start-maximized")
        return Edge(options=options)
    except ModuleNotFoundError:
        print("Dependencia ausente: instale com `pip install -r requirements.txt`.")
        return None
    except Exception as error:
        print("Nao consegui abrir o navegador com Selenium.")
        print(f"Erro: {error}")
        print("\nTente uma destas opcoes:")
        print("  python holerite_program.py --browser edge")
        print("  python holerite_program.py --browser chrome")
        return None


def run_browser_mode(args: argparse.Namespace) -> int:
    driver = create_driver(args.browser)
    if driver is None:
        return 1

    try:
        driver.get(args.url)
        print("\nFaca login manualmente no SOU CAIXA no navegador aberto.")
        print("Depois navegue ate a tela/lista de holerites, contracheques ou folha de pagamento.")
        input("Quando a lista estiver visivel, volte aqui e pressione ENTER...")

        page_text = driver.find_element("tag name", "body").text
        latest = find_latest_paycheck(split_text_blocks(page_text), args.keywords)

        if latest is None:
            print("\nNao encontrei holerite com mes/ano na tela atual.")
            print("Confira se a lista de holerites esta visivel e tente novamente.")
            return 2

        print_latest(latest)
        return 0
    finally:
        if not args.keep_open:
            driver.quit()


def run_html_mode(args: argparse.Namespace) -> int:
    page_text = read_html_text(Path(args.html))
    latest = find_latest_paycheck(split_text_blocks(page_text), args.keywords)

    if latest is None:
        print("Nao encontrei holerite no arquivo HTML informado.")
        return 2

    print_latest(latest)
    return 0


def print_latest(candidate: PaycheckCandidate) -> None:
    print("\nUltimo holerite disponivel para consulta:")
    print(f"- Referencia: {candidate.reference_date.strftime('%m/%Y')}")
    print(f"- Texto encontrado: {candidate.text[:500]}")


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
        "--browser",
        choices=("edge", "chrome"),
        default="edge",
        help="Navegador usado pelo Selenium. Padrao: edge.",
    )
    parser.add_argument(
        "--html",
        help="Arquivo HTML local para testar a extracao sem abrir navegador.",
    )
    parser.add_argument(
        "--keyword",
        dest="keywords",
        action="append",
        default=list(DEFAULT_KEYWORDS),
        help="Palavra-chave para reconhecer itens de holerite. Pode repetir.",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Mantem o navegador aberto ao final da execucao.",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    if args.html:
        return run_html_mode(args)
    return run_browser_mode(args)


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
