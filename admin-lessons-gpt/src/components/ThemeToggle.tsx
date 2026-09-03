import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { t } from '../i18n/ar'

type Props = {
  className?: string
  compact?: boolean
}

export function ThemeToggle({ className = '', compact = false }: Props) {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      className={`theme-toggle ${compact ? 'theme-toggle-compact' : ''} ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={isDark ? t.theme.switchToLight : t.theme.switchToDark}
      title={isDark ? t.theme.light : t.theme.dark}
    >
      <span className="theme-toggle-track" aria-hidden>
        <span className={`theme-toggle-thumb ${isDark ? 'is-dark' : ''}`}>
          {isDark ? <Moon size={14} /> : <Sun size={14} />}
        </span>
      </span>
      {!compact && <span className="theme-toggle-label">{isDark ? t.theme.dark : t.theme.light}</span>}
    </button>
  )
}
