import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login } = useAuth();
  const [formState, setFormState] = useState({
    username: '',
    password: '',
  });
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormState((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage('');

    try {
      await login(formState);
      const targetPath = location.state?.from?.pathname || '/';
      navigate(targetPath, { replace: true });
    } catch (error) {
      setErrorMessage(error?.message || 'Не удалось войти в систему');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-page__backdrop" />
      <div className="auth-card">
        <div className="auth-card__eyebrow">Кульман</div>
        <h1>Вход в систему</h1>
        <p className="auth-card__subtitle">
          Авторизация обязательна. После входа вы попадете в рабочее пространство проекта.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-form__field">
            <span>Логин</span>
            <input
              type="text"
              name="username"
              autoComplete="username"
              value={formState.username}
              onChange={handleChange}
              required
            />
          </label>

          <label className="auth-form__field">
            <span>Пароль</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={formState.password}
              onChange={handleChange}
              required
            />
          </label>

          {errorMessage && <div className="auth-form__error">{errorMessage}</div>}

          <button type="submit" className="btn btn-primary auth-form__submit" disabled={isSubmitting}>
            {isSubmitting ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
