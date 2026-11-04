# 5. Data Analysis

## 5.1 Findings and decisions

The data was profiled before implementation. The findings below shaped the design, and most of them are also reported automatically by the `emporio audit` command.

| Finding | Decision |
|---|---|
| Products with status `discontinued` or `coming_soon`, and one active product with zero stock (id 96) | Never offered as available; the status is stated and alternatives from the same category are suggested. |
| Several promotions for the same product; "Black Friday" is inactive in November | `is_active` is the only source of truth, as required by manual section 7.3. |
| Order totals that differ from the sum of the items (orders 3 and 20) | The recorded total, the amount actually charged, is reported and never recalculated. |
| Orders containing a product not yet released (orders 3 and 14) | Reported as stored and flagged by the audit. |
| A shipped order with an expired delivery estimate (order 8) | Flagged as late; the agent offers to open a ticket for the team. |
| Two customers sharing one e-mail (customers 11 and 43) | Identity checks compare the contact with the owner of the specific order, so there is no ambiguity. |
| Two different WhatsApp numbers and an e-mail typo in the manual | The number and address on the cover and in the company data table are used: (67) 3341-4444 and contato@emporiodamusica.com.br. |
| Ambiguous rule for 1x to 3x installments ("no minimum, except below R$ 50") | Interpreted as a minimum of R$ 50 per installment. |
| No actual delivery date recorded | The estimated delivery date is used to count return deadlines. |
| Specifications in English (`"strings": "steel"`) while customers say "aço" | Specifications are translated for both search and answers. |
| Three categories without products; the manual mentions "more than 300 instruments" | The agent only reports what the data contains. |

## 5.2 Data quality report

`emporio audit` turns these checks into a list for the store team, sorted by severity. With the data provided it reports ten issues:

| Severity | Issue |
|---|---|
| High | Orders 3 and 14 contain a product with status `coming_soon` |
| High | Order 8 is shipped and its delivery estimate has passed |
| Medium | Orders 3 and 20: total differs from the items at list price |
| Medium | Customers 11 and 43 share the same e-mail |
| Low | Product 96 is active with zero stock |
| Low | Categories 6, 7 and 8 have no available products |

## 5.3 Validation on load

Every file is validated when the application starts:

- required columns are present;
- data types are correct;
- prices are positive;
- identifiers are unique;
- product specifications are well-formed JSON.

Any problem stops the application with the file name and line number, for example `products.csv, line 3: …`. The `emporio check` command runs this validation without calling the language model.
