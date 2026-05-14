import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

const DialogContext = createContext(null);

function createId(prefix = 'dialog') {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

export function DialogProvider({ children }) {
  const [toastItems, setToastItems] = useState([]);
  const [dialogState, setDialogState] = useState(null);
  const dialogResolverRef = useRef(null);

  const dismissToast = useCallback((toastId) => {
    setToastItems((prev) => prev.filter((item) => item.id !== toastId));
  }, []);

  const toast = useCallback((message, options = {}) => {
    const id = createId('toast');
    const nextToast = {
      id,
      tone: options.tone || 'info',
      title: options.title || '',
      message: String(message || ''),
    };
    setToastItems((prev) => [...prev, nextToast]);
    window.setTimeout(() => dismissToast(id), options.duration ?? 4200);
  }, [dismissToast]);

  const closeDialog = useCallback((value) => {
    if (dialogResolverRef.current) {
      dialogResolverRef.current(value);
    }
    dialogResolverRef.current = null;
    setDialogState(null);
  }, []);

  const confirm = useCallback((message, options = {}) => new Promise((resolve) => {
    dialogResolverRef.current = resolve;
    setDialogState({
      kind: 'confirm',
      title: options.title || 'Подтверждение',
      message: String(message || ''),
      confirmLabel: options.confirmLabel || 'Подтвердить',
      cancelLabel: options.cancelLabel || 'Отмена',
    });
  }), []);

  const prompt = useCallback((message, options = {}) => new Promise((resolve) => {
    dialogResolverRef.current = resolve;
    setDialogState({
      kind: 'prompt',
      title: options.title || 'Введите значение',
      message: String(message || ''),
      confirmLabel: options.confirmLabel || 'Сохранить',
      cancelLabel: options.cancelLabel || 'Отмена',
      defaultValue: options.defaultValue || '',
      placeholder: options.placeholder || '',
    });
  }), []);

  useEffect(() => {
    const originalAlert = window.alert;
    window.alert = (message) => {
      toast(message, { tone: 'error' });
    };
    return () => {
      window.alert = originalAlert;
    };
  }, [toast]);

  const contextValue = useMemo(() => ({
    confirm,
    prompt,
    toast,
  }), [confirm, prompt, toast]);

  return (
    <DialogContext.Provider value={contextValue}>
      {children}

      {toastItems.length > 0 && (
        <div className="app-toast-stack" role="status" aria-live="polite">
          {toastItems.map((item) => (
            <div key={item.id} className={`app-toast app-toast--${item.tone}`}>
              <div>
                {item.title && <div className="app-toast__title">{item.title}</div>}
                <div className="app-toast__message">{item.message}</div>
              </div>
              <button type="button" className="app-toast__close" onClick={() => dismissToast(item.id)} aria-label="Закрыть уведомление">
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {dialogState && (
        <div className="app-dialog-backdrop" role="presentation">
          <div className="app-dialog" role="dialog" aria-modal="true" aria-labelledby="app-dialog-title">
            <h3 id="app-dialog-title" className="app-dialog__title">{dialogState.title}</h3>
            <div className="app-dialog__message">{dialogState.message}</div>
            {dialogState.kind === 'prompt' ? (
              <PromptBody dialogState={dialogState} onClose={closeDialog} />
            ) : (
              <div className="app-dialog__actions">
                <button type="button" className="btn btn-secondary" onClick={() => closeDialog(false)}>
                  {dialogState.cancelLabel}
                </button>
                <button type="button" className="btn btn-primary" onClick={() => closeDialog(true)}>
                  {dialogState.confirmLabel}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

function PromptBody({ dialogState, onClose }) {
  const [value, setValue] = useState(dialogState.defaultValue || '');

  return (
    <>
      <input
        autoFocus
        className="app-dialog__input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={dialogState.placeholder}
      />
      <div className="app-dialog__actions">
        <button type="button" className="btn btn-secondary" onClick={() => onClose(null)}>
          {dialogState.cancelLabel}
        </button>
        <button type="button" className="btn btn-primary" onClick={() => onClose(value)}>
          {dialogState.confirmLabel}
        </button>
      </div>
    </>
  );
}

export function useDialogs() {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error('useDialogs must be used inside DialogProvider');
  }
  return context;
}
