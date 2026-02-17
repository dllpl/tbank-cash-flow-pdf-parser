import json
import re
import pdfplumber

PDF_FILE = "input.pdf"

START_TEXT = "Движение средств за период"
END_TEXT = "Пополнения:"

date_start_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{4}")
IGNORE_KEYWORDS = ["АО «ТБанк»", "БИК", "ИНН", "КПП", "лицензия"]

line_pattern = re.compile(
    r"(?P<date1>\d{2}\.\d{2}\.\d{4})"
    r"(?:\s+(?P<time1>\d{2}:\d{2}))?"
    r"\s+(?P<date2>\d{2}\.\d{2}\.\d{4})"
    r"(?:\s+(?P<time2>\d{2}:\d{2}))?"
    r"\s+(?P<amount1>[+-]?\d{1,3}(?: \d{3})*(?:[.,]\d+)?\s*₽)"
    r"\s+(?P<amount2>[+-]?\d{1,3}(?: \d{3})*(?:[.,]\d+)?\s*₽)"
    r"\s+(?P<description>.+)$",
    re.UNICODE
)


def clean_description(description):
    desc = description.strip()
    card_num = "-"

    # 1. Убираем мусор
    garbage_pattern = r'\s+\d+\s+Дата и время.*$'
    desc = re.sub(garbage_pattern, '', desc, flags=re.IGNORECASE)

    # 2. Строгие паттерны
    strict_card_patterns = [
        r'на\s+(\d{4})\b',
        r'по\s+(\d{4})\b',
        r'для\s+(\d{4})\b',
        r'с\s+(\d{4})\b',
    ]

    for pattern in strict_card_patterns:
        match = re.search(pattern, desc, re.IGNORECASE)
        if match:
            card_num = match.group(1)
            break

    # 3. Если не нашли — ищем просто 4 цифры
    if card_num == "-":
        loose_match = re.search(r'\b(\d{4})\b', desc)
        if loose_match:
            card_num = loose_match.group(1)

    # 4. Удаляем номер карты из текста
    if card_num != "-":
        desc = re.sub(rf'\b{card_num}\b', '', desc)

    # 5. Убираем время
    desc = re.sub(r'\b\d{2}:\d{2}\b', '', desc)

    # 6. Финальная чистка
    desc = re.sub(r'\s+', ' ', desc).strip()

    return desc, card_num


def extract_table_from_pdf(pdf_path):
    rows = []
    capture = False
    buffer = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue

            for line in text.split("\n"):
                if START_TEXT in line:
                    capture = True
                    continue
                if END_TEXT in line:
                    capture = False
                    break
                if capture:
                    if any(keyword in line for keyword in IGNORE_KEYWORDS):
                        continue
                    buffer.append(line.strip())

    merged_lines = []
    current_line = ""
    for line in buffer:
        if date_start_pattern.match(line):
            if current_line:
                merged_lines.append(current_line.strip())
            current_line = line
        else:
            current_line += " " + line
    if current_line:
        merged_lines.append(current_line.strip())

    for line in merged_lines:
        match = line_pattern.match(line)
        if match:
            description, card_num = clean_description(match.group("description"))
            row_dict = {
                "Дата и время операции": f"{match.group('date1')} {match.group('time1') or ''}".strip(),
                "Дата списания": f"{match.group('date2')} {match.group('time2') or ''}".strip(),
                "Сумма в валюте операции": match.group("amount1"),
                "Сумма операции в валюте карты": match.group("amount2"),
                "Описание операции": description,
                "Номер карты": card_num
            }
            rows.append(row_dict)
        else:
            print(f"⚠ Не удалось разобрать: {line}")

    return rows


if __name__ == "__main__":
    data = extract_table_from_pdf(PDF_FILE)
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"✅ Извлечено {len(data)} транзакций")

    for i, t in enumerate(data[:5]):
        print(f"{i + 1}. '{t['Описание операции']}' | {t['Номер карты']}")
