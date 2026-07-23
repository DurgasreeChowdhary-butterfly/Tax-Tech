import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary'
  loading?: boolean
}

export function Button({ variant = 'primary', loading = false, disabled, children, className = '', ...rest }: ButtonProps) {
  const base =
    'inline-flex w-full items-center justify-center rounded-lg px-4 py-3 text-base font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto'
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus-visible:outline-blue-600',
    secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 focus-visible:outline-gray-400 dark:bg-gray-800 dark:text-gray-100 dark:hover:bg-gray-700',
  }

  return (
    <button className={`${base} ${variants[variant]} ${className}`} disabled={disabled || loading} aria-busy={loading} {...rest}>
      {loading ? 'Please wait…' : children}
    </button>
  )
}
