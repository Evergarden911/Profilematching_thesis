/**
 * Pramita Lab - MPA Frontend Controller
 * Kode ini telah dibersihkan dari logika SPA routing.
 * Tugas file ini murni hanya untuk kontrol UI sekunder (Modal, Toast, Logout).
 */
const App = {
  // Fungsi pemanggil modal secara lazy-load
  async loadModal(modalName, id = null) {
    try {
      const response = await fetch(`/modals/${modalName}.html`);
      if (!response.ok) throw new Error('Komponen modal tidak ditemukan');
      const html = await response.text();
      
      const container = document.getElementById('modal-container');
      container.innerHTML = html;
      
      // Keamanan UX: Tutup modal jika area luar diklik
      const backdrop = container.querySelector('.modal-backdrop');
      if (backdrop) {
        backdrop.addEventListener('click', e => {
          if (e.target === backdrop) this.closeModal();
        });
      }

      // Jika ada logika passing ID ke dalam modal, letakkan di sini
      if (id) {
        console.log(`Membuka modal ${modalName} untuk record ID:`, id);
      }
    } catch (error) {
      console.error(error);
      this.showToast('Gagal memuat komponen antarmuka.', 'error');
    }
  },

  closeModal() {
    document.getElementById('modal-container').innerHTML = '';
  },

  showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    
    setTimeout(() => toast.remove(), 3500);
  },

  async logout() {
    try {
      // Cookie bersifat httponly — JS tidak bisa menghapusnya langsung.
      // Wajib memanggil endpoint server agar Set-Cookie: Max-Age=0 dikirim.
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (_) {
      // Tetap redirect meski request gagal
    } finally {
      window.location.href = '/';
    }
  }
};

// Daftarkan App ke global scope agar bisa dipanggil dari atribut onclick di HTML
window.App = App;