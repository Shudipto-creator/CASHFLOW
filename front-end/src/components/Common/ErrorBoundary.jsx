import React, { Component } from 'react';

const DEFAULT_FALLBACK = ({ error, resetError }) => (
  <div className="surface-card p-6 mx-auto w-full max-w-md">
    <div className="flex flex-col items-center gap-3">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--negative-color)]/10 text-[var(--negative-color)]">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h3 className="text-xs font-medium uppercase tracking-[0.15em] text-[var(--text-primary)]">Something went wrong</h3>
      <p className="text-[10px] text-center text-[var(--text-muted)] leading-relaxed">
        {error && error.message ? error.message : 'An unexpected error occurred.'}
      </p>
      <button
        onClick={resetError}
        className="btn-primary uppercase tracking-[0.1em] text-xs px-4 py-2"
      >
        Try again
      </button>
    </div>
  </div>
);

export class ErrorBoundary extends Component {
  state = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary] Uncaught error:', error, errorInfo);
  }

  resetError = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    const { children, fallback } = this.props;
    const { hasError, error } = this.state;

    if (hasError) {
      if (fallback) return fallback;
      return <DEFAULT_FALLBACK error={error} resetError={this.resetError} />;
    }

    return children;
  }
}

export default ErrorBoundary;
