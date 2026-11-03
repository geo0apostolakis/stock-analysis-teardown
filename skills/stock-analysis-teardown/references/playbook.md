# The analysis playbook

This is the framework every teardown follows. Parts 1 to 3 come from the original analysis plan the skill was built on. Part 4 (valuation) and the thesis were added so the deck ends with what the price assumes.

Not every section suits every company. The deck scales with the company. A small single-product business can fold several sections into one slide, a conglomerate may need two slides for one section. Each section has an id. A slide lists the ids it covers in `sections`, and `validate.py` checks that every id is either on a slide or skipped on purpose in `meta.coverage_skipped` with a reason. Sections marked core cannot be skipped.

Ids 3.1 to 3.3 are numbered 1.13 to 1.15 in the original plan. They are renumbered here so the parts read in order.

## Executive summary

### 0.1 Executive summary

- Verdict in words, the one sentence that justifies it
- Three strengths and three risks
- Five headline KPIs
- Business quality score from 1.12

## Part 1. The business

### 1.1 Business model and revenue generation

- How does the company generate revenue?
- What is its business model, and how does it create value?
- What are its primary revenue streams and sources of profitability?

### 1.2 Business segments and revenue breakdown

- Segments by product, service, customer type and geography
- Revenue and profitability contribution of each segment
- Core growth drivers and the most important segments

### 1.3 Competitive advantage and economic moat

- Key competitive advantages
- What protects the market position
- Barriers to entry, switching costs, network effects, IP, scale, brand (where they apply)
- Durability of the advantages

### 1.4 Industry and sector analysis

- Industry structure, size and TAM
- Growth prospects, maturity, cyclicality, long-term trends
- Demand drivers, technology shifts, structural changes
- Competitive landscape, concentration, the company's relative position

### 1.5 Pricing power and customer retention

- Ability to raise prices without hurting demand
- Customer price sensitivity and demand elasticity
- Switching cost for customers
- Retention, contract structure, recurring revenue, customer concentration

### 1.6 Products and services, lifecycle and development (optional)

- Main products and their lifecycle stage
- Differentiation, adoption, demand sustainability
- Upcoming launches
- Effect of new products on revenue, margins and position

### 1.7 Key dependencies and operational risks

- Dependence on major customers, suppliers, channels, technologies, partners
- Supply chain bottlenecks
- Exposure to key components, IP or third-party platforms
- Impact if a critical dependency breaks

### 1.8 Management, board and governance

- Background and track record of the CEO, CFO and key executives
- Board expertise and independence
- Capital allocation and execution record
- Insider ownership, alignment, pay incentives
- Credibility, governance quality, value creation

### 1.9 Strategic threats and competitive risks

- Existing competitors and new entrants
- Technological disruption and obsolescence
- Substitutes and changing customer preferences
- Regulatory, geopolitical and industry risks
- Effect on the long-term advantage

### 1.10 Mergers, acquisitions and strategic investments (optional)

- Significant acquisitions, divestitures and investments
- Strategic rationale of each
- Price paid, integration, value created
- Did they strengthen the position or add risk
- Future acquisition strategy

### 1.11 Growth strategy and geographic expansion (optional)

- Where and why the company will expand
- New markets, customers, products, regions
- Organic versus acquired growth
- Required investment, execution risk, expected benefit

### 1.12 Overall business quality assessment

- Business model, advantages and long-term sustainability
- Strongest attributes and biggest structural weaknesses
- Durability of position and of profits and cash flows
- Quality judged apart from the share price

## Part 2. Financial analysis

### 2.1 Revenue performance and growth

- Historical revenue and CAGR
- Year-over-year growth and drivers
- Cyclicality and inflection points
- Organic versus acquisition-driven growth

### 2.2 Revenue mix and growth quality (optional)

- Revenue by segment, product, geography, end market
- Recurring versus non-recurring revenue
- Customer concentration and visibility
- Sustainability of growth drivers

