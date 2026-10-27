import React from 'react';

const LoadingSpinner = ({ size = 'medium' }) => {
  const sizeClasses = {
    small: 'w-4 h-4 border-2',
    medium: 'w-8 h-8 border-[3px]',
    large: 'w-12 h-12 border-4',
  };

  return (
    <div className="flex justify-center items-center" role="status">
      <div
        className={`${sizeClasses[size]} animate-spin border-[var(--border-color)] border-t-[var(--primary-accent)] rounded-full`}
      />
      <span className="sr-only">Loading</span>
    </div>
  );
};

export default LoadingSpinner;
