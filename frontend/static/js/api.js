/**
 * Api — JWT-aware fetch wrapper
 * All screens use: Api.get(), Api.post(), Api.put(), Api.delete()
 * Token is read from localStorage on every call (no stale closures).
 */
const Api = {
  _headers() {
    const token = localStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  },

  async _handle(res) {
    if (res.status === 401) {
      App.showToast('Sesi berakhir. Silakan masuk kembali.', 'error');
      localStorage.clear();
      window.location.hash = 'login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Request gagal.');
    }
    if (res.status === 204) return null;
    return res.json();
  },

  async get(path) {
    return this._handle(await fetch(path, { headers: this._headers() }));
  },

  async post(path, body) {
    return this._handle(await fetch(path, {
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify(body),
    }));
  },

  async put(path, body) {
    return this._handle(await fetch(path, {
      method: 'PUT',
      headers: this._headers(),
      body: JSON.stringify(body),
    }));
  },

  async patch(path, body) {
    return this._handle(await fetch(path, {
      method: 'PATCH',
      headers: this._headers(),
      body: JSON.stringify(body),
    }));
  },

  async delete(path) {
    return this._handle(await fetch(path, {
      method: 'DELETE',
      headers: this._headers(),
    }));
  },

  // For login: application/x-www-form-urlencoded (OAuth2 form)
  async postForm(path, data) {
    return this._handle(await fetch(path, {
      method: 'POST',
      body: new URLSearchParams(data),
    }));
  },
};