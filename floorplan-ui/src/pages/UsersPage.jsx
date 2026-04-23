import React, { useEffect, useState } from 'react';

import { usersApi } from '../api/client';

function createUserDraft() {
  return {
    username: '',
    full_name: '',
    role: 'engineer',
    password: '',
    is_active: true,
  };
}

function buildEditDraft(user) {
  return {
    username: user?.username ?? '',
    full_name: user?.full_name ?? '',
    role: user?.role ?? 'engineer',
    is_active: Boolean(user?.is_active),
  };
}

function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState('');
  const [createForm, setCreateForm] = useState(createUserDraft());
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [editForm, setEditForm] = useState(buildEditDraft(null));
  const [resetPassword, setResetPassword] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const loadUsers = async (preferredUserId = null) => {
    setLoading(true);
    try {
      const data = await usersApi.list();
      setUsers(data);
      const nextSelectedUser =
        data.find((item) => item.id === preferredUserId)
        || data.find((item) => item.id === selectedUserId)
        || data[0]
        || null;
      setSelectedUserId(nextSelectedUser?.id ?? null);
      setEditForm(buildEditDraft(nextSelectedUser));
    } catch (error) {
      console.error('Error loading users:', error);
      setBanner(`Ошибка загрузки пользователей: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedUser = users.find((item) => item.id === selectedUserId) || null;

  const handleCreateChange = (event) => {
    const { name, value, type, checked } = event.target;
    setCreateForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleEditChange = (event) => {
    const { name, value, type, checked } = event.target;
    setEditForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSelectUser = (user) => {
    setSelectedUserId(user.id);
    setEditForm(buildEditDraft(user));
    setResetPassword('');
    setBanner('');
  };

  const handleCreateUser = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    setBanner('');
    try {
      const createdUser = await usersApi.create(createForm);
      setCreateForm(createUserDraft());
      setResetPassword('');
      await loadUsers(createdUser.id);
      setBanner(`Пользователь ${createdUser.full_name} создан`);
    } catch (error) {
      console.error('Error creating user:', error);
      setBanner(`Ошибка создания пользователя: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveUser = async (event) => {
    event.preventDefault();
    if (!selectedUser) {
      return;
    }
    setIsSaving(true);
    setBanner('');
    try {
      const updatedUser = await usersApi.update(selectedUser.id, editForm);
      await loadUsers(updatedUser.id);
      setBanner(`Профиль ${updatedUser.full_name} обновлен`);
    } catch (error) {
      console.error('Error updating user:', error);
      setBanner(`Ошибка обновления пользователя: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetPassword = async (event) => {
    event.preventDefault();
    if (!selectedUser || !resetPassword.trim()) {
      return;
    }
    setIsSaving(true);
    setBanner('');
    try {
      await usersApi.resetPassword(selectedUser.id, { password: resetPassword });
      setResetPassword('');
      setBanner(`Пароль для ${selectedUser.full_name} обновлен`);
    } catch (error) {
      console.error('Error resetting password:', error);
      setBanner(`Ошибка сброса пароля: ${error.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="users-page">
      <div className="users-page__hero project-list-container">
        <h1>Пользователи</h1>
        <p className="users-page__subtitle">
          Разработчик управляет учетными записями, ролями и доступом к проектам.
        </p>
        {banner && (
          <div className={`users-page__banner ${banner.startsWith('Ошибка') ? 'users-page__banner--error' : ''}`}>
            {banner}
          </div>
        )}
      </div>

      <div className="users-page__grid">
        <section className="project-list-container users-page__panel">
          <div className="users-page__panel-header">
            <h2>Создать пользователя</h2>
          </div>
          <form className="users-form" onSubmit={handleCreateUser}>
            <label className="users-form__field">
              <span>Полное имя</span>
              <input name="full_name" value={createForm.full_name} onChange={handleCreateChange} required />
            </label>
            <label className="users-form__field">
              <span>Логин</span>
              <input name="username" value={createForm.username} onChange={handleCreateChange} required />
            </label>
            <label className="users-form__field">
              <span>Роль</span>
              <select name="role" value={createForm.role} onChange={handleCreateChange}>
                <option value="engineer">Инженер</option>
                <option value="developer">Разработчик</option>
              </select>
            </label>
            <label className="users-form__field">
              <span>Стартовый пароль</span>
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                value={createForm.password}
                onChange={handleCreateChange}
                required
              />
            </label>
            <label className="users-form__checkbox">
              <input
                type="checkbox"
                name="is_active"
                checked={createForm.is_active}
                onChange={handleCreateChange}
              />
              <span>Активная учетная запись</span>
            </label>
            <button type="submit" className="btn btn-primary" disabled={isSaving}>
              {isSaving ? 'Сохранение...' : 'Создать'}
            </button>
          </form>
        </section>

        <section className="project-list-container users-page__panel users-page__panel--wide">
          <div className="users-page__panel-header">
            <h2>Список пользователей</h2>
          </div>
          {loading ? (
            <div className="loading">Загрузка пользователей...</div>
          ) : (
            <div className="users-page__workspace">
              <div className="users-page__list">
                {users.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    className={`users-page__list-item ${selectedUserId === user.id ? 'users-page__list-item--active' : ''}`}
                    onClick={() => handleSelectUser(user)}
                  >
                    <strong>{user.full_name}</strong>
                    <span>{user.username}</span>
                    <span>{user.role === 'developer' ? 'Разработчик' : 'Инженер'}</span>
                    <span>{user.is_active ? 'Активен' : 'Отключен'}</span>
                  </button>
                ))}
              </div>

              <div className="users-page__editor">
                {selectedUser ? (
                  <>
                    <form className="users-form" onSubmit={handleSaveUser}>
                      <div className="users-page__editor-header">
                        <h3>{selectedUser.full_name}</h3>
                        <span>{selectedUser.role === 'developer' ? 'Разработчик' : 'Инженер'}</span>
                      </div>
                      <label className="users-form__field">
                        <span>Полное имя</span>
                        <input name="full_name" value={editForm.full_name} onChange={handleEditChange} required />
                      </label>
                      <label className="users-form__field">
                        <span>Логин</span>
                        <input name="username" value={editForm.username} onChange={handleEditChange} required />
                      </label>
                      <label className="users-form__field">
                        <span>Роль</span>
                        <select name="role" value={editForm.role} onChange={handleEditChange}>
                          <option value="engineer">Инженер</option>
                          <option value="developer">Разработчик</option>
                        </select>
                      </label>
                      <label className="users-form__checkbox">
                        <input
                          type="checkbox"
                          name="is_active"
                          checked={editForm.is_active}
                          onChange={handleEditChange}
                        />
                        <span>Активная учетная запись</span>
                      </label>
                      <button type="submit" className="btn btn-primary" disabled={isSaving}>
                        {isSaving ? 'Сохранение...' : 'Сохранить изменения'}
                      </button>
                    </form>

                    <form className="users-form users-form--secondary" onSubmit={handleResetPassword}>
                      <h3>Сброс пароля</h3>
                      <label className="users-form__field">
                        <span>Новый пароль</span>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={resetPassword}
                          onChange={(event) => setResetPassword(event.target.value)}
                          required
                        />
                      </label>
                      <button type="submit" className="btn btn-secondary" disabled={isSaving || !resetPassword.trim()}>
                        Обновить пароль
                      </button>
                    </form>
                  </>
                ) : (
                  <div className="users-page__empty">Пользователи пока не созданы.</div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default UsersPage;
