# Diff Report: svod_2025_2026.csv vs svod_2025_2026.xlsx

**CSV:** `D:\models\extracted\svod_2025_2026.csv`
**XLSX:** `D:\models\extracted\svod_2025_2026.xlsx`
**Total differing cells:** 48

## Structure
- CSV emitters: 24
- XLSX emitters: 24
- Columns: 24 (identical sets)

## Category Counts
- пустое vs число: 35
- пустое vs "нет": 10
- значение заменено: 2
- перестановка цифр / опечатка (<5%): 1

## Verdict Counts
- XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source: 35
- нет JSON: 6
- нет cash_flow: 4
- CSV = JSON (pipeline OK); XLSX differs (human correction): 3

## Full Diff List

| # | Emitter | Key | CSV | XLSX | JSON | Category | Stage | Verdict |
|---|---------|-----|-----|------|------|----------|-------|---------|
| 1 | КИФА | 1410_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 2 | КИФА | 1300_2026 |  | 292421 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 3 | КИФА | 1410_2026 |  | 573120 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 4 | КИФА | 1450_2026 |  | 69641 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 5 | КИФА | 1510_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 6 | КИФА | 1550_2026 |  | 37732 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 7 | Проект 111 | 1250_2025 |  | 158429 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 8 | Проект 111 | 1300_2025 |  | 4081321 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 9 | Проект 111 | 1410_2025 |  | 1205284 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 10 | Проект 111 | 1450_2025 |  | 312968 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 11 | Проект 111 | 1510_2025 |  | 167217 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 12 | Проект 111 | 1550_2025 |  | 93034 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 13 | Проект 111 | 1300_2026 |  | 4459045 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 14 | Проект 111 | 1410_2026 |  | 505284 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 15 | Проект 111 | 1450_2026 |  | 272536 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 16 | Проект 111 | 1510_2026 |  | 714060 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 17 | Проект 111 | 1550_2026 |  | 118455 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 18 | Афанасий | 1550_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 19 | Афанасий | 4100_2025 |  | нет |  | пустое vs "нет" | нет cash_flow | нет cash_flow |
| 20 | Афанасий | 4110_2025 |  | нет |  | пустое vs "нет" | нет cash_flow | нет cash_flow |
| 21 | Афанасий | 1550_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 22 | Афанасий | 4100_2026 |  | нет |  | пустое vs "нет" | нет cash_flow | нет cash_flow |
| 23 | Афанасий | 4110_2026 |  | нет |  | пустое vs "нет" | нет cash_flow | нет cash_flow |
| 24 | Омега | 1550_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 25 | Омега | 1550_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 26 | Байсэл | 1450_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 27 | Байсэл | 1550_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 28 | Байсэл | 1450_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 29 | Байсэл | 1550_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 30 | Бианка премиум | 1510_2025 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 31 | Бианка премиум | 1510_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 32 | Моторные технологии | 1250_2025 | 4070 | 14500 | 4070 | значение заменено | pipeline | CSV = JSON (pipeline OK); XLSX differs (human correction) |
| 33 | Моторные технологии | 1550_2025 | 9643 | 9410 | 9643 | перестановка цифр / опечатка (<5%) | pipeline | CSV = JSON (pipeline OK); XLSX differs (human correction) |
| 34 | Эфферон | 1250_2025 | 800 | 9685 | 800 | значение заменено | pipeline | CSV = JSON (pipeline OK); XLSX differs (human correction) |
| 35 | Эфферон | 1300_2025 |  | 166401 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 36 | Эфферон | 1410_2025 |  | 230401 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 37 | Эфферон | 1450_2025 |  | 16293 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 38 | Эфферон | 1510_2025 |  | 6683 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 39 | Эфферон | 1550_2025 |  | 26971 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 40 | Эфферон | 1510_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 41 | Финэква | 1250_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 42 | Финэква | 1300_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 43 | Финэква | 1410_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 44 | Финэква | 1450_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 45 | Финэква | 1510_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 46 | Финэква | 1550_2025 |  | нет |  | пустое vs "нет" | нет JSON | нет JSON |
| 47 | Финэква | 1450_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
| 48 | Финэква | 1550_2026 |  | 0 |  | пустое vs число | pipeline | XLSX has value, JSON balance column found -> pipeline missed it or human filled from other source |
