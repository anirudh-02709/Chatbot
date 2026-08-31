import React from 'react'
import { cn } from '@/lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
}

export const Card: React.FC<CardProps> = ({ children, className }) => {
  return (
    <div
      className={cn(
        'rounded-lg border border-surface-border bg-surface-1 p-5 shadow-sm transition-colors duration-150',
        className
      )}
    >
      {children}
    </div>
  )
}
