const grid = document.querySelector('#donation-grid');
const searchInput = document.querySelector('#search');
const categorySelect = document.querySelector('#category');
const statusSelect = document.querySelector('#status-filter');
const formDialog = document.querySelector('#donation-dialog');
const claimDialog = document.querySelector('#claim-dialog');
const toast = document.querySelector('#toast');
let donations = [];
let claimingId = null;
let toastTimer;

const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusLabel = status => ({available:'Available',reserved:'Reserved',collected:'Collected'}[status] || status);
function timeLeft(dateString) {
  const hours = Math.max(0, Math.ceil((new Date(dateString) - Date.now()) / 36e5));
  if (hours < 1) return 'Pickup due soon';
  if (hours < 24) return `Pickup in ${hours}h`;
  return `Pickup in ${Math.ceil(hours / 24)}d`;
}
function showToast(message) {
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 3200);
}
async function api(path, options = {}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Something went wrong. Please try again.');
  return payload;
}
async function loadDonations() {
  document.querySelector('#loading-state').hidden = false;
  try {
    const data = await api('/api/donations');
    donations = data.donations;
    document.querySelector('#stat-active').textContent = data.stats.active;
    document.querySelector('#hero-active').textContent = data.stats.active;
    document.querySelector('#stat-meals').textContent = data.stats.meals.toLocaleString();
    document.querySelector('#stat-rescued').textContent = data.stats.rescued;
    renderDonations();
  } catch (error) {
    grid.innerHTML = `<div class="empty-state"><h3>Couldn’t reach the community board</h3><p>${escapeHtml(error.message)} Check that the app server is running, then refresh.</p></div>`;
  } finally {
    document.querySelector('#loading-state').hidden = true;
  }
}
function renderDonations() {
  const query = searchInput.value.trim().toLowerCase();
  const category = categorySelect.value;
  const status = statusSelect.value;
  const filtered = donations.filter(item => {
    const text = [item.title,item.category,item.location,item.donor,item.notes].join(' ').toLowerCase();
    const categoryMatches = category === 'all' || item.category.toLowerCase() === category.toLowerCase();
    return text.includes(query) && categoryMatches && (status === 'all' || item.status === status);
  });
  document.querySelector('#result-count').textContent = `${filtered.length} ${filtered.length === 1 ? 'listing' : 'listings'}`;
  document.querySelector('#empty-state').hidden = filtered.length !== 0;
  grid.innerHTML = filtered.map(item => `<article class="donation-card">
    <div class="card-top"><span class="category-tag">${escapeHtml(item.category)}</span><span class="status-tag ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span></div>
    <h3>${escapeHtml(item.title)}</h3><p class="quantity">${Number(item.quantity).toLocaleString()} ${escapeHtml(item.unit)} available</p>
    ${item.notes ? `<p class="card-notes">${escapeHtml(item.notes)}</p>` : ''}
    <div class="card-meta"><span>⌖ ${escapeHtml(item.location)}</span><span>◷ ${escapeHtml(timeLeft(item.expires_at))}</span></div>
    <div class="card-footer"><span class="donor-info">From ${escapeHtml(item.donor)}${item.claimed_by ? ` · held for ${escapeHtml(item.claimed_by)}` : ''}${item.status === 'reserved' ? ` · <a href="tel:${escapeHtml(item.phone)}">${escapeHtml(item.phone)}</a>` : ''}</span><div class="card-actions">${item.status === 'available' ? `<button class="card-action" data-claim="${item.id}">Reserve ↗</button>` : item.status === 'reserved' ? `<button class="card-action" data-status="${item.id}" data-next="collected">Mark collected</button>` : `<button class="card-action" data-status="${item.id}" data-next="available">Relist</button>`}</div></div>
  </article>`).join('');
}
document.querySelectorAll('[data-open-form]').forEach(button => button.addEventListener('click', () => {
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  document.querySelector('[name="expires_at"]').min = now.toISOString().slice(0,16);
  const deadline = new Date(now.getTime() + 8 * 3600000);
  document.querySelector('[name="expires_at"]').value = deadline.toISOString().slice(0,16);
  document.querySelector('#form-error').textContent = '';
  formDialog.showModal();
}));
document.querySelectorAll('.close-button').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); }));
searchInput.addEventListener('input', renderDonations);
categorySelect.addEventListener('change', renderDonations);
statusSelect.addEventListener('change', renderDonations);
document.querySelector('#clear-filters').addEventListener('click', () => { searchInput.value=''; categorySelect.value='all'; statusSelect.value='all'; renderDonations(); });

document.querySelector('#donation-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('[type="submit"]');
  const data = Object.fromEntries(new FormData(form));
  data.quantity = Number(data.quantity);
  button.disabled = true; button.textContent = 'Posting…';
  try {
    const result = await api('/api/donations', {method:'POST', body:JSON.stringify(data)});
    donations.unshift(result.donation);
    formDialog.close(); form.reset(); renderDonations();
    showToast('Your donation is live on the community board.');
    document.querySelector('#donations').scrollIntoView({behavior:'smooth'});
  } catch (error) { document.querySelector('#form-error').textContent = error.message; }
  finally { button.disabled = false; button.innerHTML = 'Post donation <span>↗</span>'; }
});

grid.addEventListener('click', async event => {
  const claimButton = event.target.closest('[data-claim]');
  const statusButton = event.target.closest('[data-status]');
  if (claimButton) {
    claimingId = claimButton.dataset.claim;
    document.querySelector('#claim-error').textContent = '';
    claimDialog.showModal();
  }
  if (statusButton) {
    statusButton.disabled = true;
    try {
      await api(`/api/donations/${statusButton.dataset.status}/status`, {method:'PATCH', body:JSON.stringify({status:statusButton.dataset.next})});
      await loadDonations();
      showToast(statusButton.dataset.next === 'collected' ? 'Marked collected. Thank you for sharing!' : 'Donation is back on the board.');
    } catch(error) { showToast(error.message); statusButton.disabled = false; }
  }
});
document.querySelector('#claim-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    await api(`/api/donations/${claimingId}/claim`, {method:'PATCH', body:JSON.stringify({partner:new FormData(event.currentTarget).get('partner')})});
    claimDialog.close(); event.currentTarget.reset(); await loadDonations();
    showToast('Reserved! The donor’s phone number is now on the listing.');
  } catch(error) { document.querySelector('#claim-error').textContent = error.message; }
  finally { button.disabled = false; }
});
loadDonations();
