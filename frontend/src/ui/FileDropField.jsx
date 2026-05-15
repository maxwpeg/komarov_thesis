import React, { useRef, useState } from 'react';

function formatFileSize(bytes) {
  const numeric = Number(bytes || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return '0 B';
  }
  if (numeric < 1024) {
    return `${numeric} B`;
  }
  if (numeric < 1024 * 1024) {
    return `${(numeric / 1024).toFixed(1)} KB`;
  }
  return `${(numeric / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileDropField({
  accept,
  disabled = false,
  compact = false,
  title,
  description,
  buttonLabel,
  onSelect,
  className = '',
}) {
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [lastFile, setLastFile] = useState(null);

  const handleFiles = (fileList) => {
    const file = fileList?.[0] || null;
    if (!file || disabled || typeof onSelect !== 'function') {
      return;
    }
    setLastFile(file);
    onSelect(file);
  };

  return (
    <div
      className={`file-drop-field${compact ? ' file-drop-field--compact' : ''}${dragActive ? ' file-drop-field--drag' : ''}${disabled ? ' file-drop-field--disabled' : ''}${className ? ` ${className}` : ''}`}
      onClick={() => {
        if (!disabled) {
          inputRef.current?.click();
        }
      }}
      onDragOver={(event) => {
        if (disabled) {
          return;
        }
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={(event) => {
        if (event.currentTarget.contains(event.relatedTarget)) {
          return;
        }
        setDragActive(false);
      }}
      onDrop={(event) => {
        if (disabled) {
          return;
        }
        event.preventDefault();
        setDragActive(false);
        handleFiles(event.dataTransfer?.files);
      }}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={(event) => {
        if (disabled) {
          return;
        }
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        aria-label={title || buttonLabel || 'Файл'}
        accept={accept}
        disabled={disabled}
        style={{ display: 'none' }}
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = '';
        }}
      />
      <div className="file-drop-field__body">
        {title && <div className="file-drop-field__title">{title}</div>}
        {description && <div className="file-drop-field__description">{description}</div>}
        {lastFile && (
          <div className="file-drop-field__meta">
            {lastFile.name} · {lastFile.type || 'unknown'} · {formatFileSize(lastFile.size)}
          </div>
        )}
      </div>
      <span className="file-drop-field__button">{buttonLabel}</span>
    </div>
  );
}
