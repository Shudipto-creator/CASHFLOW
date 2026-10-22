import React from 'react';

const Terms = () => {
  return (
    <div className="max-w-3xl mx-auto px-6 py-12 space-y-8">
      <div className="border-b border-[var(--border-color)] pb-4 mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">Terms and Conditions</h1>
        <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase">Effective date: October 17, 2026</p>
      </div>

      <div className="space-y-6">
        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">1. Acceptance of Terms</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            By accessing or using CASHFLOW, you agree to be bound by these Terms and Conditions. If you do not agree, you may not use the service.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">2. Account Registration</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            You must register an account with a valid email address and password to use CASHFLOW. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">3. Use of Service</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            You may use CASHFLOW to upload financial documents, run analyses, and generate reports for your own business purposes. You agree not to upload content that is unlawful, harmful, or that you do not have the right to share.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">4. AI-Generated Insights</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            CASHFLOW uses AI models to generate financial analysis, forecasts, and recommendations. These outputs are for informational purposes only and do not constitute professional financial, legal, or tax advice. You should consult with a qualified professional before making financial decisions based on this output.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">5. Limitation of Liability</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            To the fullest extent permitted by law, CASHFLOW and its providers are not liable for any indirect, incidental, or consequential damages arising out of your use of or inability to use the service, including reliance on AI-generated insights.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">6. Termination</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            We may terminate or suspend your account at any time, without notice, for conduct that violates these Terms. Upon termination, your right to use the service will immediately cease.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">7. Governing Law</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            These Terms are governed by and construed in accordance with the laws of the jurisdiction in which CASHFLOW is operated, without regard to conflict of law principles.
          </p>
        </section>

        <section>
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-3 uppercase tracking-wider">8. Contact</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            If you have questions about these Terms, please contact the account administrator through the application.
          </p>
        </section>
      </div>
    </div>
  );
};

export default Terms;
