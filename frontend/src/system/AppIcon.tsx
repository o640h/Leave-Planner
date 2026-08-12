type AppIconProps = {
  name:
    | 'consultants'
    | 'wallchart'
    | 'settings'
    | 'search'
    | 'plus'
    | 'edit'
    | 'calendar'
    | 'appearance'
    | 'profile'
    | 'jobPlan'
}

export function AppIcon({ name }: AppIconProps) {
  const commonProps = {
    'aria-hidden': true,
    className: 'app-icon',
    fill: 'none',
    viewBox: '0 0 24 24',
  }

  if (name === 'calendar') {
    return (
      <svg {...commonProps}>
        <path d="M5 4.5h14v15H5zM8 2.5v4M16 2.5v4M5 9h14M8.5 14l2 2 4.5-5" />
      </svg>
    )
  }

  if (name === 'consultants') {
    return (
      <svg {...commonProps}>
        <circle cx="9" cy="8" r="3" />
        <path d="M3.5 19c.4-4 2.2-6 5.5-6s5.1 2 5.5 6M15 6.5a3 3 0 0 1 0 5.8M16.5 14c2.4.6 3.7 2.3 4 5" />
      </svg>
    )
  }

  if (name === 'wallchart') {
    return (
      <svg {...commonProps}>
        <path d="M4 5.5h16v14H4zM8 3v5M16 3v5M4 9.5h16M8 13h2M12 13h2M16 13h1M8 16.5h2M12 16.5h2" />
      </svg>
    )
  }

  if (name === 'search') {
    return (
      <svg {...commonProps}>
        <circle cx="10.5" cy="10.5" r="5.5" />
        <path d="m15 15 4.5 4.5" />
      </svg>
    )
  }

  if (name === 'appearance') {
    return (
      <svg {...commonProps}>
        <path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5A6.5 6.5 0 0 1 12 3.5Z" />
        <path d="M12 3.5V20.5" />
      </svg>
    )
  }

  if (name === 'plus') {
    return (
      <svg {...commonProps}>
        <path d="M12 5v14M5 12h14" />
      </svg>
    )
  }

  if (name === 'edit') {
    return (
      <svg {...commonProps}>
        <path d="m5 16-.5 3.5L8 19l10.5-10.5-3-3zM13.5 7.5l3 3" />
      </svg>
    )
  }

  if (name === 'profile') {
    return (
      <svg {...commonProps}>
        <circle cx="12" cy="7.5" r="3.5" />
        <path d="M5.5 21v-2c0-4 2.2-6 6.5-6s6.5 2 6.5 6v2" />
      </svg>
    )
  }

  if (name === 'jobPlan') {
    return (
      <svg {...commonProps}>
        <path d="M3.5 8h17v11h-17zM8.5 8V5h7v3M3.5 12.5h17M10 12.5v2h4v-2" />
      </svg>
    )
  }

  if (name === 'settings') {
    return (
      <svg {...commonProps}>
        <path d="M9.5 3.5h5l.5 2.2 1.3.8 2.2-.7L21 10.2l-1.7 1.5v1.6l1.7 1.5-2.5 4.4-2.2-.7-1.3.8-.5 2.2h-5L9 19.3l-1.3-.8-2.2.7L3 14.8l1.7-1.5v-1.6L3 10.2l2.5-4.4 2.2.7L9 5.7z" />
        <circle cx="12" cy="12.5" r="3" />
      </svg>
    )
  }

  return (
    <svg {...commonProps}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" />
    </svg>
  )
}