### 2.3 Profitability and margins

- Gross profit and gross margin
- Operating income and operating margin
- Net income and net margin
- Margin trends and drivers

### 2.4 Operating expenses and operating leverage (optional)

- R&D, SG&A, other opex
- Opex as % of revenue
- Revenue growth versus opex growth
- Fixed-cost absorption and scalability

### 2.5 Earnings quality and normalized profitability

- GAAP versus adjusted earnings
- One-off gains, restructuring, impairments
- Acquisition amortization
- SBC and dilution
- Normalized, sustainable earnings

### 2.6 Cash flow generation and conversion

- Operating cash flow and free cash flow
- Capex and FCF margin
- Cash conversion, earnings to cash reconciliation
- Quality and sustainability of cash

### 2.7 Working capital efficiency (optional)

- Receivables and DSO
- Inventory and turnover
- Payables and supplier financing
- Cash conversion cycle, operating working capital
- Working capital needs relative to revenue

### 2.8 Balance sheet quality (optional)

- Cash and short-term investments
- Receivables, inventory, other current assets
- Goodwill and intangibles
- Asset quality and impairment exposure
- Current assets, liabilities, working capital

### 2.9 Debt, liquidity and financial risk

- Short and long-term debt
- Net debt and net debt to EBITDA
- Debt to equity and interest coverage
- Maturity profile and refinancing
- Liquidity, credit facilities, flexibility

### 2.10 Capital expenditure and capital intensity (optional)

- Historical and projected capex
- Capex % of revenue
- Maintenance versus growth capex where estimable
- Depreciation and amortization
- Capital needed for future growth

### 2.11 Capital allocation

- Organic investment versus acquisitions
- M&A strategy and returns
- Buybacks and dividends
- Debt repayment and financing
- Dilution and discipline

### 2.12 Returns on capital and shareholder performance

- ROIC
- ROE
- ROA where relevant
- Diluted EPS and EPS growth
- Share count and per-share value
- Returns against the cost of capital

### 2.13 Financial peer benchmarking

- Growth and margins
- Cash generation and capital efficiency
- Leverage and liquidity
- Valuation multiples
- Business model and accounting differences

### 2.14 Financial outlook and key takeaways

- Historical inflection points
- Main strengths and weaknesses
- Key drivers and risks
- Sustainability of growth, margins, cash flow
- What it means for forecasting and valuation

## Part 3. Competitors, owners and pressures

### 3.1 Competitor analysis (playbook 1.13)

- Competitive positioning: product quality, features, pricing, value versus main competitors
- Pricing power: which competitors can raise prices without losing customers
- Competitive exposure by product, customer segment and geography
- Recent developments: competitor M&A, partnerships
- Competitive threats to share, profitability and growth

### 3.2 Ownership and insider activity (playbook 1.14)

- Institutional ownership: major holders and changes
- Insider ownership and significant purchases or sales
- Buybacks: size, rationale, effect on value

### 3.3 Competitive pressures and brand strength (playbook 1.15) (optional)

- External pressures: competitive, regulatory, government
- Brand strength and customer loyalty
- Credible customer surveys and independent studies against competitors

## Part 4. Valuation

### 4.1 Multiples versus peers and own history

- P/E, EV/EBITDA, EV/sales, P/FCF, FCF yield against peer medians
- Same multiples against the company's own 5-year range

### 4.2 DCF scenarios and sensitivity

- Bear, base, bull assumptions with reasons
- Value per share in each case and the probability-weighted value
- WACC and terminal growth sensitivity

### 4.3 Reverse DCF: what the price assumes

- Owner FCF growth and revenue growth the current price implies
- Whether that is plausible against history, guidance and the industry

### 4.4 Valuation summary (football field)

- All methods on one chart against the price
- Where the price sits and what has to go right

## Thesis

### 5.1 Thesis and what would change my mind

- The investment case in three short paragraphs
- Four to six measurable signposts that would change the view
