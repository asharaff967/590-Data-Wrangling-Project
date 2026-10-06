# A Backtest Ready Historical Options Dataset for S&P 500 Stocks

FINTECH 590 Data Wrangling, Fall 2026, Duke University. Instructor: Alessio Brini. Group 2.

## The idea

We are building a dataset that lets researchers price historical options on S&P 500 stocks and indices realistically, from 2004 onward, so option trading strategies can be backtested.

Clean option price data already exists, but backtests that price historical options synthetically run into three problems:

1. **Survivorship bias.** Using today's index members hides the firms that were removed or delisted.
2. **Earnings announcements.** Backtests ignore when earnings come out, so they miss the volatility jump around the event.
3. **Midpoint fills.** Backtests assume trades fill at the midpoint, which understates trading costs.

Our dataset joins option data with the context needed to avoid these errors.

## Sources

| Source | What we use it for |
| --- | --- |
| WRDS: OptionMetrics | Option prices and volatility surfaces |
| WRDS: CRSP | Point in time index membership, stock prices, corporate actions |
| WRDS: I/B/E/S and Compustat | Earnings announcement dates and times |
| SEC EDGAR (free) | Company earnings press releases, used to confirm announcement dates and times |
| Bloomberg and LSEG | Spot checks and validation |
| IBKR | Live quotes for a short out of sample test at the end of the semester |

## Required LLM enrichment

Earnings dates and times often disagree across data providers. An LLM reads each company's press release and extracts the announcement date and whether it came before the open or after the close. We then hand validate a random sample and report the sample size, the agreement rate and the error types.

## Why it is new

OptionMetrics and commercial vendors such as ORATS sell option prices and volatility surfaces, and it is common in research to price S&P 500 index options from the OptionMetrics surface. We have not found a public dataset that extends this to individual stocks with point in time membership, verified earnings timing and realistic trading costs. This is still to be confirmed during source scouting.

## Consumer and "so what"

The consumer is a portfolio manager or quant researcher evaluating a systematic options strategy. The dataset should let them backtest strategies that use options on individual stocks without the three errors above.

## Plan and risks

* Start with the S&P 500 index and about 50 stocks, then scale to the full universe.
* Thin data for less liquid stocks is flagged, not hidden.
* Raw data is large, so we store derived tables.

## Course requirements

The project is worth 30 percent of the course grade. Full guidelines are in the course materials on Canvas.

### Three pillars

1. **The asset.** A cleaned, integrated dataset in a database (SQLite or similar) with a documented schema, deposited to the course Box folder.
2. **Proof of value.** A datasheet, a "so what" analysis and a stakeholder decision brief.
3. **The human and AI workflow.** A repository with an assistant instruction file, at least one LLM enrichment step with hand validation, and a reflective log.

### Deliverables, due in the final week

1. Dataset and database with a documented schema
2. Reproducible repository: code, instruction file, tests and a readable git history. A grader must be able to rebuild the dataset from raw sources with a single command (`make all`).
3. Datasheet: motivation, composition, collection process, cleaning, recommended uses, limitations and maintenance
4. "So what" analysis: one question the dataset answers, with at least one result or figure
5. Decision brief of one to two pages for a realistic consumer
6. AI workflow log: how AI supported us, failed us and extended us, the hand validation results, API cost and a statement of accountability
7. Final presentation

### Working with AI

* Use AI, but do not submit what AI made. Every artifact must be understood and defensible.
* One required enrichment step, hand validated on a random sample.
* Keep a running log of how AI supported, failed and extended us at each stage.
* Work in git with a project instruction file, keep raw data immutable and out of git, pin dependencies and track API cost.

### Grading

| Component | Weight |
| --- | --- |
| The asset (sources, integration, wrangling, schema, database, reproducibility) | 35% |
| Proof of value (datasheet, "so what" analysis, decision brief) | 30% |
| Human and AI workflow (three questions, enrichment and validation, accountability) | 20% |
| Presentation | 15% |

## Timeline

| Week | Date | Checkpoint |
| --- | --- | --- |
| 7 | Oct 7 | First integration: at least two sources joined and the key reconciliation shown. Setup card due on Canvas Oct 6, 11:59 pm. |
| 9 | Oct 21 | Preliminary cleaned dataset (20 to 30 percent coverage) and a demo of the LLM enrichment step with its hand validated sample |
| 10 | Oct 28 | Schema finalized, database stood up, first queries running |
| 11 | Nov 4 | Datasheet draft, "so what" question chosen, first result sketched |
| 12 | Nov 11 | Decision brief draft, queries and visuals refined |
| 13 | Nov 18 | Polish, dry run presentation, AI workflow log assembled |
| 14 | Dec 2 | Final deliverables submitted and presentations delivered |

## Open questions

* Whether derived OptionMetrics, CRSP, Compustat and I/B/E/S data may be deposited in the course Box folder under the WRDS license.
* Where realistic bid and ask spreads for the trading cost model come from.
* The novelty check against existing products.
