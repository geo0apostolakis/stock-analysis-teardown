"""Which XBRL tags feed each line item, in priority order.

Companies switch tags over the years (Marvell moved from Revenues to
RevenueFromContractWithCustomerExcludingAssessedTax), so every item is a chain.
The first tag with a value for a given period wins, per period, and the tag used
is stored next to the value so a reader can audit it.

kind:
  flow       duration value (income statement, cash flow)
  instant    point-in-time value (balance sheet)
  per_share  duration value in <currency>/shares (EPS, dividends per share)
  shares     duration value in shares (weighted average share counts)
  shares_i   instant value in shares (shares outstanding)
"""

CONCEPTS = {
    # ---------------- income statement ----------------
    "revenue": {
        "label": "Revenue", "kind": "flow",
        "us-gaap": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                    "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                    "SalesRevenueGoodsNet", "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense",
                    "OperatingLeasesIncomeStatementLeaseRevenue"],
        "ifrs-full": ["Revenue", "RevenueFromContractsWithCustomers", "RevenueFromSaleOfGoods"],
    },
    "cost_of_revenue": {
        "label": "Cost of revenue", "kind": "flow",
        "us-gaap": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
                    "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization", "CostOfServices"],
        "ifrs-full": ["CostOfSales"],
    },
    "gross_profit": {
        "label": "Gross profit", "kind": "flow",
        "us-gaap": ["GrossProfit"],
        "ifrs-full": ["GrossProfit"],
    },
    "rnd": {
        "label": "Research and development", "kind": "flow",
        "us-gaap": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
                    "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"],
        "ifrs-full": ["ResearchAndDevelopmentExpense"],
    },
    "sga": {
        "label": "Selling, general and administrative", "kind": "flow",
        "us-gaap": ["SellingGeneralAndAdministrativeExpense"],
        "ifrs-full": ["SellingGeneralAndAdministrativeExpense"],
    },
    "selling_marketing": {
        "label": "Selling and marketing", "kind": "flow",
        "us-gaap": ["SellingAndMarketingExpense", "MarketingAndAdvertisingExpense"],
        "ifrs-full": ["DistributionCosts", "SellingExpense"],
    },
    "general_admin": {
        "label": "General and administrative", "kind": "flow",
        "us-gaap": ["GeneralAndAdministrativeExpense"],
        "ifrs-full": ["AdministrativeExpense"],
    },
    "amort_intangibles": {
        "label": "Amortization of acquired intangibles", "kind": "flow",
        "us-gaap": ["AmortizationOfIntangibleAssets", "AmortizationOfAcquiredIntangibleAssets"],
        "ifrs-full": ["AmortisationExpense", "AmortisationIntangibleAssetsOtherThanGoodwill"],
    },
    "restructuring": {
        "label": "Restructuring and other charges", "kind": "flow",
        "us-gaap": ["RestructuringCharges", "RestructuringSettlementAndImpairmentProvisions",
                    "RestructuringCosts", "RestructuringCostsAndAssetImpairmentCharges"],
        "ifrs-full": [],
    },
    "goodwill_impairment": {
        "label": "Goodwill impairment", "kind": "flow",
        "us-gaap": ["GoodwillImpairmentLoss", "GoodwillAndIntangibleAssetImpairment"],
        "ifrs-full": ["ImpairmentLossRecognisedInProfitOrLossGoodwill"],
    },
    "operating_expenses": {
        "label": "Total operating expenses", "kind": "flow",
        "us-gaap": ["OperatingExpenses"],
        "ifrs-full": [],
    },
    "operating_income": {
        "label": "Operating income", "kind": "flow",
        "us-gaap": ["OperatingIncomeLoss"],
        "ifrs-full": ["ProfitLossFromOperatingActivities"],
    },
    "interest_expense": {
        "label": "Interest expense", "kind": "flow",
        "us-gaap": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt",
                    "InterestAndDebtExpense", "InterestExpenseNet"],
        "ifrs-full": ["InterestExpense", "FinanceCosts", "InterestExpenseOnBorrowings"],
    },
    "interest_income": {
        "label": "Interest income", "kind": "flow",
        "us-gaap": ["InvestmentIncomeInterest", "InterestIncomeOther", "InvestmentIncomeInterestAndDividend",
                    "InterestAndOtherIncome"],
        "ifrs-full": ["InterestRevenueCalculatedUsingEffectiveInterestMethod", "FinanceIncome", "InterestIncome"],
    },
    "pretax_income": {
        "label": "Income before taxes", "kind": "flow",
        "us-gaap": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
                    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],
        "ifrs-full": ["ProfitLossBeforeTax"],
    },
    "income_tax": {
        "label": "Income tax expense", "kind": "flow",
        "us-gaap": ["IncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefitContinuingOperations"],
        "ifrs-full": ["IncomeTaxExpenseContinuingOperations"],
    },
    "net_income": {
        "label": "Net income", "kind": "flow",
        "us-gaap": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss",
                    "IncomeLossFromContinuingOperations"],
        "ifrs-full": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    },
    "gain_on_divestiture": {
        "label": "Gain on sale of business", "kind": "flow",
        "us-gaap": ["GainLossOnSaleOfBusiness", "DisposalGroupNotDiscontinuedOperationGainLossOnDisposal",
                    "GainLossOnDispositionOfBusiness", "DiscontinuedOperationGainLossOnDisposalOfDiscontinuedOperationNetOfTax",
                    "GainLossOnDispositionOfAssets1"],
        "ifrs-full": ["GainsLossesOnDisposalsOfInvestments"],
    },
    "eps_basic": {
        "label": "EPS (basic)", "kind": "per_share",
        "us-gaap": ["EarningsPerShareBasic", "IncomeLossFromContinuingOperationsPerBasicShare"],
        "ifrs-full": ["BasicEarningsLossPerShare"],
    },
    "eps_diluted": {
        "label": "EPS (diluted)", "kind": "per_share",
        "us-gaap": ["EarningsPerShareDiluted", "IncomeLossFromContinuingOperationsPerDilutedShare",
                    "EarningsPerShareBasicAndDiluted"],
        "ifrs-full": ["DilutedEarningsLossPerShare"],
    },
    "dividends_per_share": {
        "label": "Dividends declared per share", "kind": "per_share",
        "us-gaap": ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"],
        "ifrs-full": ["DividendsRecognisedAsDistributionsToOwnersPerShare"],
    },
    "shares_basic": {
        "label": "Weighted average shares (basic)", "kind": "shares",
        "us-gaap": ["WeightedAverageNumberOfSharesOutstandingBasic"],
        "ifrs-full": ["WeightedAverageShares"],
    },
    "shares_diluted": {
        "label": "Weighted average shares (diluted)", "kind": "shares",
        "us-gaap": ["WeightedAverageNumberOfDilutedSharesOutstanding",
                    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted"],
        "ifrs-full": ["AdjustedWeightedAverageShares", "WeightedAverageShares"],
    },
    # ---------------- cash flow ----------------
    "cfo": {
        "label": "Operating cash flow", "kind": "flow",
        "us-gaap": ["NetCashProvidedByUsedInOperatingActivities",
                    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
        "ifrs-full": ["CashFlowsFromUsedInOperatingActivities"],
    },
    "capex": {
        "label": "Capital expenditure", "kind": "flow",
        "us-gaap": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
                    "PaymentsForCapitalImprovements", "PaymentsToAcquireOtherPropertyPlantAndEquipment"],
        "ifrs-full": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                      "PurchaseOfPropertyPlantAndEquipment"],
    },
    "sbc": {
        "label": "Stock-based compensation", "kind": "flow",
        "us-gaap": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense",
                    "ShareBasedCompensationArrangementByShareBasedPaymentAwardExpenseRecognized"],
        "ifrs-full": ["AdjustmentsForSharebasedPayments", "ExpenseFromSharebasedPaymentTransactionsWithEmployees"],
    },
    "dna": {
        "label": "Depreciation and amortization", "kind": "flow",
        "us-gaap": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                    "DepreciationAndAmortization", "DepreciationAmortizationAndOther"],
        "ifrs-full": ["AdjustmentsForDepreciationAndAmortisationExpense", "DepreciationAndAmortisationExpense"],
    },
    "depreciation": {
        "label": "Depreciation", "kind": "flow",
        "us-gaap": ["Depreciation", "DepreciationNonproduction", "DepreciationAndAmortizationExcludingIntangibles"],
        "ifrs-full": ["DepreciationExpense", "DepreciationPropertyPlantAndEquipment"],
    },
    "acquisitions": {
        "label": "Acquisitions, net of cash acquired", "kind": "flow",
        "us-gaap": ["PaymentsToAcquireBusinessesNetOfCashAcquired", "PaymentsToAcquireBusinessesGross",
                    "PaymentsToAcquireBusinessesAndInterestInAffiliates"],
        "ifrs-full": ["CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities"],
    },
    "divestiture_proceeds": {
        "label": "Proceeds from divestitures", "kind": "flow",
        "us-gaap": ["ProceedsFromDivestitureOfBusinessesNetOfCashDivested", "ProceedsFromDivestitureOfBusinesses",
                    "ProceedsFromSaleOfBusinessNetOfCashDivested"],
        "ifrs-full": ["CashFlowsFromLosingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities"],
    },
    "buybacks": {
        "label": "Share repurchases", "kind": "flow",
        "us-gaap": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
        "ifrs-full": ["PaymentsToAcquireOrRedeemEntitysShares"],
    },
    "dividends_paid": {
        "label": "Dividends paid", "kind": "flow",
        "us-gaap": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "PaymentsOfOrdinaryDividends"],
        "ifrs-full": ["DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"],
    },
    "debt_issued": {
        "label": "Debt issued", "kind": "flow",
        "us-gaap": ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfSeniorLongTermDebt",
                    "ProceedsFromIssuanceOfDebt", "ProceedsFromDebtNetOfIssuanceCosts", "ProceedsFromIssuanceOfUnsecuredDebt"],
        "ifrs-full": ["ProceedsFromNoncurrentBorrowings", "ProceedsFromBorrowingsClassifiedAsFinancingActivities",
                      "ProceedsFromIssueOfBondsNotesAndDebentures"],
    },
    "debt_repaid": {
        "label": "Debt repaid", "kind": "flow",
        "us-gaap": ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt", "RepaymentsOfSeniorDebt",
                    "RepaymentsOfUnsecuredDebt", "RepaymentsOfConvertibleDebt"],
        "ifrs-full": ["RepaymentsOfNoncurrentBorrowings", "RepaymentsOfBorrowingsClassifiedAsFinancingActivities",
                      "RepaymentsOfBondsNotesAndDebentures"],
    },
    "interest_paid": {
        "label": "Cash interest paid", "kind": "flow",
        "us-gaap": ["InterestPaidNet", "InterestPaid"],
        "ifrs-full": ["InterestPaidClassifiedAsOperatingActivities", "InterestPaidClassifiedAsFinancingActivities"],
    },
    "taxes_paid": {
        "label": "Cash taxes paid", "kind": "flow",
        "us-gaap": ["IncomeTaxesPaidNet", "IncomeTaxesPaid"],
        "ifrs-full": ["IncomeTaxesPaidRefundClassifiedAsOperatingActivities"],
    },
    # ---------------- balance sheet ----------------
    "cash": {
        "label": "Cash and equivalents", "kind": "instant",
        "us-gaap": ["CashAndCashEquivalentsAtCarryingValue",
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
        "ifrs-full": ["CashAndCashEquivalents"],
    },
    "short_term_investments": {
        "label": "Short-term investments", "kind": "instant",
        "us-gaap": ["ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
                    "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesCurrent"],
        "ifrs-full": ["CurrentFinancialAssetsAtFairValueThroughProfitOrLoss", "OtherCurrentFinancialAssets",
                      "CurrentInvestments"],
    },
    "receivables": {
        "label": "Accounts receivable", "kind": "instant",
        "us-gaap": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent", "AccountsNotesAndLoansReceivableNetCurrent"],
        "ifrs-full": ["CurrentTradeReceivables", "TradeAndOtherCurrentReceivables"],
    },
    "inventory": {
        "label": "Inventory", "kind": "instant",
        "us-gaap": ["InventoryNet", "InventoryFinishedGoodsNetOfReserves"],
        "ifrs-full": ["Inventories", "CurrentInventoriesHeldForSale"],
    },
    "current_assets": {
        "label": "Total current assets", "kind": "instant",
        "us-gaap": ["AssetsCurrent"], "ifrs-full": ["CurrentAssets"],
    },
    "ppe": {
        "label": "Property, plant and equipment, net", "kind": "instant",
        "us-gaap": ["PropertyPlantAndEquipmentNet",
                    "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"],
        "ifrs-full": ["PropertyPlantAndEquipment"],
    },
    "goodwill": {
        "label": "Goodwill", "kind": "instant",
        "us-gaap": ["Goodwill"], "ifrs-full": ["Goodwill"],
    },
    "intangibles": {
        "label": "Intangible assets, net", "kind": "instant",
        "us-gaap": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
        "ifrs-full": ["IntangibleAssetsOtherThanGoodwill"],
    },
    "total_assets": {
        "label": "Total assets", "kind": "instant",
        "us-gaap": ["Assets"], "ifrs-full": ["Assets"],
    },
    "payables": {
        "label": "Accounts payable", "kind": "instant",
        "us-gaap": ["AccountsPayableCurrent", "AccountsPayableTradeCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"],
        "ifrs-full": ["TradeAndOtherCurrentPayablesToTradeSuppliers", "CurrentTradePayables", "TradeAndOtherCurrentPayables"],
    },
    "current_liabilities": {
        "label": "Total current liabilities", "kind": "instant",
        "us-gaap": ["LiabilitiesCurrent"], "ifrs-full": ["CurrentLiabilities"],
    },
    # DebtCurrent is the one tag for the whole current debt line. Companies that do not use it report the
    # current portion of long-term debt and short-term borrowings separately; fetch_sec.py adds the two.
    "short_term_debt": {
        "label": "Short-term debt and current portion", "kind": "instant",
        "us-gaap": ["DebtCurrent"],
        "ifrs-full": ["CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings", "CurrentBorrowings"],
        "parts": ["current_ltd", "short_borrowings"],
    },
    "current_ltd": {
        "label": "Current portion of long-term debt", "kind": "instant",
        "us-gaap": ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent",
                    "LongTermDebtAndFinanceLeasesCurrent", "ConvertibleNotesPayableCurrent", "SeniorNotesCurrent"],
        "ifrs-full": ["CurrentPortionOfLongtermBorrowings"],
    },
    "short_borrowings": {
        "label": "Short-term borrowings and commercial paper", "kind": "instant",
        "us-gaap": ["ShortTermBorrowings", "NotesAndLoansPayableCurrent", "LoansPayableCurrent", "NotesPayableCurrent",
                    "CommercialPaper"],
        "ifrs-full": ["ShorttermBorrowings"],
    },
    "long_term_debt": {
        "label": "Long-term debt", "kind": "instant",
        "us-gaap": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations",
                    "LongTermDebtAndFinanceLeasesNoncurrent", "LongTermNotesPayable", "SeniorNotesNoncurrent",
                    "ConvertibleNotesPayableNoncurrent", "SeniorLongTermNotes", "UnsecuredLongTermDebt",
                    "OtherLongTermDebtNoncurrent"],
        "ifrs-full": ["NoncurrentPortionOfNoncurrentBorrowings", "NoncurrentBorrowings"],
        "parts": ["ltd_bonds", "ltd_loans"],
    },
    "ltd_bonds": {
        "label": "Bonds payable, non-current", "kind": "instant",
        "us-gaap": [], "ifrs-full": ["NoncurrentPortionOfNoncurrentBondsIssued", "BondsIssued"],
    },
    "ltd_loans": {
        "label": "Long-term loans, non-current", "kind": "instant",
        "us-gaap": [], "ifrs-full": ["LongtermBorrowings", "NoncurrentPortionOfNoncurrentLoansReceived"],
    },
    "long_term_debt_total": {
        "label": "Long-term debt including current portion", "kind": "instant",
        "us-gaap": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
                    "DebtInstrumentCarryingAmount"],
        "ifrs-full": [],
    },
    "operating_lease_liabilities": {
        "label": "Operating lease liabilities", "kind": "instant",
        "us-gaap": ["OperatingLeaseLiability"], "ifrs-full": ["LeaseLiabilities"],
    },
    "total_liabilities": {
        "label": "Total liabilities", "kind": "instant",
        "us-gaap": ["Liabilities"], "ifrs-full": ["Liabilities"],
    },
    "equity": {
        "label": "Shareholders' equity", "kind": "instant",
        "us-gaap": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "ifrs-full": ["EquityAttributableToOwnersOfParent", "Equity"],
    },
    "shares_outstanding": {
        "label": "Shares outstanding (balance sheet)", "kind": "shares_i",
        "us-gaap": ["CommonStockSharesOutstanding"], "ifrs-full": ["NumberOfSharesOutstanding"],
    },
    # ---------------- debt maturities (latest 10-K) ----------------
    "maturity_y1": {"label": "Debt due within 1 year", "kind": "instant",
                    "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths"], "ifrs-full": []},
    "maturity_y2": {"label": "Debt due in year 2", "kind": "instant",
                    "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo"], "ifrs-full": []},
    "maturity_y3": {"label": "Debt due in year 3", "kind": "instant",
                    "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree"], "ifrs-full": []},
    "maturity_y4": {"label": "Debt due in year 4", "kind": "instant",
                    "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour"], "ifrs-full": []},
    "maturity_y5": {"label": "Debt due in year 5", "kind": "instant",
                    "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive"], "ifrs-full": []},
    "maturity_after5": {"label": "Debt due after year 5", "kind": "instant",
                        "us-gaap": ["LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive"], "ifrs-full": []},
}

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT"}
QUARTER_FORMS = {"10-Q", "10-Q/A", "6-K"}
