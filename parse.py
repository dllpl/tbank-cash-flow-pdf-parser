import pdfplumber
import json
import re

PDF_FILE = "input.pdf"

START_TEXT = "Движение средств за период"
END_TEXT = "Пополнения:"

# Шаблон для распознавания начала операции по дате
date_start_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{4}")

# Ключевые слова для игнорирования строк
IGNORE_KEYWORDS = ["АО «ТБанк»", "БИК", "ИНН", "КПП", "лицензия"]

# Шаблон для разбора склеенной строки
line_pattern = re.compile(
    r"(?P<date1>\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?)\s+"
    r"(?P<date2>\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?)\s+"
    r"(?P<amount1>[+-]?\d{1,3}(?: \d{3})*(?:[.,]\d+)?\s*₽)\s+"
    r"(?P<amount2>[+-]?\d{1,3}(?: \d{3})*(?:[.,]\d+)?\s*₽)\s+"
    r"(?P<description>.+?)"
    r"(?:\s+(?P<card>\d+))?$",
    re.DOTALL
)

def extract_table_from_pdf(pdf_path):
    rows = []
    capture = False
    buffer = []

    # 1. Извлекаем текст между START_TEXT и END_TEXT
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

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

    # 2. Склеиваем многострочные операции
    merged_lines = []
    current_line = ""
    for line in buffer:
        if date_start_pattern.match(line):  # новая операция начинается с даты
            if current_line:
                merged_lines.append(current_line.strip())
            current_line = line
        else:
            current_line += " " + line
    if current_line:
        merged_lines.append(current_line.strip())

    # 3. Разбираем склеенные строки
    for line in merged_lines:
        match = line_pattern.match(line)
        if match:
            row_dict = {
                "Дата и время операции": match.group("date1"),
                "Дата списания": match.group("date2"),
                "Сумма в валюте операции": match.group("amount1"),
                "Сумма операции в валюте карты": match.group("amount2"),
                "Описание операции": match.group("description").strip(),
                "Номер карты": match.group("card") if match.group("card") else "-"
            }
            rows.append(row_dict)
        else:
            print(f"⚠ Не удалось разобрать строку: {line}")

    return rows

if __name__ == "__main__":
    data = extract_table_from_pdf(PDF_FILE)

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"✅ Извлечено {len(data)} строк, сохранено в output.json")
