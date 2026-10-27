import React from 'react';

const Privacy = () => {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 space-y-8">
      <div className="border-b border-[var(--border-color)] pb-4 mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">Privacy Policy</h1>
        <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase">Effective date: October 17, 2026</p>
      </div>

      <div className="space-y-6">
        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">1. Information We Collect</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            CASHFLOW collects information you provide directly, including your email address, company name, and password when you create an account. We also collect financial documents you upload for analysis, such as bank statements, GST reports, and Excel sales sheets.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">2. How We Use Your Information</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            We use your information to provide financial analysis services, generate reports, authenticate your account, and communicate with you about your account and our services. Uploaded documents are processed to extract financial metrics and generate cash flow forecasts, risk assessments, and recommendations.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">3. Data Storage and Security</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            Your data is stored in a local SQLite database. Access to your documents and analyses is restricted to your authenticated account using JWT-based session tokens. We implement reasonable security measures to protect your information, but no method of transmission over the internet is completely secure.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">4. Sharing and Disclosure</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            We do not sell or share your personal data with third parties. Financial documents are processed locally or through configured AI providers based on your selected processing mode (local or AWS). We do not disclose your data to external marketing partners.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">5. Your Rights</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            You may access, update, or delete your account and uploaded documents at any time through the application interface. To request deletion of all your data, contact the account administrator or delete your account through the application.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">6. Changes to This Policy</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page with an updated effective date.
          </p>
        </section>
      </div>
    </div>
  );
};

export default Privacy;
