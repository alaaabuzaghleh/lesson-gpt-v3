import { useEffect, useId, useRef } from 'react'
import { Bold, Heading2, Link as LinkIcon, Pilcrow } from 'lucide-react'
import { FormField } from './ui'
import { t } from '../i18n/ar'

type RichTextEditorProps = {
  label: string
  value: string
  onChange: (html: string) => void
  dir?: 'rtl' | 'ltr'
  hint?: string
}

function exec(command: string, value?: string) {
  document.execCommand(command, false, value)
}

export function RichTextEditor({ label, value, onChange, dir, hint }: RichTextEditorProps) {
  const id = useId()
  const editorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = editorRef.current
    if (!el) return
    if (document.activeElement === el) return
    if ((value || '') !== (el.innerHTML || '')) {
      el.innerHTML = value || ''
    }
  }, [value])

  const apply = (command: string, arg?: string) => {
    editorRef.current?.focus()
    exec(command, arg)
    onChange(editorRef.current?.innerHTML ?? '')
  }

  const addLink = () => {
    const url = window.prompt(t.catalog.editorLinkPrompt, 'https://')
    if (!url?.trim()) return
    apply('createLink', url.trim())
  }

  return (
    <FormField label={label} hint={hint ?? t.catalog.editorHint} id={id}>
      <div className="rte">
        <div className="rte-toolbar" role="toolbar" aria-label={label}>
          <button type="button" className="rte-btn" onClick={() => apply('bold')} title={t.catalog.editorBold}>
            <Bold size={15} />
          </button>
          <button type="button" className="rte-btn" onClick={() => apply('formatBlock', 'h2')} title={t.catalog.editorH2}>
            <Heading2 size={15} />
          </button>
          <button type="button" className="rte-btn" onClick={() => apply('formatBlock', 'p')} title={t.catalog.editorP}>
            <Pilcrow size={15} />
          </button>
          <button type="button" className="rte-btn" onClick={addLink} title={t.catalog.editorLink}>
            <LinkIcon size={15} />
          </button>
        </div>
        <div
          ref={editorRef}
          id={id}
          className="rte-editor"
          contentEditable
          dir={dir}
          suppressContentEditableWarning
          onInput={() => onChange(editorRef.current?.innerHTML ?? '')}
          onBlur={() => onChange(editorRef.current?.innerHTML ?? '')}
        />
      </div>
    </FormField>
  )
}
