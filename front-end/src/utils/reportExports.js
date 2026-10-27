const saveFile = (content, contentType, filename) => {
  const url = URL.createObjectURL(new Blob([content], { type: contentType }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
};

export const downloadReportText = (analysisId, reportData) => {
  const section1 = reportData?.section_1_financial_health || {};
  const section2 = reportData?.section_2_cash_flow_forecast || {};
  const section3 = reportData?.section_3_risk_alerts || {};
  const executiveSummary = reportData?.section_6_recommended_actions?.executive_summary;

  const content = `
FINANCIAL ANALYSIS REPORT
${new Date().toLocaleDateString()}

Analysis ID: ${analysisId}

FINANCIAL HEALTH
Revenue: ${section1.revenue?.total ?? section1.financial_health?.total_revenue ?? 'N/A'}
Expenses: ${section1.expenses?.total ?? section1.financial_health?.total_expenses ?? 'N/A'}
Net Profit Margin: ${section1.metrics?.net_profit_margin ?? section1.financial_health?.net_profit_margin_percent ?? 'N/A'}%

CASH FLOW
Monthly Burn Rate: ${section2.monthly_burn_rate ?? section1.metrics?.monthly_burn_rate ?? 'N/A'}
Runway: ${section2.runway_months ?? section1.metrics?.runway_months ?? 'N/A'} months

RISK ASSESSMENT
Risk Score: ${section3.risk_score ?? 'N/A'}
Risk Level: ${section3.risk_level ?? 'N/A'}

LOAN READINESS
Score: ${reportData?.section_5_loan_readiness_score ?? reportData?.loan_readiness_score ?? 'N/A'}/100

EXECUTIVE SUMMARY
${executiveSummary || 'No summary available'}
`;

  saveFile(content, 'text/plain', `financial-report-${analysisId.slice(0, 8)}.txt`);
};

export const downloadFinancialMetricsCsv = (analysisId, reportData) => {
  const section1 = reportData?.section_1_financial_health || {};
  const section2 = reportData?.section_2_cash_flow_forecast || {};
  const section3 = reportData?.section_3_risk_alerts || {};
  const rows = [
    ['Metric', 'Value'],
    ['Total Revenue', section1.revenue?.total ?? section1.financial_health?.total_revenue ?? 'N/A'],
    ['Total Expenses', section1.expenses?.total ?? section1.financial_health?.total_expenses ?? 'N/A'],
    ['Net Profit Margin (%)', section1.metrics?.net_profit_margin ?? section1.financial_health?.net_profit_margin_percent ?? 'N/A'],
    ['Monthly Burn Rate', section2.monthly_burn_rate ?? section1.metrics?.monthly_burn_rate ?? 'N/A'],
    ['Runway (months)', section2.runway_months ?? section1.metrics?.runway_months ?? 'N/A'],
    ['Risk Score', section3.risk_score ?? 'N/A'],
    ['Risk Level', section3.risk_level ?? 'N/A'],
    ['Loan Readiness Score', reportData?.section_5_loan_readiness_score ?? reportData?.loan_readiness_score ?? 'N/A'],
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  saveFile(csv, 'text/csv', `financial-metrics-${analysisId.slice(0, 8)}.csv`);
};

export const downloadRiskSummaryJson = (analysisId, reportData) => {
  const riskData = reportData?.section_3_risk_alerts || {};
  saveFile(
    JSON.stringify(riskData, null, 2),
    'application/json',
    `risk-summary-${analysisId.slice(0, 8)}.json`,
  );
};