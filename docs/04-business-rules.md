# 4. Business Rules

All rules below come from the store's policy manual. They are implemented in the domain layer and covered by unit tests, so the language model never calculates prices, discounts or deadlines itself.

| Rule | Manual section | Implementation |
|---|---|---|
| PIX payments receive 5% off the list price | 3 | `PriceCalculator` |
| Promotions are not cumulative; the PIX discount does not apply to promotional prices | 6.2 | `PriceCalculator` |
| Only active promotions apply; with several active, the largest discount wins | 6.2, 7.3 | `PriceCalculator`, promotion repository |
| Interest-free installments up to 12x, with a minimum per installment of R$ 50 (1x to 3x), R$ 80 (4x to 6x) and R$ 100 (7x to 12x) | 3.1 | `PriceCalculator` |
| Regret: return within 7 calendar days after delivery | 4.1 | `ReturnPolicy` |
| Defect: exchange within 30 days of purchase, then the manufacturer's warranty with store mediation | 4.2 | `ReturnPolicy` |
| Preference exchange (colour, model, size): within 7 days | 4.3 | `ReturnPolicy` |
| Legal warranty: 90 days from delivery | 8.1 | `ReturnPolicy` |
| Opening hours: Monday to Friday 09:00–18:00, Saturday 09:00–13:00, closed on Sundays and holidays, in Campo Grande time (UTC-4) | 2 | `StoreSchedule`, `SystemClock` |
| Only musical instruments are sold; accessories are redirected | 1, 7.1 | System prompt |
| Out-of-stock and discontinued products: inform and suggest alternatives | 7.3 | `CatalogService` |
| Expired promotions are never promised | 7.3 | Promotion repository (`is_active`) |
| Promotional prices are always shown with the original price and the discount | 6.2 | Presenters and system prompt |
| Complaints are answered within 24 business hours | 7.3 | `HandoffService` |

## 4.1 Worked example

The Crafter HT-100 has a list price of R$ 2.399,00 and an active 18% promotion:

- the promotional price is R$ 2.399,00 × 0,82 = **R$ 1.967,18**;
- because promotions and PIX are not cumulative, the PIX price is also R$ 1.967,18;
- the largest plan that keeps each installment at R$ 100 or more is **12x of R$ 163,93**.

The agent receives these values from the tool already calculated and only has to communicate them.
